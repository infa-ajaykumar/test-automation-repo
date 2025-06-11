# Configuration Files

This directory stores YAML configuration files for different products and test suite types.
The Temporal worker's `load_config_activity` reads these files to determine how to trigger a test suite.

## Naming Convention

Files should be named in the format: `productname_testsuitetype.yaml`.
For example:
- `producta_functional.yaml`
- `anotherproduct_smoketest.yaml`

The `productname` and `testsuitetype` should match the values provided by the user in the frontend dashboard (converted to lowercase).

## Structure

Each YAML file should have the following structure:

```yaml
target_url: "string"  # REQUIRED: The URL of the test suite executor (e.g., Jenkins job, API endpoint)
http_method: "string" # REQUIRED: The HTTP method to use (e.g., "POST", "GET")

default_parameters: {}  # OPTIONAL: A dictionary of default parameters to send with the request.
                       # These can be static values needed for the test trigger.

credential_env_keys: {} # OPTIONAL: A dictionary mapping header names (or sometimes parameter names)
                       # to the names of environment variables. The workflow will resolve these
                       # environment variables to their actual values and include them in the
                       # HTTP request (typically as headers).
                       # Example:
                       #   Authorization: "MY_PRODUCT_AUTH_TOKEN_ENV_VAR"
                       #   X-Api-Key: "MY_PRODUCT_API_KEY_ENV_VAR"
```

### `target_url`
The full URL to which the HTTP request will be made.

### `http_method`
The HTTP method to use for the request, commonly "POST" or "GET".

### `default_parameters`
These are key-value pairs that will be sent as the JSON body for POST requests or as query parameters for GET requests by default. The workflow might add or override some of these based on user input if designed to do so.

### `credential_env_keys`
This is crucial for security. Instead of storing secrets directly in these config files, you store the *name* of the environment variable that holds the secret.
- The **key** in this dictionary is typically the HTTP Header name (e.g., `Authorization`, `X-API-Key`).
- The **value** is the name of the environment variable that the Temporal worker will read at runtime (e.g., `PRODUCT_A_AUTH_TOKEN`).

Make sure the corresponding environment variables are set in the environment where the Temporal worker is running (e.g., in its `.env` file or system environment).
