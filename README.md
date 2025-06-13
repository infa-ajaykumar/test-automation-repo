# Test Orchestration Platform - Full Stack

A comprehensive full-stack test orchestration platform using Temporal as the backend workflow orchestrator. It features dynamic test automation inputs via a plugin-like configuration architecture, secure authentication, role-based access control, a responsive UI, and scheduling capabilities.

## Table of Contents

- [Features](#features)
- [Project Structure](#project-structure)
- [Core Technologies](#core-technologies)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Local Development Setup](#local-development-setup)
- [Usage](#usage)
- [Configuration Management](#configuration-management)
- [Plugin Architecture](#plugin-architecture)
- [Deployment](#deployment)
- [Testing Strategy](#testing-strategy)
- [Security Considerations](#security-considerations)
- [Codebase Generation Script](#codebase-generation-script)
- [Contributing](#contributing)
- [License](#license)

## Features

-   **Dynamic Test Input Forms**: Frontend UI dynamically renders input forms for test suites based on YAML configurations.
-   **Plugin-like Extensibility**: Add or update test automation entries (products, suites, inputs, execution details) by modifying version-controlled YAML/JSON config files in `config/`.
-   **Temporal Workflow Orchestration**: Leverages Temporal for robust management and execution of test suites.
-   **User Authentication & RBAC**: Secure signup, login, and role-based access control (admin, editor, viewer) for features and data.
-   **Scheduling**: UI and API for creating, listing, and deleting cron-based schedules for test suite executions.
-   **Execution Monitoring**: Dashboard to view historical and live test executions, statuses, and event history.
-   **Notifications**: Configurable notifications (Email, Microsoft Teams, Opsgenie) on test success or failure.
-   **Cloud-Agnostic Design**: Containerized components (Frontend, Backend, Worker) for flexible deployment on any cloud or on-premises environment.

## Project Structure

-   `frontend/`: React + TypeScript single-page application.
-   `backend/`: FastAPI application providing the REST API.
-   `worker/`: Temporal worker (Python) implementing workflows and activities.
-   `config/`: YAML files defining products, test suites, environments, etc.
-   `docker-compose.yml`: For local development setup of all services including Temporal.
-   `DEPLOYMENT.MD`: Detailed deployment instructions.
-   `generate_project_structure.sh`: Script to scaffold the basic project layout.

See individual README files in each component directory for more details:
-   [Frontend README](./frontend/README.md)
-   [Backend README](./backend/README.md)
-   [Worker README](./worker/README.md)
-   [Config README](./config/README.md)

## Core Technologies

-   **Frontend**: React, TypeScript, Axios, React Router
-   **Backend**: FastAPI (Python), Pydantic, JWT, Passlib
-   **Worker**: Temporal Python SDK, HTTPX, PyYAML
-   **Workflow Engine**: Temporal
-   **Containerization**: Docker, Docker Compose
-   **Configuration**: YAML

## Getting Started

### Prerequisites
-   Docker and Docker Compose (or a container runtime like Podman)
-   Node.js (v18+) and yarn/npm (for direct frontend development)
-   Python (v3.10+) (for direct backend/worker development)
-   Git

### Local Development Setup
1.  **Clone the repository**:
    ```bash
    git clone <repository-url>
    cd <repository-name>
    ```
2.  **Environment Variables**:
    - Create `.env` files based on `.env.example` (if provided) or set environment variables as described in `docker-compose.yml` and component READMEs for secrets like `APP_SECRET_KEY`, SMTP settings, notification service keys, and any keys required by your `test_suites.yaml` `credential_keys`.
    - For the `docker-compose` setup, you can create a `.env` file in the project root, and Docker Compose will automatically load it. Example `.env` content:
      ```env
      # In project root .env file (example)
      APP_SECRET_KEY=a_very_strong_random_secret_for_local_dev
      # SMTP for MailHog via docker-compose
      SMTP_HOST=mailhog
      SMTP_PORT=1025
      SMTP_SENDER_EMAIL=noreply@example.com
      # Other worker secrets (Teams, Opsgenie, test suite credentials)
      # E.g., MY_JENKINS_TOKEN_ENV_VAR=some_token_value
      ```
3.  **Run with Docker Compose (Recommended for full stack)**:
    This will build images and start all services (Frontend, Backend, Worker, Temporal Server, MailHog).
    ```bash
    docker-compose up --build -d
    ```
    -   Frontend will be available at: `http://localhost:3000`
    -   Backend API docs at: `http://localhost:8000/docs`
    -   Temporal Web UI at: `http://localhost:8233`
    -   MailHog UI (for viewing emails sent by worker) at: `http://localhost:8025`

4.  **Initial Login**:
    -   The backend creates a default admin user:
        -   Username: `admin`
        -   Password: `adminpassword`
    -   You can register new users via the frontend UI.

For individual component setup, see their respective READMEs.

## Usage
- Access the frontend at `http://localhost:3000`.
- Register a new user or log in with the default admin credentials.
- Navigate through the dashboard to execute tests, view execution history, and manage schedules.
- Configure test suites by modifying YAML files in the `config/` directory (requires backend/worker restart if not using Docker volume mounts that allow live config reload, or if configs are baked into images).

## Configuration Management
The system's dynamic behavior (available products, test suites, their input parameters, execution details, notification rules) is primarily driven by YAML files in the `config/` directory. See `config/README.md` for details on their structure.

## Plugin Architecture
Adding new test suites or modifying existing ones primarily involves changes to the `config/` YAML files. This allows for extending the platform's capabilities with minimal code changes to the core application components.

## Deployment
Refer to [DEPLOYMENT.MD](./DEPLOYMENT.MD) for detailed instructions on building images and deploying the application to various environments (Docker Compose, Kubernetes, Cloud Services).

## Testing Strategy

A comprehensive testing strategy is crucial for maintaining the quality and reliability of this platform. The following types of tests are recommended:

### Unit Tests
-   **Backend (`backend/`)**:
    -   Test Pydantic model validators (e.g., `ScheduleCreateRequest`).
    -   Test authentication logic helpers and any custom business logic in API endpoints.
    -   Test configuration loading helpers (e.g., `get_suite_config_sync`).
-   **Worker (`worker/`)**:
    -   Thoroughly test dynamic value resolvers: `_resolve_value`, `_resolve_dict_placeholders` (for URL/payload templating), and `_resolve_notification_template`.
    -   Test individual activity logic if it involves complex processing beyond external calls (mocking the external calls).
-   **Frontend (`frontend/`)**:
    -   Use Jest and React Testing Library to test critical components like `DynamicForm.tsx` (form rendering, state changes, dropdown logic), `TestSuiteSelector.tsx`, and `AuthContext.tsx`.

### Integration Tests
-   **Backend API Endpoints**:
    -   Use `pytest` with `httpx` or FastAPI's `TestClient`.
    -   Verify authentication (JWT) and RBAC on all protected endpoints.
    -   Test CRUD operations for users and schedules.
    -   Test the workflow start endpoint (`/api/v1/workflows/test-suites/start`) by mocking the `TemporalClient.start_workflow` call to ensure correct parameter passing and input validation.
    -   Test config fetching and execution history/details endpoints (mocking Temporal client list/describe calls).
-   **Temporal Worker Activities**:
    -   `trigger_test_suite_activity`: Test with a mock HTTP server (e.g., `pytest-httpx`) to simulate responses from target test systems.
    -   Notification activities: Test with mock SMTP servers or mock HTTP servers for Teams/Opsgenie.
    -   The existing `backend/test_temporal_workflows.py` serves as an example for backend-to-worker workflow integration testing.

### End-to-End (E2E) Tests
-   Use tools like Cypress or Playwright for frontend E2E testing.
-   Key Scenarios:
    1.  User registration and login flow.
    2.  Selecting a product/test suite, filling the dynamic form, and successfully starting a test execution.
    3.  Viewing execution lists, details, and history.
    4.  Creating, viewing, and deleting a schedule.
    5.  Verifying RBAC by attempting to access restricted areas/actions with different user roles.
-   E2E tests require the full application stack to be running (Docker Compose is ideal for this).

## Security Considerations
Please refer to the "Security Considerations" section in [DEPLOYMENT.MD](./DEPLOYMENT.MD) for crucial information on securing your deployment. This includes secrets management, HTTPS/TLS, input validation, dependency scanning, and more.

## Codebase Generation Script
A shell script `generate_project_structure.sh` is provided in the root directory. This script can be used to quickly scaffold the basic directory layout and placeholder files for the project.
```bash
bash generate_project_structure.sh
```
This script is intended for initial setup or for understanding the project layout. It creates placeholders and will overwrite existing files if not handled carefully (though it has some checks for `DEPLOYMENT.MD` and `docker-compose.yml`).

## Contributing
(Placeholder for contribution guidelines)

## License
(Placeholder for license information, e.g., MIT, Apache 2.0)
