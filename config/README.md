# Configuration Directory (`config/`)

This directory contains YAML files that define the dynamic aspects of the Test Orchestration Platform. These configurations drive what products and test suites are available, how their input forms are rendered, how tests are executed, and how notifications are handled.

Modifying these files is the primary way to customize and extend the test suites available in the platform without changing the core application code.

## Core Configuration Files

1.  **`csps.yaml`**:
    -   Defines a list of Cloud Service Providers (CSPs).
    -   Used to populate dropdowns in the UI where a CSP selection is required.
    -   Each entry typically has an `id` and `name`.
    -   Example: `aws`, `azure`, `gcp`.

2.  **`regions.yaml`**:
    -   Defines a list of regions, often associated with a CSP.
    -   Used to populate region selection dropdowns, potentially filtered by a selected CSP (using `depends_on` in `test_suites.yaml` input definitions).
    -   Each entry typically has `id`, `name`, and `csp` (linking to an ID from `csps.yaml`).

3.  **`environments.yaml`**:
    -   Defines a list of deployment or testing environments (e.g., dev, staging, prod).
    -   Used to populate environment selection dropdowns.
    -   Each entry typically has an `id` and `name`.

4.  **`products.yaml`**:
    -   Defines the products or services that have test suites.
    -   Each product entry has an `id`, `name`, `description`, and a list of associated `test_suites` (by their IDs from `test_suites.yaml`).
    -   This structure helps organize test suites by product in the UI.

5.  **`test_suites.yaml`**:
    -   This is a crucial file defining individual test suites. Each test suite entry is an object that can contain:
        -   `id`: Unique identifier for the test suite.
        -   `name`: Human-readable name.
        -   `description`: Detailed description of what the test suite does.
        -   `product_ids`: (Optional) A list of product IDs this suite belongs to, for filtering or association.
        -   `inputs`: An array defining the input fields for the dynamic form in the UI. Each input object specifies:
            -   `name`: The internal variable name for the input.
            -   `label`: The display label for the form field.
            -   `type`: Input type (e.g., `text`, `dropdown`, `number`, `checkbox`).
            -   `required`: Boolean, if the field is mandatory.
            -   `default_value`: A default value for the field.
            -   `source`: (For `dropdown` type) The name of another YAML file in this directory (e.g., "csps.yaml") from which to populate dropdown options. The items in the source file are expected to have `id` and `name` fields.
            -   `depends_on`: (For `dropdown` type) The `name` of another input field in the same form. This is used to filter options. For example, a 'region' dropdown might depend on a 'csp' dropdown, filtering regions based on the selected CSP. The source YAML for the dependent dropdown (e.g., `regions.yaml`) must contain items with a field corresponding to the `depends_on` field's name (e.g., if `depends_on: "csp"`, region items should have a `csp` field like `csp: "aws"`).
            -   `options`: (For `dropdown` type) An array of `{id: string, name: string}` objects for static dropdown options, used if `source` is not provided.
        -   `worker_config`: A dictionary specifying how the Temporal worker should execute this test suite. This is passed to the `ExecuteTestSuiteWorkflow` and then to `trigger_test_suite_activity`.
            -   `type`: Typically `http_post` (or `http_get`). Defines the method for `trigger_test_suite_activity`.
            -   `target_url_template`: The URL template for the HTTP request. Can contain placeholders like `{input_variable_name}` or `{suite_id}` which will be resolved from user inputs or suite context.
            -   `payload_template`: A dictionary defining the structure of the JSON payload for POST requests. Values can be placeholders like `{input_variable_name}` or `{SECRET:ABSTRACT_KEY}`.
            -   `credential_keys`: (Optional) A mapping of abstract secret names (used in `payload_template` as `{SECRET:ABSTRACT_KEY}`) to the actual environment variable names that the worker should use to retrieve the secret values. For example, `{"JENKINS_TOKEN": "WORKER_ENV_VAR_FOR_JENKINS_TOKEN"}`.
            -   `timeout_seconds`: (Optional) Timeout for the HTTP request in `trigger_test_suite_activity`. Defaults to 60.
            -   `retry_initial_interval_seconds`, `retry_backoff_coefficient`, `retry_maximum_interval_seconds`, `retry_maximum_attempts`: (Optional) Parameters to control the retry policy for the `trigger_test_suite_activity` within the `ExecuteTestSuiteWorkflow`.
            -   `notifications`: (Optional) An object to configure notifications.
                -   `on_success`: An array of notification configurations to send if the test suite execution is successful.
                -   `on_failure`: An array of notification configurations to send if the test suite execution fails.
                -   Each notification configuration object specifies:
                    -   `type`: `email`, `teams`, or `opsgenie`.
                    -   `recipients`: (For `email`) List of email addresses.
                    -   `subject_template`, `body_template`, `message_template`: Templates for notification content. Can use placeholders like `{suite_id}`, `{status}`, `{error_message}`, etc., which are resolved by the workflow.
                    -   `smtp_config_env_prefix`: (For `email`) Prefix for SMTP environment variables (e.g., "SMTP" for `SMTP_HOST`).
                    -   `webhook_env_var`: (For `teams`) Name of the environment variable holding the Teams webhook URL.
                    -   `api_key_env_var`: (For `opsgenie`) Name of the environment variable holding the Opsgenie API key.
                    -   `alias_template`, `priority`: (For `opsgenie`) Opsgenie alert fields.
        -   `schedule_options`: (Optional) Hints for UI regarding scheduling capabilities (e.g., `allow_manual`, `allow_periodic`).

## Management
-   **Updates**: Changes to these YAML files (when mounted into running containers or if containers are restarted after changes) will be reflected in the UI and worker behavior. If configurations are baked into Docker images, an image rebuild and redeployment are necessary.
-   **Validation**: The backend API performs basic validation when loading these files (e.g., ensuring `test_suites.yaml` is a list). The `ScheduleCreateRequest` model in the backend also validates `cron_string` and `schedule_id` formats.

## Testing Notes
-   When adding or modifying configurations, especially `test_suites.yaml`:
    -   Thoroughly test the dynamic form rendering in the frontend.
    -   Verify that placeholders in `target_url_template` and `payload_template` are correctly resolved by the worker.
    -   Ensure `credential_keys` correctly map to environment variables set in the worker's environment.
    -   Test notification configurations with appropriate mock setups or test channels/services.
-   Schema validation for these YAML files could be implemented using tools or libraries if more rigorous structure enforcement is needed beyond what the application's Pydantic models provide at load time.

This directory is central to the platform's "plugin" architecture for defining and managing test automation.
