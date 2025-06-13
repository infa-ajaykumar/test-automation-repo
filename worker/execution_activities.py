from temporalio import activity, exceptions
import httpx
import os
import json
from typing import Dict, Any, Optional

# _resolve_value and _resolve_dict_placeholders helpers
def _resolve_value(template_value: Any, user_inputs: Dict[str, Any], suite_id: str, worker_config: Dict[str, Any]) -> Any:
    if not isinstance(template_value, str):
        return template_value # Not a string, return as-is

    # Resolve secrets using credential_keys mapping
    if template_value.startswith("{SECRET:") and template_value.endswith("}"):
        abstract_secret_key = template_value[8:-1] # e.g., JENKINS_TOKEN
        credential_keys_map = worker_config.get("credential_keys", {})
        env_var_name = credential_keys_map.get(abstract_secret_key)

        if not env_var_name:
            activity.logger.error(f"Abstract secret key '{abstract_secret_key}' not found in credential_keys for suite '{suite_id}'. Worker config credential_keys: {credential_keys_map}")
            raise exceptions.ApplicationError(
                f"Configuration error: Abstract secret key '{abstract_secret_key}' not mapped in credential_keys.",
                type="SecretConfigError"
            )

        secret_value = os.environ.get(env_var_name)
        if secret_value is None:
            activity.logger.error(f"Secret environment variable '{env_var_name}' (for key '{abstract_secret_key}') not found for suite '{suite_id}'.")
            raise exceptions.ApplicationError(
                f"Configuration error: Environment variable '{env_var_name}' for secret '{abstract_secret_key}' not found.",
                type="SecretNotFoundError"
            )
        activity.logger.info(f"Successfully resolved secret for key '{abstract_secret_key}' using env var '{env_var_name}'.")
        return secret_value

    # If not a secret, proceed with other placeholders
    resolved_string = template_value

    # Replace {suite_id} first - this is a fixed placeholder
    resolved_string = resolved_string.replace("{suite_id}", str(suite_id))

    # Replace placeholders from user_inputs
    for key, value in user_inputs.items():
        placeholder = f"{{{key}}}"
        resolved_string = resolved_string.replace(placeholder, str(value))

    return resolved_string


def _resolve_dict_placeholders(template_dict: Dict[str, Any], user_inputs: Dict[str, Any], suite_id: str, worker_config: Dict[str, Any]) -> Dict[str, Any]:
    resolved_dict = {}
    for key, value_template in template_dict.items():
        if isinstance(value_template, dict):
            resolved_dict[key] = _resolve_dict_placeholders(value_template, user_inputs, suite_id, worker_config)
        elif isinstance(value_template, list):
            resolved_list = []
            for item in value_template: # Iterate and resolve each item in the list
                resolved_list.append(_resolve_value(item, user_inputs, suite_id, worker_config))
            resolved_dict[key] = resolved_list
        else: # It's a primitive type, try to resolve it
            resolved_dict[key] = _resolve_value(value_template, user_inputs, suite_id, worker_config)
    return resolved_dict


@activity.defn
async def trigger_test_suite_activity(
    suite_id: str, worker_config: Dict[str, Any], user_inputs: Dict[str, Any]
) -> Dict[str, Any]:
    activity.logger.info(f"trigger_test_suite_activity started for suite_id: {suite_id}.")
    # Be cautious with logging full worker_config if it contains sensitive defaults not handled by credential_keys
    activity.logger.debug(f"Received worker_config (first level keys): {list(worker_config.keys())}")
    activity.logger.debug(f"Received user_inputs: {user_inputs}")

    target_url_template = worker_config.get("target_url_template")
    payload_template = worker_config.get("payload_template")
    http_method = worker_config.get("type", "http_post").upper()
    timeout_seconds = worker_config.get("timeout_seconds", 60.0) # Get timeout from config

    if not target_url_template:
        activity.logger.error("target_url_template missing in worker_config.")
        raise exceptions.ApplicationError("target_url_template missing in worker_config.", type="ConfigError")
    if not payload_template:
        activity.logger.error("payload_template missing in worker_config.")
        raise exceptions.ApplicationError("payload_template missing in worker_config.", type="ConfigError")
    if not isinstance(payload_template, dict): # Ensure payload_template is a dictionary
        activity.logger.error(f"payload_template must be a dictionary, got {type(payload_template)}.")
        raise exceptions.ApplicationError(f"payload_template must be a dictionary, got {type(payload_template)}.", type="ConfigError")


    try:
        activity.logger.info("Resolving target URL and payload...")
        target_url = _resolve_value(target_url_template, user_inputs, suite_id, worker_config)
        payload = _resolve_dict_placeholders(payload_template, user_inputs, suite_id, worker_config)
        activity.logger.info("URL and payload resolved.")
    except exceptions.ApplicationError as e: # Catch app errors from helpers (SecretConfigError, SecretNotFoundError)
        activity.logger.error(f"Application error during resolution: {e.message} (type: {e.type})")
        raise # Re-raise to be handled by workflow/retries as per its type
    except Exception as e:
        activity.logger.error(f"Unexpected error resolving URL or payload for suite '{suite_id}': {e}")
        raise exceptions.ApplicationError(f"Error resolving URL/payload: {str(e)}", type="ResolutionError")

    activity.logger.info(f"Executing {http_method} request to: {target_url}")

    masked_payload = {}
    credential_keys_map = worker_config.get("credential_keys", {})

    for k, v_template in payload_template.items(): # Iterate over original template to identify secrets
        v_resolved = payload.get(k) # Get the resolved value
        is_secret = False
        if isinstance(v_template, str) and v_template.startswith("{SECRET:"):
            abstract_key = v_template[8:-1]
            if abstract_key in credential_keys_map: # Check if the abstract key is in credential_keys
                 is_secret = True

        if is_secret and isinstance(v_resolved, str) and len(v_resolved) > 4:
            masked_payload[k] = v_resolved[:2] + '****' + v_resolved[-2:]
        elif is_secret: # Handle short secrets or non-string resolved secrets
            masked_payload[k] = "****"
        else:
            masked_payload[k] = v_resolved

    activity.logger.info(f"Payload (masked): {masked_payload}")

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        try:
            if http_method == "HTTP_POST":
                response = await client.post(target_url, json=payload)
            elif http_method == "HTTP_GET":
                response = await client.get(target_url, params=payload) # GET uses params
            else:
                activity.logger.error(f"Unsupported HTTP method: {http_method}")
                raise exceptions.ApplicationError(f"Unsupported HTTP method: {http_method}", type="ConfigError")

            activity.logger.info(f"Response status code for {suite_id}: {response.status_code}")
            response.raise_for_status()

            response_data = {}
            try:
                response_data = response.json()
                activity.logger.debug(f"Response JSON data for {suite_id}: {response_data}")
            except json.JSONDecodeError:
                response_data = {"raw_content": response.text}
                activity.logger.debug(f"Response raw text data for {suite_id} (first 500 chars): {response.text[:500]}")

            activity.logger.info(f"trigger_test_suite_activity for {suite_id} completed successfully.")
            return {
                "status_code": response.status_code,
                "response_body": response_data,
                "message": f"Successfully triggered test suite {suite_id}."
            }
        except httpx.HTTPStatusError as e:
            activity.logger.error(f"HTTP error for {suite_id}: Status {e.response.status_code}. Response: {e.response.text[:500]}")
            raise exceptions.ApplicationError(
                f"HTTP error: {e.response.status_code}. Response: {e.response.text[:200]}", # Truncate for error message
                type="HttpError",
                details={"status_code": e.response.status_code, "response": e.response.text[:500]} # More details for logs
            )
        except httpx.RequestError as e:
            activity.logger.error(f"Request error for {suite_id} ({target_url}): {e}")
            raise exceptions.ApplicationError(f"Request failed for {target_url}: {str(e)}", type="NetworkError")
