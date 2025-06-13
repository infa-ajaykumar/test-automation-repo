# Backend API

This directory contains the FastAPI backend for the Test Orchestration platform.

## Running Locally

1.  Make sure you have Python 3.8+ installed.
2.  Create a virtual environment:
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```
3.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
4.  Run the FastAPI server:
    ```bash
    uvicorn main:app --reload --port 8000
    ```
    The API will be available at `http://localhost:8000`. You can access the OpenAPI documentation at `http://localhost:8000/docs`.

## Authentication
The backend uses JWT-based authentication. The initial admin user is `admin` with password `adminpassword`. Other users can be registered via the `/users/register` endpoint.

Use the token obtained from `/token` as a Bearer token in the Authorization header for protected endpoints.

## Testing Temporal Integration

A script `test_temporal_workflows.py` is provided to test the connection to the Temporal server and the execution of basic configuration-reading workflows.

1.  Ensure your Temporal server is running (e.g., `temporal server start-dev`).
2.  Ensure the Temporal worker from the `worker` directory is running (`python ../worker/run_worker.py`).
3.  From the `backend` directory (with its virtual environment activated and `temporalio` installed):
    ```bash
    python test_temporal_workflows.py
    ```
This script will attempt to:
- Fetch the `products.yaml` content via `ConfigReaderWorkflow`.
- Attempt to fetch a non-existent configuration file to check error handling.
- Fetch the configuration for `suite_login` via `TestSuiteConfigWorkflow`.
- Attempt to fetch a non-existent test suite to check error handling.

## Security

- **JWT Secret Key**: The `APP_SECRET_KEY` environment variable **MUST** be set in production for secure JWT signing. See the main project README's "Security Considerations" section for more details.
- **HTTPS**: In production, run this FastAPI application behind a reverse proxy that handles TLS termination and enforces HTTPS.
- **Input Validation**: Pydantic models provide automatic request data validation. Ensure new endpoints also validate inputs thoroughly.
