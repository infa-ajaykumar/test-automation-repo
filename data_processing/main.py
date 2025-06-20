import os
import time
import logging
import psycopg2
from psycopg2.extras import Json # Will be needed later for attributes
from elasticsearch import Elasticsearch, exceptions as es_exceptions
import pika
import json
from datetime import datetime, timezone # Added back
from geopy.geocoders import Nominatim # Added back
from geopy.extra.rate_limiter import RateLimiter # Added back
import re # Added back

# --- Configuration ---
RABBITMQ_HOST = os.environ.get('RABBITMQ_HOST', 'rabbitmq')
RABBITMQ_USER = os.environ.get('RABBITMQ_USER', 'user')
RABBITMQ_PASS = os.environ.get('RABBITMQ_PASS', 'password')
RABBITMQ_QUEUE_RAW = 'property_listings_raw'

GEOPY_USER_AGENT = os.environ.get('GEOPY_USER_AGENT', 'RealEstateAggregator/1.0 (your-email@example.com)')

POSTGRES_HOST = os.environ.get('POSTGRES_HOST', 'postgres_db')
POSTGRES_DB = os.environ.get('POSTGRES_DB', 'realestate_listings')
POSTGRES_USER = os.environ.get('POSTGRES_USER', 'dbuser')
POSTGRES_PASSWORD = os.environ.get('POSTGRES_PASSWORD', 'dbpassword')

ELASTICSEARCH_HOST = os.environ.get('ELASTICSEARCH_HOST', 'elasticsearch')
ELASTICSEARCH_PORT = int(os.environ.get('ELASTICSEARCH_PORT', 9200))
ELASTICSEARCH_INDEX_NAME = os.environ.get('ELASTICSEARCH_INDEX_NAME', 'property_listings')

LOG_FORMAT = '%(asctime)s - %(levelname)s - %(name)s - %(module)s - %(funcName)s - %(lineno)d - %(message)s'
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

pg_conn_global = None
es_client_global = None

try:
    geolocator = Nominatim(user_agent=GEOPY_USER_AGENT)
    geocode_func = RateLimiter(geolocator.geocode, min_delay_seconds=1.1, error_wait_seconds=10.0, max_retries=3, swallow_exceptions=True)
except Exception as e_geo_init:
    logger.error(f"Failed to initialize Nominatim geolocator: {e_geo_init}", exc_info=True)
    def geocode_func_dummy(query, addressdetails=None, timeout=None):
        logger.warning(f"Using dummy geocode function. Query: {query}")
        return None
    geocode_func = geocode_func_dummy

ES_INDEX_SETTINGS = {
    "mappings": { "properties": {
        "title": {"type": "text", "analyzer": "english"}, "description": {"type": "text", "analyzer": "english"},
        "price_usd": {"type": "double"}, "location_original": {"type": "text"}, "address_full": {"type": "text"},
        "city": {"type": "keyword"}, "state": {"type": "keyword"}, "zip_code": {"type": "keyword"}, "country": {"type": "keyword"},
        "bedrooms": {"type": "float"}, "bathrooms": {"type": "float"}, "area_sqft": {"type": "double"},
        "source_site": {"type": "keyword"},
        "date_posted": {"type": "date", "format": "strict_date_optional_time||epoch_millis||yyyy-MM-dd HH:mm:ss||yyyy-MM-dd'T'HH:mm:ssZ||yyyy-MM-dd"},
        "date_scraped_utc": {"type": "date", "format": "strict_date_optional_time||epoch_millis"},
        "date_processed_utc": {"type": "date", "format": "strict_date_optional_time||epoch_millis"},
        "url": {"type": "keyword"}, "images": {"type": "keyword", "index": False},
        "location_point": {"type": "geo_point"}, "attributes": {"type": "object", "enabled": False}
    }}}

def connect_postgres_with_retry():
    global pg_conn_global
    if pg_conn_global and not pg_conn_global.closed:
        try:
            with pg_conn_global.cursor() as cur: cur.execute("SELECT 1")
            logger.info("PostgreSQL connection already active and valid.")
            return True
        except psycopg2.Error:
            logger.warning("PostgreSQL connection found closed or invalid. Reconnecting.")
            try: pg_conn_global.close()
            except psycopg2.Error: pass
            pg_conn_global = None
    attempts = 0; max_attempts = 5
    while attempts < max_attempts:
        try:
            logger.info(f"Connecting to PostgreSQL (attempt {attempts+1}/{max_attempts})")
            pg_conn_global = psycopg2.connect(host=POSTGRES_HOST, database=POSTGRES_DB, user=POSTGRES_USER, password=POSTGRES_PASSWORD, connect_timeout=10)
            pg_conn_global.autocommit = True
            logger.info("PostgreSQL connection successful.")
            return True
        except psycopg2.OperationalError as e:
            attempts += 1; wait_time = min(30, 5 * attempts)
            logger.error(f"PG connect error (attempt {attempts}): {e}. Retrying in {wait_time}s.")
            time.sleep(wait_time)
    logger.error(f"Failed to connect to PostgreSQL after {max_attempts} attempts.")
    pg_conn_global = None; return False

def connect_elasticsearch_with_retry():
    global es_client_global
    if es_client_global:
        try:
            if es_client_global.ping(): logger.info("ES connection active."); return True
            else: logger.warning("ES ping failed. Reconnecting.")
        except es_exceptions.ConnectionError: logger.warning("ES ping failed (ConnectionError). Reconnecting.")
        es_client_global = None
    attempts = 0; max_attempts = 5
    while attempts < max_attempts:
        try:
            logger.info(f"Connecting to ES (attempt {attempts+1}/{max_attempts})")
            es_client_global = Elasticsearch([{'host': ELASTICSEARCH_HOST, 'port': ELASTICSEARCH_PORT, 'scheme': 'http'}], request_timeout=20, max_retries=3, retry_on_timeout=True)
            if not es_client_global.ping(): raise es_exceptions.ConnectionError("ES ping failed post-connect.")
            logger.info("ES connection successful.")
            if not es_client_global.indices.exists(index=ELASTICSEARCH_INDEX_NAME):
                logger.info(f"Creating ES index: {ELASTICSEARCH_INDEX_NAME}")
                try: es_client_global.indices.create(index=ELASTICSEARCH_INDEX_NAME, body=ES_INDEX_SETTINGS)
                except es_exceptions.RequestError as e_create:
                    if 'resource_already_exists_exception' in str(e_create.info).lower(): logger.info(f"ES index {ELASTICSEARCH_INDEX_NAME} already exists.")
                    else: raise
            return True
        except es_exceptions.ConnectionError as e:
            attempts += 1; wait_time = min(30, 5 * attempts)
            logger.error(f"ES connect error (attempt {attempts}): {e}. Retrying in {wait_time}s.")
            time.sleep(wait_time)
        except Exception as e_es_other:
            attempts +=1; wait_time = min(30, 5 * attempts)
            logger.error(f"ES setup error (attempt {attempts}): {e_es_other}. Retrying in {wait_time}s.", exc_info=True)
            time.sleep(wait_time)
    logger.error(f"Failed to connect to ES after {max_attempts} attempts."); es_client_global = None; return False

# --- NORMALIZATION AND PARSING FUNCTIONS (Copied from full version) ---
def normalize_price(price_str):
    if price_str is None: return None, None
    if not isinstance(price_str, str): price_str = str(price_str)
    currency = 'USD'; price_str_no_curr = price_str
    if '€' in price_str: currency = 'EUR'; price_str_no_curr = price_str.replace('€', '')
    elif '£' in price_str: currency = 'GBP'; price_str_no_curr = price_str.replace('£', '')
    elif 'CAD' in price_str.upper(): currency = 'CAD'; price_str_no_curr = price_str.upper().replace('CAD', '')
    price_str_no_curr = price_str_no_curr.replace('$', '').strip()
    cleaned_price_chars = []; found_decimal = False; has_digits = False
    for char_idx, char in enumerate(price_str_no_curr):
        if char.isdigit(): cleaned_price_chars.append(char); has_digits = True
        elif char == '.' and not found_decimal:
            if not cleaned_price_chars and len(price_str_no_curr) > char_idx + 1 and price_str_no_curr[char_idx+1].isdigit(): cleaned_price_chars.append('0')
            cleaned_price_chars.append(char); found_decimal = True
        elif char == ',' and not found_decimal: pass
        elif char == ',' and found_decimal :
             if '.' in cleaned_price_chars: pass
             else: cleaned_price_chars.append('.'); found_decimal = True
    if not has_digits: return None, currency
    cleaned_price = "".join(cleaned_price_chars)
    if ',' in cleaned_price and '.' in cleaned_price:
        if cleaned_price.rfind(',') > cleaned_price.rfind('.'): cleaned_price = cleaned_price.replace('.', '').replace(',', '.')
        else: cleaned_price = cleaned_price.replace(',', '')
    elif ',' in cleaned_price: cleaned_price = cleaned_price.replace(',', '.')
    if not cleaned_price: return None, currency
    try: return round(float(cleaned_price), 2), currency
    except ValueError: logger.warning(f"Price norm error: '{price_str}' -> '{cleaned_price}'"); return None, currency

def normalize_area(area_str):
    if area_str is None: return None
    if not isinstance(area_str, str): area_str = str(area_str)
    area_str_lower = area_str.lower()
    match = re.search(r'(\d[\d,\.]*\.?\d*|\.\d+)', area_str_lower)
    if not match: logger.warning(f"Area norm error: No number in {area_str}"); return None
    num_str = match.group(1).replace(',', '')
    try:
        area_val = float(num_str)
        if 'm2' in area_str_lower or 'sqm' in area_str_lower or 'meter' in area_str_lower: return round(area_val * 10.7639, 2)
        return round(area_val, 2)
    except ValueError: logger.warning(f"Area norm error: '{area_str}' -> '{num_str}'"); return None

def normalize_bedrooms_bathrooms(attr_str):
    if attr_str is None: return None
    if not isinstance(attr_str, str): attr_str = str(attr_str)
    attr_lower = attr_str.lower()
    if "studio" in attr_lower: return 0.5
    match = re.search(r'(\d+\.?\d*|\.\d+)', attr_str)
    if not match: logger.warning(f"Bed/bath norm error: No num in {attr_str}"); return None
    num_str = match.group(1)
    try: return float(num_str)
    except ValueError: logger.warning(f"Bed/bath norm error: '{attr_str}' -> '{num_str}'"); return None

def parse_datetime_flexible(dt_str):
    if not dt_str: return None
    try:
        if isinstance(dt_str, datetime): return dt_str.astimezone(timezone.utc) if dt_str.tzinfo else dt_str.replace(tzinfo=timezone.utc)
        dt_str_processed = str(dt_str).strip().replace('Z', '+00:00').replace('z', '+00:00').replace(' UTC', '+00:00').replace(' GMT', '+00:00')
        if 'T' not in dt_str_processed and ' ' in dt_str_processed:
            parts = dt_str_processed.split(' ', 1)
            if len(parts) == 2 and parts[0].count('-') == 2 and parts[1].count(':') >= 1: dt_str_processed = 'T'.join(parts)
        if 'T' in dt_str_processed:
            d_parts = dt_str_processed.split('T'); t_part = d_parts[1]
            if t_part.count(':') == 1: # HH:MM
                if re.fullmatch(r"\d{1,2}:\d{2}", t_part): dt_str_processed = d_parts[0] + 'T' + t_part + ":00"
                else: # HH:MM+-TZ
                    m = re.fullmatch(r"(\d{1,2}:\d{2})([\+\-].*)", t_part)
                    if m: dt_str_processed = d_parts[0] + 'T' + m.group(1) + ":00" + m.group(2)
        if '.' in dt_str_processed:
            main_p, frac_p_full = dt_str_processed.split('.', 1)
            frac_p = frac_p_full.split('+')[0].split('-')[0].split(' ')[0]
            tz_sfx = ""; m_tz = re.search(r"([\+\-])(\d{2}):?(\d{2})?([Zz])?$", frac_p_full)
            if m_tz: tz_sfx = m_tz.group(0)
            dt_str_processed = main_p + '.' + frac_p[:6] + tz_sfx
        dt_obj = datetime.fromisoformat(dt_str_processed)
        return dt_obj.astimezone(timezone.utc) if dt_obj.tzinfo else dt_obj.replace(tzinfo=timezone.utc)
    except Exception as e: logger.warning(f"Date parse error: '{str(dt_str)}' -> '{dt_str_processed}': {e}"); return None

# --- Main Data Processing Function ---
def process_listing(raw_data): # Renamed from placeholder
    processed = {}
    raw_url = raw_data.get('url')
    if not raw_url or not isinstance(raw_url, str) or not raw_url.strip().startswith(('http://', 'https://')):
        logger.error(f"Skipping item due to invalid URL: '{raw_url}'")
        return None
    processed['url'] = raw_url.strip()

    processed['title'] = str(raw_data.get('title','')).strip() if raw_data.get('title') else None
    processed['price_original'] = str(raw_data.get('price','')).strip() if raw_data.get('price') else None
    processed['location_original'] = str(raw_data.get('location','')).strip() if raw_data.get('location') else None

    raw_images = raw_data.get('images', [])
    if isinstance(raw_images, list):
        processed['images'] = [str(img_url).strip() for img_url in raw_images if isinstance(img_url, (str, bytes)) and str(img_url).strip().startswith(('http://', 'https://'))]
    elif isinstance(raw_images, (str, bytes)) and str(raw_images).strip().startswith(('http://', 'https://')):
        processed['images'] = [str(raw_images).strip()]
    else: processed['images'] = []

    processed['description'] = str(raw_data.get('description','')).strip() if raw_data.get('description') else None
    processed['date_posted'] = parse_datetime_flexible(raw_data.get('date_posted'))
    processed['date_scraped_utc'] = parse_datetime_flexible(raw_data.get('scrape_timestamp') or raw_data.get('date_scraped_utc'))
    processed['source_site'] = str(raw_data.get('source_site','')).strip() if raw_data.get('source_site') else None
    processed['date_processed_utc'] = datetime.now(timezone.utc)

    price_val, currency_orig = normalize_price(processed['price_original'])
    processed['price_usd'] = price_val; processed['currency_original'] = currency_orig
    processed['area_original'] = str(raw_data.get('area','')).strip() if raw_data.get('area') else None
    processed['area_sqft'] = normalize_area(processed['area_original'])
    processed['bedrooms'] = normalize_bedrooms_bathrooms(raw_data.get('bedrooms'))
    processed['bathrooms'] = normalize_bedrooms_bathrooms(raw_data.get('bathrooms'))

    location_query = processed['location_original']
    processed['latitude'], processed['longitude'] = None, None
    processed['address_full'], processed['city'], processed['state'], processed['zip_code'], processed['country'] = None, None, None, None, None

    if location_query and isinstance(location_query, str) and len(location_query.strip()) > 2 :
        logger.info(f"Geocoding: {location_query[:100]}")
        try:
            location_geo = geocode_func(location_query, addressdetails=True, timeout=15)
            if location_geo and hasattr(location_geo, 'latitude') and location_geo.latitude is not None and \
               hasattr(location_geo, 'longitude') and location_geo.longitude is not None:
                processed['latitude'] = location_geo.latitude; processed['longitude'] = location_geo.longitude
                processed['address_full'] = getattr(location_geo, 'address', None)
                if hasattr(location_geo, 'raw') and isinstance(location_geo.raw, dict):
                    addr = location_geo.raw.get('address', {})
                    processed['city'] = addr.get('city', addr.get('town', addr.get('village', addr.get('hamlet'))))
                    processed['state'] = addr.get('state', addr.get('county'))
                    processed['zip_code'] = addr.get('postcode')
                    processed['country'] = addr.get('country_code', '').upper() if addr.get('country_code') else None
            else: logger.warning(f"Geocoding invalid/missing lat/lon for: {location_query[:100]}. Result: {location_geo}")
        except Exception as e: logger.error(f"Geocoding error for '{location_query[:100]}': {e}", exc_info=True)
    else: logger.info(f"No/invalid location for geocoding: '{location_query}'")

    raw_attrs = raw_data.get('attributes', {}); processed['attributes'] = raw_attrs if isinstance(raw_attrs, dict) else {}
    expected_keys = ['title', 'price_original', 'price_usd', 'currency_original', 'location_original', 'address_full', 'city', 'state', 'zip_code', 'country', 'latitude', 'longitude', 'bedrooms', 'bathrooms', 'area_sqft', 'area_original', 'images', 'description', 'date_posted', 'date_scraped_utc', 'date_processed_utc', 'source_site', 'attributes']
    for key in expected_keys: processed.setdefault(key, None)

    # Convert datetime objects to ISO 8601 string format for JSON serialization
    if isinstance(processed.get('date_posted'), datetime):
        processed['date_posted'] = processed['date_posted'].isoformat()
    if isinstance(processed.get('date_scraped_utc'), datetime):
        processed['date_scraped_utc'] = processed['date_scraped_utc'].isoformat()
    if isinstance(processed.get('date_processed_utc'), datetime):
        processed['date_processed_utc'] = processed['date_processed_utc'].isoformat()

    return processed

# --- RabbitMQ Callback ---
def on_message_callback(ch, method, properties, body):
    logger.info(f"Received msg. Tag: {method.delivery_tag}")
    try:
        raw_data = json.loads(body.decode('utf-8'))
        url = raw_data.get('url', 'N/A URL')[:100]
        processed_item = process_listing(raw_data) # Now calls the full processing
        if processed_item:
            logger.info(f"Processed item for {url}: {json.dumps({k:v for k,v in processed_item.items() if k not in ['images', 'description']}, default=str)[:300]}...")
            # TODO NEXT: Call store_in_postgres(processed_item) and store_in_elasticsearch(processed_item)
        else: logger.warning(f"Processing returned None for {url}. Discarding.")
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}. Body: '{body[:200]}'. Discarding.", exc_info=False)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    except Exception as e:
        logger.error(f"Critical callback error: {e}", exc_info=True)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

# --- Main Consumer Loop ---
def main_consumer_loop():
    global pg_conn_global, es_client_global
    logger.info("Data Processing Service - Consumer Loop starting...")
    if not connect_postgres_with_retry(): logger.critical("No PG. Consumer exit."); return # Changed to use retry function
    if not connect_elasticsearch_with_retry(): # Changed to use retry function
        logger.critical("No ES. Consumer exit.")
        if pg_conn_global and not pg_conn_global.closed:
            try: pg_conn_global.close()
            except Exception: pass # Changed from psycopg2.Error to generic Exception
        return

    connection = None
    while True:
        try:
            if connection is None or connection.is_closed:
                logger.info("Connecting to RabbitMQ...")
                creds = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
                params = pika.ConnectionParameters(RABBITMQ_HOST, 5672, '/', creds, heartbeat=600, blocked_connection_timeout=300)
                connection = pika.BlockingConnection(params); logger.info("RabbitMQ connected.")

            channel = connection.channel()
            channel.queue_declare(queue=RABBITMQ_QUEUE_RAW, durable=True)
            cpu_c = os.cpu_count(); pf_val = max(1, (cpu_c - 1 if cpu_c and cpu_c > 1 else (1 if cpu_c == 1 else 2)))
            channel.basic_qos(prefetch_count=pf_val)
            channel.basic_consume(queue=RABBITMQ_QUEUE_RAW, on_message_callback=on_message_callback)
            logger.info(f"[*] Waiting for messages with prefetch {pf_val}. CTRL+C to exit.")
            channel.start_consuming()
        except pika.exceptions.AMQPConnectionError as e:
            logger.error(f"RMQ connection error: {e}. Retrying in 10s.", exc_info=False)
            if connection and connection.is_open:
                try: connection.close()
                except Exception: pass # Changed from pika.exceptions.AMQPError to generic Exception
            connection = None; time.sleep(10)
        except KeyboardInterrupt:
            logger.info("Consumer stopped by user."); break
        except Exception as e:
            logger.error(f"Unhandled consumer loop error: {e}", exc_info=True)
            if connection and connection.is_open:
                try: connection.close()
                except Exception: pass # Changed from pika.exceptions.AMQPError to generic Exception
            connection = None; logger.info("Restarting consumer in 10s."); time.sleep(10)

    logger.info("Shutting down consumer loop...")
    if pg_conn_global and not pg_conn_global.closed:
        try: pg_conn_global.close()
        except Exception: pass # Changed from psycopg2.Error to generic Exception
    logger.info("Consumer loop shut down.")

if __name__ == '__main__':
    main_consumer_loop()
```
