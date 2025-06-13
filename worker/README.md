# Temporal Worker

This directory contains the Temporal worker for the Test Orchestration platform.

## Prerequisites

- Python 3.8+
- Temporal Server running (e.g., `temporal server start-dev` or a Docker setup)
- Required environment variables set for any configured notification services or secret-dependent activities (see Security section).

## Running Locally

1.  Create a virtual environment:
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3.  Ensure any necessary environment variables for notifications or activities are set (e.g., `SMTP_HOST`, `OPSGENIE_API_KEY_YOUR_SERVICE`, etc.).
4.  Run the worker:
    ```bash
    python run_worker.py
    ```
    The worker will connect to the Temporal server (default: `localhost:7233`) and start polling for tasks on `my-task-queue`.

## Workflows & Activities

### Workflows
-   **`ConfigReaderWorkflow`**: Loads a specified configuration file from `../config`.
-   **`TestSuiteConfigWorkflow`**: Retrieves the configuration for a specific test suite ID from `test_suites.yaml`.
-   **`ExecuteTestSuiteWorkflow`**:
    -   Orchestrates the execution of a single test suite.
    -   Takes `suite_id`, `worker_config` (from the suite's definition), and `user_inputs`.
    -   Calls `trigger_test_suite_activity` to perform the actual test execution (e.g., HTTP POST).
    -   Handles notifications based on success or failure as defined in the suite's `worker_config.notifications`.
-   **`ScheduledTestSuiteRunnerWorkflow`**:
    -   Designed to be run on a cron schedule by Temporal.
    -   Receives pre-configured parameters (`suite_id`, `worker_config`, `user_inputs`, `schedule_name`).
    -   For each cron invocation, it starts an `ExecuteTestSuiteWorkflow` as a child workflow.
-   **`SendNotificationChildWorkflow`**:
    -   A child workflow responsible for sending a single notification (email, Teams, Opsgenie).
    -   Called by `ExecuteTestSuiteWorkflow` to isolate notification logic and retries.

### Activities
-   **`load_config_file`**: Loads and parses a YAML file from `../config`.
-   **`get_test_suite_config`**: Finds a specific test suite's configuration from `test_suites.yaml`.
-   **`trigger_test_suite_activity`**:
    -   Makes HTTP requests (typically POST) to external systems to trigger test suites.
    -   Resolves placeholders in URLs and payloads, including secrets from environment variables (mapped via `credential_keys` in `worker_config`).
-   **`send_email_notification_activity`**: Sends email notifications. SMTP server details are read from environment variables.
-   **`send_teams_notification_activity`**: Sends notifications to Microsoft Teams. The webhook URL is read from an environment variable.
-   **`send_opsgenie_notification_activity`**: Creates alerts in Opsgenie. The API key is read from an environment variable.

## Security

- **Secrets Management**: This worker requires various secrets for its operations (e.g., SMTP credentials, notification service API keys/webhooks, secrets for `trigger_test_suite_activity` via `credential_keys` in test suite configs). These **MUST** be provided as environment variables in your deployment environment. Consult the main project README's "Security Considerations" section and your `test_suites.yaml` configurations to determine all required environment variables.
- **Never hardcode secrets.** Use secure environment variable injection methods. Review `config/test_suites.yaml` for `credential_keys` in `worker_config` sections and `notifications` sections to identify what environment variables need to be set for the activities used by your test suites. For example, if a `payload_template` uses `{SECRET:MY_API_TOKEN}` and `credential_keys` maps `MY_API_TOKEN` to `ACTUAL_ENV_VAR_FOR_TOKEN`, then `ACTUAL_ENV_VAR_FOR_TOKEN` must be set in the worker's environment. Similarly for notification activities (e.g., `SMTP_HOST`, `TEAMS_WEBHOOK_MYTEAM`, `OPSGENIE_API_KEY_DEFAULT`).
