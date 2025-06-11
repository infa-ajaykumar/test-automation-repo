from temporalio import activity
import os
import requests # Ensure requests is used
from dotenv import load_dotenv

from .config_loader import load_yaml_config

load_dotenv()

@activity.defn
async def load_config_activity(product: str, testsuite_type: str) -> dict:
    """
    Temporal activity to load test suite configuration from a YAML file.
    """
    activity.logger.info(f"Executing load_config_activity for product: {product}, testsuite_type: {testsuite_type}")
    try:
        config = load_yaml_config(product, testsuite_type)

        required_keys = ['target_url', 'http_method']
        for key in required_keys:
            if key not in config:
                raise ValueError(f"Missing required key '{key}' in configuration file for {product} - {testsuite_type}")

        config.setdefault('default_parameters', {})
        config.setdefault('credential_env_keys', {})

        return config
    except FileNotFoundError as e:
        activity.logger.error(f"Configuration file not found: {e}")
        raise ValueError(f"Configuration not found: {str(e)}") from e
    except ValueError as e:
        activity.logger.error(f"Invalid configuration: {e}")
        raise
    except Exception as e:
        activity.logger.error(f"Unexpected error in load_config_activity: {e}")
        raise

@activity.defn
async def execute_test_suite_activity(
    url: str,
    method: str,
    params: dict | None,
    resolved_credentials: dict | None # Changed from credential_keys to resolved_credentials
) -> dict:
    """
    Temporal activity to execute a test suite by making an HTTP request.
    'resolved_credentials' should be a dictionary of header names to their values.
    """
    activity.logger.info(f"Executing test suite: {method} to {url}")
    activity.logger.info(f"Parameters: {params}")
    activity.logger.info(f"Headers (credentials keys): {resolved_credentials.keys() if resolved_credentials else 'None'}")

    headers = resolved_credentials if resolved_credentials else {}
    headers.update({
        'Content-Type': 'application/json' # Default content type, can be overridden by resolved_credentials
    })

    try:
        request_method = method.upper()
        if request_method == 'POST':
            response = requests.post(url, json=params, headers=headers, timeout=300) # 5 min timeout
        elif request_method == 'GET':
            response = requests.get(url, params=params, headers=headers, timeout=300)
        else:
            activity.logger.error(f"Unsupported HTTP method: {request_method}")
            return {
                "status_code": 0,
                "response_body": None,
                "error": f"Unsupported HTTP method: {request_method}"
            }

        response_body = ""
        try:
            response_body = response.json()
        except requests.exceptions.JSONDecodeError:
            response_body = response.text

        if response.status_code >= 400:
            activity.logger.error(f"HTTP Error {response.status_code}: {response_body}")
            return {
                "status_code": response.status_code,
                "response_body": response_body,
                "error": f"HTTP Error {response.status_code}"
            }

        activity.logger.info(f"Successfully executed test suite. Status: {response.status_code}")
        return {
            "status_code": response.status_code,
            "response_body": response_body,
            "error": None
        }

    except requests.exceptions.RequestException as e:
        activity.logger.error(f"Request failed: {e}")
        return {
            "status_code": 0, # Or a specific error code like 503 for service unavailable
            "response_body": None,
            "error": f"Request failed: {str(e)}"
        }
    except Exception as e:
        activity.logger.error(f"An unexpected error occurred in execute_test_suite_activity: {e}")
        return {
            "status_code": 0,
            "response_body": None,
            "error": f"An unexpected error occurred: {str(e)}"
        }
