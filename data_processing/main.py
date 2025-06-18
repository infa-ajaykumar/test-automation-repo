import pika
import json
import time
import os
import logging
from datetime import datetime
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
# import psycopg2 # TODO: Uncomment when DB logic is added
# from psycopg2.extras import Json as PsycopgJson
# from elasticsearch import Elasticsearch, helpers # TODO: Uncomment when ES logic is added


# --- Configuration ---
RABBITMQ_HOST = os.environ.get('RABBITMQ_HOST', 'rabbitmq')
RABBITMQ_USER = os.environ.get('RABBITMQ_USER', 'user')
RABBITMQ_PASS = os.environ.get('RABBITMQ_PASS', 'password')
RABBITMQ_QUEUE_RAW = 'property_listings_raw'
# RABBITMQ_QUEUE_PROCESSED = 'property_listings_processed' # Not used yet

GEOPY_USER_AGENT = os.environ.get('GEOPY_USER_AGENT', 'RealEstateAggregator/1.0 (your-email@example.com)')

POSTGRES_HOST = os.environ.get('POSTGRES_HOST', 'postgres_db')
POSTGRES_DB = os.environ.get('POSTGRES_DB', 'realestate_listings')
POSTGRES_USER = os.environ.get('POSTGRES_USER', 'dbuser')
POSTGRES_PASSWORD = os.environ.get('POSTGRES_PASSWORD', 'dbpassword')

ELASTICSEARCH_HOST = os.environ.get('ELASTICSEARCH_HOST', 'elasticsearch')
ELASTICSEARCH_PORT = os.environ.get('ELASTICSEARCH_PORT', '9200')
ELASTICSEARCH_INDEX_NAME = os.environ.get('ELASTICSEARCH_INDEX_NAME', 'property_listings')

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Geocoding Setup ---
geolocator = Nominatim(user_agent=GEOPY_USER_AGENT)
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1.1, error_wait_seconds=10.0, max_retries=2)

# --- Database Connection (PostgreSQL) ---
# TODO: Implement robust connection handling and retries for DB
# def get_db_connection():
#     conn = psycopg2.connect(host=POSTGRES_HOST, dbname=POSTGRES_DB, user=POSTGRES_USER, password=POSTGRES_PASSWORD)
#     return conn

# --- Elasticsearch Connection ---
# TODO: Implement ES connection
# es_client = None
# try:
#     es_client = Elasticsearch(
#         [f"http://{ELASTICSEARCH_HOST}:{ELASTICSEARCH_PORT}"],
#         # Basic auth can be added here if XPack security is enabled later
#         # http_auth=('elastic', ELASTICSEARCH_PASSWORD),
#         retry_on_timeout=True,
#         max_retries=3
#     )
#     if not es_client.ping():
#         logging.error("Elasticsearch connection failed on ping.")
#         es_client = None # Set to None if ping fails
#     else:
#         logging.info("Successfully connected to Elasticsearch.")
#         # Create index if it doesn't exist (basic mapping, can be improved)
#         if not es_client.indices.exists(index=ELASTICSEARCH_INDEX_NAME):
#             es_client.indices.create(index=ELASTICSEARCH_INDEX_NAME, body={
#                 "mappings": {
#                     "properties": {
#                         "geom": {"type": "geo_point"},
#                         "date_posted": {"type": "date"},
#                         "date_scraped_utc": {"type": "date"},
#                         "date_processed_utc": {"type": "date"},
#                         "price_usd": {"type": "float"},
#                         "area_sqft": {"type": "float"},
#                         "bedrooms": {"type": "float"}, # Using float for flexibility e.g. 0.5 for studio
#                         "bathrooms": {"type": "float"}
#                         # Add other field mappings as needed
#                     }
#                 }
#             })
#             logging.info(f"Created Elasticsearch index: {ELASTICSEARCH_INDEX_NAME}")
# except Exception as e:
#     logging.error(f"Failed to connect to Elasticsearch or create index: {e}", exc_info=True)
#     es_client = None


def normalize_price(price_str):
    if not price_str or not isinstance(price_str, str): return None, None
    currency = 'USD'
    if '€' in price_str: currency = 'EUR'
    elif '£' in price_str: currency = 'GBP'
    cleaned_price = ''.join(filter(str.isdigit, price_str.split('.')[0]))
    try: return float(cleaned_price), currency
    except ValueError: return None, None

def normalize_area(area_str):
    if not area_str or not isinstance(area_str, str): return None
    area_str_lower = area_str.lower()
    num_str = ''.join(filter(lambda x: x.isdigit() or x == '.', area_str_lower))
    try:
        area_val = float(num_str)
        if 'm2' in area_str_lower or 'sqm' in area_str_lower: return area_val * 10.7639
        return area_val
    except ValueError: return None

def normalize_bedrooms_bathrooms(attr_str):
    if not attr_str or not isinstance(attr_str, str): return None
    num_str = ''.join(filter(lambda x: x.isdigit() or x == '.', attr_str))
    try: return float(num_str)
    except ValueError: return None

def parse_datetime(date_str):
    if not date_str: return None
    try:
        # Attempt to parse ISO 8601 format directly
        return datetime.fromisoformat(date_str.replace('Z', '+00:00')).isoformat()
    except ValueError:
        logging.warning(f"Could not parse date string '{date_str}' directly to ISO format.")
        return None # Or attempt other parsing methods

def process_listing(raw_data):
    processed = {}
    processed['title'] = raw_data.get('title')
    processed['price_original'] = raw_data.get('price')
    processed['location_original'] = raw_data.get('location')
    processed['images'] = raw_data.get('images', [])
    processed['description'] = raw_data.get('description')
    processed['url'] = raw_data.get('url')
    processed['date_posted'] = parse_datetime(raw_data.get('date_posted'))
    processed['date_scraped_utc'] = parse_datetime(raw_data.get('scrape_timestamp'))
    processed['source_site'] = raw_data.get('source_site')
    processed['date_processed_utc'] = datetime.utcnow().isoformat()

    price_val, currency_orig = normalize_price(raw_data.get('price'))
    processed['price_usd'] = price_val
    processed['currency_original'] = currency_orig

    processed['area_original'] = raw_data.get('area')
    processed['area_sqft'] = normalize_area(raw_data.get('area'))

    processed['bedrooms'] = normalize_bedrooms_bathrooms(raw_data.get('bedrooms'))
    processed['bathrooms'] = normalize_bedrooms_bathrooms(raw_data.get('bathrooms'))

    location_query = raw_data.get('location')
    if isinstance(location_query, dict):
        location_query = location_query.get('address', str(location_query))

    processed['latitude'], processed['longitude'] = None, None
    processed['address_full'], processed['city'], processed['state'], processed['zip_code'], processed['country'] = None, None, None, None, None

    if location_query:
        logging.info(f"Geocoding: {location_query[:100]}")
        try:
            location_geo = geocode(location_query, addressdetails=True, timeout=10)
            if location_geo and location_geo.raw and location_geo.raw.get('address'):
                processed['latitude'] = location_geo.latitude
                processed['longitude'] = location_geo.longitude
                processed['address_full'] = location_geo.address
                addr_details = location_geo.raw.get('address', {})
                processed['city'] = addr_details.get('city', addr_details.get('town', addr_details.get('village')))
                processed['state'] = addr_details.get('state')
                processed['zip_code'] = addr_details.get('postcode')
                processed['country'] = addr_details.get('country_code', '').upper()
            else: logging.warning(f"Geocoding failed or no address details for: {location_query[:100]}")
        except Exception as e: logging.error(f"Error during geocoding for '{location_query[:100]}': {e}")
    else: logging.info("No location provided for geocoding.")

    processed['attributes'] = raw_data.get('attributes', {})
    return processed

# def save_to_postgres(data):
#     # TODO: Implement actual save to PostgreSQL
#     # Handle potential duplicate URLs (ON CONFLICT DO UPDATE)
#     # Convert latitude/longitude to PostGIS GEOMETRY Point
#     logging.info(f"Placeholder: Save to PostgreSQL: {data.get('url')[:100]}")
#     # Example (highly simplified, needs error handling, connection management, real SQL):
#     # conn = get_db_connection()
#     # try:
#     #     with conn.cursor() as cur:
#     #         # geom_val = f"SRID=4326;POINT({data['longitude']} {data['latitude']})" if data.get('longitude') and data.get('latitude') else None
#     #         # cur.execute("INSERT INTO property_listings (url, ..., geom) VALUES (%s, ..., %s) ON CONFLICT (url) DO UPDATE SET ...", (...data_values..., geom_val))
#     #         # conn.commit()
#     # except Exception as e:
#     #     logging.error(f"Error saving to PostgreSQL: {e}")
#     #     # conn.rollback() # Important
#     # finally:
#     #     # conn.close() # Return to pool or close
#     pass


# def save_to_elasticsearch(data):
#     # TODO: Implement actual save to Elasticsearch
#     # Use URL as document ID if possible for idempotency
#     logging.info(f"Placeholder: Save to Elasticsearch: {data.get('url')[:100]}")
#     # if es_client:
#     #     try:
#     #         doc_id = data['url'] # Assuming URL is unique and suitable as ID
#     #         es_doc = data.copy()
#     #         if es_doc.get('latitude') and es_doc.get('longitude'):
#     #             es_doc['geom'] = {"lat": es_doc['latitude'], "lon": es_doc['longitude']}
#     #
#     #         # Remove fields not ideal for direct ES doc or handled by geom
#     #         # es_doc.pop('latitude', None)
#     #         # es_doc.pop('longitude', None)
#     #
#     #         helpers.bulk(es_client, [{
#     #             "_index": ELASTICSEARCH_INDEX_NAME,
#     #             "_id": doc_id,
#     #             "_source": es_doc
#     #         }])
#     #     except Exception as e:
#     #         logging.error(f"Error saving to Elasticsearch: {e}", exc_info=True)
#     pass

def on_message_callback(ch, method, properties, body):
    try:
        logging.info(f"Received raw message. Size: {len(body)} bytes.")
        raw_listing_data = json.loads(body.decode('utf-8'))

        logging.info(f"Processing listing: {raw_listing_data.get('url', 'N/A URL')[:100]}")
        processed_listing = process_listing(raw_listing_data)

        logging.info(f"Processed JSON: {json.dumps(processed_listing, indent=2)[:1000]}")

        # TODO: Call save_to_postgres and save_to_elasticsearch here
        # save_to_postgres(processed_listing.copy()) # Pass a copy
        # save_to_elasticsearch(processed_listing.copy()) # Pass a copy

        ch.basic_ack(delivery_tag=method.delivery_tag)
    except json.JSONDecodeError as e:
        logging.error(f"Failed to decode JSON: {e}. Body: {body[:200]}", exc_info=True)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    except Exception as e:
        logging.error(f"Error processing message: {e}", exc_info=True)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

def main():
    # Remove old test_consumer.py if it exists
    test_consumer_path = "data_processing/test_consumer.py" # Relative to repo root
    if os.path.exists(test_consumer_path):
        logging.info(f"Removing {test_consumer_path}")
        try:
            os.remove(test_consumer_path)
        except OSError as e:
            logging.error(f"Failed to remove {test_consumer_path}: {e}")

    # TODO: Initialize DB connection pool and ES client here if they are not module-level

    while True:
        try:
            logging.info("Connecting to RabbitMQ...")
            credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
            connection_params = pika.ConnectionParameters(
                RABBITMQ_HOST, 5672, '/', credentials,
                heartbeat=600, blocked_connection_timeout=300
            )
            connection = pika.BlockingConnection(connection_params)
            channel = connection.channel()
            channel.queue_declare(queue=RABBITMQ_QUEUE_RAW, durable=True)
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=RABBITMQ_QUEUE_RAW, on_message_callback=on_message_callback)
            logging.info(f"[*] Waiting for messages in {RABBITMQ_QUEUE_RAW}.")
            channel.start_consuming()
        except pika.exceptions.AMQPConnectionError as e:
            logging.error(f"RabbitMQ connection error: {e}. Retrying in 10s...")
            time.sleep(10)
        except Exception as e:
            logging.error(f"Unhandled exception in main: {e}", exc_info=True)
            time.sleep(10)

if __name__ == '__main__':
    main()
