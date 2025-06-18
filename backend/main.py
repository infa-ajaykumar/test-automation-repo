from fastapi import FastAPI, HTTPException, Query
from typing import List, Optional, Dict, Any
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from elasticsearch import Elasticsearch, exceptions as es_exceptions
import redis # Import redis
import json # For serializing/deserializing cache data
import logging

# --- Configuration ---
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://dbuser:dbpassword@postgres_db:5432/realestate_listings')
ELASTICSEARCH_HOST = os.environ.get('ELASTICSEARCH_HOST', 'elasticsearch')
ELASTICSEARCH_PORT = int(os.environ.get('ELASTICSEARCH_PORT', 9200))
ELASTICSEARCH_INDEX_NAME = os.environ.get('ELASTICSEARCH_INDEX_NAME', 'property_listings')
REDIS_HOST = os.environ.get('REDIS_HOST', 'redis_cache') # New
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))   # New
CACHE_EXPIRATION_SECONDS = int(os.environ.get('CACHE_EXPIRATION_SECONDS', 300)) # 5 minutes default

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Real Estate Aggregator API",
    description="API for searching and retrieving property listings.",
    version="0.1.0"
)

db_conn = None
es_client = None
redis_client = None # New

# --- Helper Functions for DB/ES/Redis Connection ---
def get_db_connection():
    global db_conn
    try:
        if db_conn is None or db_conn.closed:
            logger.info(f"Connecting to database...")
            db_conn = psycopg2.connect(DATABASE_URL)
            logger.info("Database connection successful.")
        return db_conn
    except psycopg2.OperationalError as e:
        logger.error(f"Database connection failed: {e}")
        db_conn = None
        raise HTTPException(status_code=503, detail="Database service unavailable.")
    except Exception as e_db_other:
        logger.error(f"An unexpected database error occurred: {e_db_other}")
        db_conn = None
        raise HTTPException(status_code=500, detail="Internal database error.")

def get_es_client():
    global es_client
    try:
        if es_client is None or not es_client.ping():
            logger.info(f"Connecting to Elasticsearch...")
            es_client = Elasticsearch(
                [{'host': ELASTICSEARCH_HOST, 'port': ELASTICSEARCH_PORT, 'scheme': 'http'}],
                request_timeout=10, max_retries=2, retry_on_timeout=True
            )
            if not es_client.ping():
                raise es_exceptions.ConnectionError("Elasticsearch ping failed after connect")
            logger.info("Elasticsearch connection successful.")
        return es_client
    except es_exceptions.ConnectionError as e:
        logger.error(f"Elasticsearch connection failed: {e}")
        es_client = None
        raise HTTPException(status_code=503, detail="Search service unavailable.")
    except Exception as e_es_other:
        logger.error(f"An unexpected Elasticsearch error occurred: {e_es_other}")
        es_client = None
        raise HTTPException(status_code=500, detail="Internal search service error.")

def get_redis_client(): # New function
    global redis_client
    try:
        if redis_client is None: # Initialize if None
            logger.info(f"Connecting to Redis: {REDIS_HOST}:{REDIS_PORT}")
            redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=False) # decode_responses=False to handle bytes for json
            redis_client.ping() # Check connection
            logger.info("Redis connection successful.")
        # Check if connection is still alive if already initialized
        elif not redis_client.ping():
            logger.warning("Redis ping failed, attempting to reconnect...")
            redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=False)
            redis_client.ping()
            logger.info("Redis re-connection successful.")
        return redis_client
    except redis.exceptions.ConnectionError as e:
        logger.error(f"Redis connection failed: {e}")
        redis_client = None # Reset client
        # Don't raise HTTPException here, allow services to degrade gracefully if cache is down
        return None # Indicate cache is unavailable
    except Exception as e_redis_other:
        logger.error(f"An unexpected Redis error occurred: {e_redis_other}")
        redis_client = None
        return None


@app.on_event("startup")
async def startup_event():
    try: get_db_connection()
    except HTTPException: logger.error("Startup: Failed to connect to PostgreSQL.")
    try: get_es_client()
    except HTTPException: logger.error("Startup: Failed to connect to Elasticsearch.")
    try: get_redis_client() # New
    except Exception: logger.error("Startup: Failed to connect to Redis.")


@app.on_event("shutdown")
async def shutdown_event():
    global db_conn, redis_client # Add redis_client
    if db_conn and not db_conn.closed:
        logger.info("Closing database connection.")
        db_conn.close()
    if redis_client: # New
        logger.info("Closing Redis connection.")
        redis_client.close()


@app.get("/health", summary="Health Check", tags=["Utility"])
async def health_check():
    db_status = "disconnected"
    es_status = "disconnected"
    redis_status = "disconnected" # New

    try:
        conn = get_db_connection()
        if conn and not conn.closed:
            with conn.cursor() as cursor: cursor.execute("SELECT 1")
            db_status = "connected"
    except Exception: db_status = "error"

    try:
        search_client = get_es_client()
        if search_client and search_client.ping(): es_status = "connected"
    except Exception: es_status = "error"

    try: # New
        cache_client = get_redis_client()
        if cache_client and cache_client.ping(): redis_status = "connected"
    except Exception: redis_status = "error"

    final_status = "ok"
    if db_status != "connected" or es_status != "connected" or redis_status != "connected":
        final_status = "degraded"

    return {"status": final_status, "database": db_status, "search_service": es_status, "cache_service": redis_status}


@app.post("/search", summary="Search Property Listings", tags=["Listings"])
async def search_listings(payload: Dict[Any, Any]):
    logger.info(f"Received search payload: {payload}")

    # --- Cache Logic ---
    cache_key = f"search:{json.dumps(payload, sort_keys=True)}" # Create a stable cache key
    redis_c = get_redis_client()
    cached_result = None

    if redis_c:
        try:
            cached_data_bytes = redis_c.get(cache_key)
            if cached_data_bytes:
                cached_result = json.loads(cached_data_bytes.decode('utf-8')) # Decode bytes then parse JSON
                logger.info(f"Cache HIT for key: {cache_key}")
                return cached_result
            else:
                logger.info(f"Cache MISS for key: {cache_key}")
        except redis.exceptions.RedisError as e:
            logger.error(f"Redis GET error for key {cache_key}: {e}. Proceeding without cache.")
        except json.JSONDecodeError as e:
             logger.error(f"Error decoding cached JSON for key {cache_key}: {e}. Invalidating cache entry.")
             try: redis_c.delete(cache_key)
             except Exception: pass # Ignore delete error if redis is down

    # --- Placeholder: Actual data fetching logic would be here ---
    # This part would query Elasticsearch/PostgreSQL based on the payload.
    # For now, we simulate a database response.
    logger.info("Simulating database/Elasticsearch query as it's a placeholder.")
    simulated_results = {
        "message": "Search results (simulated - from source, not cache). Full functionality pending.",
        "query_received": payload,
        "results": [
            {"id": 1, "title": "Sample Property 1 from DB", "price_usd": 250000},
            {"id": 2, "title": "Another Sample Property from DB", "price_usd": 350000},
        ],
        "total": 2,
        "page": payload.get("page", 1),
        "page_size": payload.get("page_size", 10)
    }
    # --- End Placeholder ---

    if redis_c:
        try:
            # Serialize the actual result to JSON string before storing in Redis
            result_to_cache_json = json.dumps(simulated_results)
            redis_c.setex(cache_key, CACHE_EXPIRATION_SECONDS, result_to_cache_json.encode('utf-8')) # Encode to bytes
            logger.info(f"Result for key {cache_key} stored in cache. TTL: {CACHE_EXPIRATION_SECONDS}s")
        except redis.exceptions.RedisError as e:
            logger.error(f"Redis SETEX error for key {cache_key}: {e}. Result not cached.")
        except TypeError as e: # Handles issues if simulated_results is not JSON serializable
            logger.error(f"Could not serialize results for caching. Key: {cache_key}. Error: {e}")


    return simulated_results
