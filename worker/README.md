# Temporal Worker

This directory contains the Temporal worker for the Test Orchestration platform.

## Prerequisites

- Python 3.8+
- Temporal Server running (e.g., `temporal server start-dev` or a Docker setup)

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
3.  Run the worker:
    ```bash
    python run_worker.py
    ```
    The worker will connect to the Temporal server (default: `localhost:7233`) and start polling for tasks on `my-task-queue`.

## Workflows & Activities

-   **`ConfigReaderWorkflow`**: A simple workflow that executes an activity to load a specified configuration file from the `../config` directory.
-   **`TestSuiteConfigWorkflow`**: A workflow that executes an activity to load the `test_suites.yaml` file and retrieve the configuration for a specific test suite ID.
-   **Activities**:
    -   `load_config_file`: Loads and parses a YAML file from `../config`.
    -   `get_test_suite_config`: Finds a specific test suite's configuration.
