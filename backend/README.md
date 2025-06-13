# Backend API (FastAPI)

This directory contains the FastAPI backend for the Test Orchestration platform. It serves as the central API for the frontend, manages user authentication, interacts with Temporal for workflow orchestration, and serves configuration data.

## Key Features
- **User Management**: Registration, login (JWT-based), role management (admin, editor, viewer).
- **Configuration API**: Endpoints to serve YAML configurations from the `../config` directory (`/api/v1/configs/*`).
- **Temporal Interaction**:
    - Starts Temporal workflows for test suite execution (`/api/v1/workflows/test-suites/start`).
    - Queries Temporal for workflow execution history and details (`/api/v1/workflows/executions/*`).
    - Manages Temporal cron schedules for test suites (`/api/v1/schedules/*`).
- **RBAC**: Protects endpoints based on user roles.
- **Input Validation**: Uses Pydantic for request and response data validation.

## Tech Stack
- **FastAPI**: Modern, fast (high-performance) web framework for building APIs with Python.
- **Pydantic**: Data validation and settings management using Python type annotations.
- **JWT (PyJWT)**: For generating and verifying access tokens.
- **Passlib**: For password hashing (bcrypt).
- **Temporal Python SDK**: For client-side interaction with the Temporal server.

## Running Locally (Standalone Development)

This is for developing the backend independently of the Docker Compose setup. Ensure the Temporal server is running and accessible.

1.  **Navigate to the `backend` directory**:
    ```bash
    cd backend
    ```
2.  **Create and activate a virtual environment**:
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```
3.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
4.  **Set Environment Variables**:
    Key environment variables needed:
    -   `APP_SECRET_KEY`: A strong secret key for JWT signing. For local development, you can set it directly or it will use a default (with a warning).
        ```bash
        export APP_SECRET_KEY="your_local_dev_secret_key"
        ```
    -   `TEMPORAL_SERVER_ADDRESS`: Address of the Temporal server's gRPC frontend.
        ```bash
        export TEMPORAL_SERVER_ADDRESS="localhost:7233"
        ```
    Consider using a `.env` file with a library like `python-dotenv` if you prefer, though the current `main.py` loads `APP_SECRET_KEY` directly via `os.environ.get`.

5.  **Run the FastAPI server**:
    ```bash
    uvicorn main:app --reload --port 8000
    ```
    -   The API will be available at `http://localhost:8000`.
    -   OpenAPI (Swagger) documentation at `http://localhost:8000/docs`.
    -   ReDoc documentation at `http://localhost:8000/redoc`.

## API Endpoints Overview
(Refer to the OpenAPI documentation at `/docs` for a full, interactive list)
-   `/token`: User login, returns JWT.
-   `/users/register`: User registration.
-   `/users/me`, `/users`, `/users/{user_id}/roles`: User management.
-   `/api/v1/configs`, `/api/v1/configs/{config_name}`: Serve YAML configurations.
-   `/api/v1/workflows/test-suites/start`: Start a test suite execution workflow.
-   `/api/v1/workflows/executions/*`: List and view workflow execution details and history.
-   `/api/v1/schedules/*`: Create, list, and delete cron schedules for test suites.

## Configuration
The backend serves configurations from the `../config` directory. When running standalone, ensure this path is correct relative to where you run `uvicorn`. The Docker setup mounts this directory.

## Testing Temporal Integration
The `test_temporal_workflows.py` script can be used to perform basic tests of starting config-reading workflows via Temporal.
1.  Ensure Temporal server is running.
2.  Ensure the worker (from `../worker`) is running.
3.  From the `backend` directory (with venv activated):
    ```bash
    python test_temporal_workflows.py
    ```

## Testing Strategy Notes
- **Unit Tests**: Use `pytest`. Focus on testing Pydantic model validators (e.g., `ScheduleCreateRequest` validators), authentication helper functions, and any complex logic within endpoint functions (by mocking external calls like Temporal client interactions).
- **Integration Tests**: Use `pytest` with FastAPI's `TestClient` (or `httpx.AsyncClient`).
    - Test all API endpoints for correct responses, status codes, and error handling.
    - Verify JWT authentication and RBAC on protected routes.
    - Mock `temporalio.client.Client` methods to simulate interactions with Temporal without needing a live server for most tests (e.g., testing that `start_workflow` is called with correct parameters).
    - The `test_temporal_workflows.py` script provides a starting point for live Temporal integration tests.

Refer to the main project README's "Testing Strategy" section for a more comprehensive overview.

## Security
- **JWT Secret Key**: The `APP_SECRET_KEY` environment variable **MUST** be set to a strong, unique value in production.
- **HTTPS**: In production, deploy behind a reverse proxy (e.g., Nginx, Traefik) that handles TLS termination.
- **Input Validation**: Pydantic models provide automatic validation for request data. Ensure all new models and endpoints include thorough validation.
- See the main project README's "Security Considerations" section for more details.
