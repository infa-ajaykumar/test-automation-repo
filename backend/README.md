# Backend API Service (Python/FastAPI)

This service provides a RESTful API for searching and retrieving processed property listings.

## Functionality

- Exposes API endpoints to query the aggregated property data.
- Connects to PostgreSQL for structured data and Elasticsearch for search queries (once data storage in `data_processing_service` is functional).
- Implements caching using Redis to improve response times for frequent queries.

## Key Endpoints

- `GET /health`: Health check for the API and its connections to database, Elasticsearch, and Redis.
- `GET /docs`: Interactive API documentation (Swagger UI).
- `GET /openapi.json`: OpenAPI schema.
- `POST /search`: Endpoint for searching listings. (Currently returns mocked/placeholder data as the data pipeline is not fully storing data yet).

## Configuration

Key environment variables (set in `docker-compose.yml`):
- `DATABASE_URL`: PostgreSQL connection string.
- `ELASTICSEARCH_HOST`, `ELASTICSEARCH_PORT`, `ELASTICSEARCH_INDEX_NAME`: For Elasticsearch connection.
- `REDIS_HOST`, `REDIS_PORT`: For Redis connection.

## Running

This service starts automatically as part of `docker-compose up`. The API will be available at `http://localhost:8000`.

To view logs:
```bash
docker-compose logs -f backend_api_service
```

## Testing
Basic API tests can be run using Pytest. Ensure you have `pytest` and `httpx` in `requirements.txt`.
To run tests (assuming they are in `test_api.py`):
```bash
# From the project root, while other services (DB, ES, Redis) are running for integration aspects of health check
docker-compose run --rm backend_api_service pytest test_api.py
# Or, for more isolated unit tests that mock external services:
# (cd backend && pytest test_api.py) # If dependencies are managed locally for testing
```
