# Temporal Worker (Python)

This directory contains the Temporal worker for the Test Orchestration platform. It executes workflows and activities related to test suite execution, configuration loading, and notifications.

## Key Responsibilities
-   **Workflow Orchestration**: Hosts and runs Temporal workflows (`ExecuteTestSuiteWorkflow`, `ScheduledTestSuiteRunnerWorkflow`, etc.).
-   **Activity Execution**: Performs tasks defined as activities, such as:
    -   Loading configuration files (`config_loader_activity.py`).
    -   Triggering external test suites via HTTP calls (`execution_activities.py`).
    -   Sending notifications (email, Teams, Opsgenie) (`notification_activities.py`).
-   **Connecting to Temporal Server**: Polls a specific task queue (`my-task-queue`) for work.

## Tech Stack
-   **Temporal Python SDK**: For defining and running workflows and activities.
-   **HTTPX**: Asynchronous HTTP client used in activities to call external services.
-   **PyYAML**: For parsing YAML configuration files.

## Prerequisites for Running Locally or in Production
-   Python 3.10+
-   Access to a running Temporal Server instance.
-   All necessary environment variables must be set (see "Environment Variables" and "Security" sections).

## Running Locally (Standalone Development)

This is for developing the worker independently of the Docker Compose setup.

1.  **Navigate to the `worker` directory**:
    ```bash
    cd worker
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
    The worker requires several environment variables to function correctly, especially for its activities.
    -   `TEMPORAL_SERVER_ADDRESS`: Address of the Temporal server's gRPC frontend.
        ```bash
        export TEMPORAL_SERVER_ADDRESS="localhost:7233"
        ```
    -   **Notification Service Credentials**: Depending on which notification activities you intend to use (as configured in `test_suites.yaml`), set variables like:
        -   `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_SENDER_EMAIL`, `SMTP_USE_TLS`
        -   `TEAMS_WEBHOOK_YOUR_CHANNEL_ENV_VAR_NAME` (the name of the env var holding the webhook URL)
        -   `OPSGENIE_API_KEY_YOUR_SERVICE_ENV_VAR_NAME` (the name of the env var holding the API key)
        -   `OPSGENIE_API_URL` (optional, defaults to standard Opsgenie endpoint)
    -   **Activity-Specific Secrets**: Any environment variables referenced by `credential_keys` in your `config/test_suites.yaml` for the `trigger_test_suite_activity`. For example, if a suite has:
        ```yaml
        # In test_suites.yaml
        # ...
        worker_config:
          credential_keys:
            JENKINS_API_TOKEN: "CI_JENKINS_TOKEN"
        # ...
        ```
        You would need to set the environment variable `CI_JENKINS_TOKEN`:
        ```bash
        export CI_JENKINS_TOKEN="your_actual_jenkins_api_token_value"
        ```
    Refer to the main project README's "Security Considerations" and the `docker-compose.yml` for more examples.

5.  **Run the worker**:
    ```bash
    python run_worker.py
    ```
    The worker will connect to the Temporal server (default: `localhost:7233`) and start polling for tasks on `my-task-queue`.

## Workflows & Activities Overview
(This section was previously updated and is largely accurate, minor review for consistency)

### Workflows
-   **`ConfigReaderWorkflow`**: Loads a specified configuration file.
-   **`TestSuiteConfigWorkflow`**: Retrieves a specific test suite's configuration.
-   **`ExecuteTestSuiteWorkflow`**: Orchestrates a single test suite execution, including triggering and notifications. Retry policies and activity timeouts are configurable via `worker_config` in `test_suites.yaml`.
-   **`ScheduledTestSuiteRunnerWorkflow`**: Designed for cron-based execution, starts `ExecuteTestSuiteWorkflow` as a child.
-   **`SendNotificationChildWorkflow`**: Child workflow for isolated sending of individual notifications.

### Activities
-   **`load_config_file`, `get_test_suite_config`**: Configuration loading.
-   **`trigger_test_suite_activity`**: Makes HTTP requests to trigger tests, resolving placeholders and secrets.
-   **`send_email_notification_activity`**, **`send_teams_notification_activity`**, **`send_opsgenie_notification_activity`**: Send notifications via respective channels.

## Testing Strategy Notes
- **Unit Tests**: Use `pytest`.
    - Test activity logic thoroughly, especially the dynamic placeholder/secret resolvers (`_resolve_value`, `_resolve_dict_placeholders`, `_resolve_notification_template`). Mock external calls (HTTP, SMTP) using libraries like `pytest-httpx` or `unittest.mock`.
    - Test any complex decision logic within workflows by mocking activity execution results.
- **Integration Tests**:
    - Test activities that interact with external services against mock servers or sandboxed environments if possible.
    - For workflows, use the Temporal test server (`temporaltest`) or a local Temporal server to run workflow tests and verify that activities are called as expected and that workflows react correctly to different activity outcomes (success, failure, timeout).

Refer to the main project README's "Testing Strategy" section for a more comprehensive overview.

## Security
- **Secrets Management**: This worker relies heavily on environment variables for all secrets (SMTP credentials, API keys, webhook URLs, test system credentials via `credential_keys`). These **MUST** be set securely in your deployment environment.
- **Never hardcode secrets.** Refer to the main project README and your `test_suites.yaml` to identify all required environment variables.

This README provides a guide for understanding, running, and developing the Temporal worker component.
