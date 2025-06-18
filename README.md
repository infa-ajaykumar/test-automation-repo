# Cloud Status Monitor

## Project Description

This Python automation script monitors the status pages of configured cloud and service providers for incidents. When an incident is detected affecting a specific service or region, it can trigger predefined test suites.

**Core Features:**
- Periodically checks status URLs for new or updated incident reports.
- Parses status information (currently implemented for AWS via its RSS feed).
- Identifies new vs. ongoing incidents to avoid redundant actions.
- Extracts incident details: title, affected region, status, timestamp.
- Loads a configurable JSON mapping file (`config/service_map.json`) to link services/regions to test scripts.
- Triggers corresponding test suites using `subprocess`.
- Configurable monitoring interval and settings via `config/settings.ini`.

**NOTE on Environment Stability:** During development, the execution environment exhibited instability, particularly with Python's `logging` module and sometimes with basic script execution (`monitor.py`). The logging and notification features were skipped due to these unresolved environment timeouts. The script's components have been tested individually where possible. Full integration testing of the main loop was hindered.

## Setup Instructions

### Prerequisites
- Python 3.7+
- `pip` for installing dependencies

### Installation
1.  **Clone the repository (if applicable) or download the files.**
2.  **Navigate to the project directory:**
    ```bash
    cd path/to/cloud_status_monitor
    ```
3.  **Create a virtual environment (recommended):**
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```
4.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    The `requirements.txt` file includes:
    ```
    requests
    beautifulsoup4
    lxml
    ```
    *(lxml was added during parser development for XML parsing of RSS feeds)*

## Configuration

Configuration is split into two main files located in the `config/` directory:

### 1. Settings (`config/settings.ini`)
This file controls the monitor's operational parameters.
```ini
[monitor]
interval_seconds = 300
mapping_file_path = config/service_map.json
log_file = cloud_monitor.log
log_level = INFO
```
-   `interval_seconds`: How often (in seconds) the monitor checks for status updates.
-   `mapping_file_path`: Path to the service-to-test mapping JSON file.
-   `log_file`: Path to the log file (Logging feature was attempted but skipped due to environment issues).
-   `log_level`: Desired log level (e.g., INFO, DEBUG) (Logging feature was attempted but skipped).

### 2. Service-to-Test Mapping (`config/service_map.json`)
This JSON file maps cloud providers, their regions, or specific services to corresponding test scripts. Test script paths are relative to the project root directory (`cloud_status_monitor/`).

Example structure:
```json
{
  "AWS": {
    "us-east-1": "tests/aws_us_east_1_tests.py",
    "eu-west-1": "tests/aws_eu_west_1_tests.py",
    "global": "tests/aws_global_tests.py"
  },
  "Azure": {
    "eastus": "tests/azure_eastus_tests.py"
  }
  // ... other providers
}
```
-   **Top-level keys**: Service provider names (e.g., "AWS", "Azure"). These should match the keys used in `SERVICE_PARSERS` in `monitor.py` and the `service` field in incident data.
-   **Nested keys**: Region names or specific service identifiers (e.g., "us-east-1", "platform").
    -   The special region key `"global"` can be used as a fallback if a more specific region from an incident is not found in the map for that service.
-   **Values**: Paths to the test scripts to be executed.

## Running the Monitor

Assuming you are in the project's root directory (`cloud_status_monitor/`) and the virtual environment is activated:

```bash
python3 monitor.py
```

The script will:
1.  Load settings and the service map.
2.  Enter a loop, periodically checking configured service status pages.
3.  If a new or updated incident is detected and mapped to a test script, it will execute the script.
4.  (Logging and notifications were planned but are not fully functional due to environment issues noted above). Output will currently be to standard out/err.

To stop the monitor, press `Ctrl+C`.

## Adding New Services or Updating Mappings

### 1. Updating Test Mappings
-   Modify `config/service_map.json` to add new entries or change existing test script paths.
-   Ensure the test scripts exist at the specified paths. You can create new Python test scripts in the `tests/` directory (or elsewhere, and adjust the path). Test scripts should be executable and typically exit with code 0 for success and non-zero for failure.

### 2. Adding a New Service Provider to Monitor
This is more involved and requires code changes:

1.  **Create a Parser Function:**
    *   In `cloud_status_monitor/parsers.py`, add a new function (e.g., `parse_newprovider_status()`).
    *   This function needs to:
        *   Fetch data from the provider's status page URL (or API, or RSS feed).
        *   Parse the content to identify incidents.
        *   For each incident, return a dictionary with the standard structure:
            ```python
            {
                "id": "unique_incident_identifier", # (e.g., generated by generate_incident_id())
                "service": "NewProviderName",     # Must match the key you'll use in service_map.json
                "region": "affected_region",      # e.g., "us-west-2", "europe", "global"
                "title": "incident_title",
                "status_summary": "current_status", # e.g., "Investigating", "Resolved"
                "timestamp_utc": datetime_object_utc, # datetime.datetime object, UTC
                "url": "url_to_incident_details"
            }
            ```
    *   Add any new library dependencies to `requirements.txt` and reinstall (`pip install -r requirements.txt`).
    *   Refer to `parse_aws_status()` as an example (it uses an RSS feed).

2.  **Register the Parser:**
    *   In `cloud_status_monitor/monitor.py`, add your new service name and parser function to the `SERVICE_PARSERS` dictionary:
        ```python
        SERVICE_PARSERS = {
            "AWS": parse_aws_status,
            # ... other existing parsers ...
            "NewProviderName": parse_newprovider_status, # Your new entry
        }
        ```

3.  **Add Mapping to `service_map.json`:**
    *   Add an entry for `"NewProviderName"` in `config/service_map.json` with its regions and corresponding test scripts.

## Notes on Status Page Parsing

-   **AWS**: The current AWS parser uses the official AWS RSS feed (`https://status.aws.amazon.com/rss/all.rss`) because the main HTML status page (`https://status.aws.amazon.com/`) is heavily JavaScript-rendered and difficult to scrape reliably without tools like Selenium. RSS feeds or official status APIs are generally preferred.
-   **Fragility of HTML Scraping**: Status page HTML structures can change without notice, breaking parsers that rely on specific HTML tags or CSS selectors. If a provider offers an official status API or RSS/Atom feeds, these are generally more stable sources of information.
-   **Placeholders**: Parsers for Azure, GCP, Oracle, JFrog, Artifactory, and MongoDB are currently placeholders and will return no incidents. They need to be implemented.

```
