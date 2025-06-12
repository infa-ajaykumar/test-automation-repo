from temporalio import activity, exceptions
import httpx # HTTP client
import os
import json # For payload processing if needed, though templates might be strings
from typing import Dict, Any, Optional

# Helper to resolve placeholders like {variable} or {SECRET:ENV_VAR_NAME}
def _resolve_value(template_value: Any, user_inputs: Dict[str, Any], suite_id: str) -> Any:
    if not isinstance(template_value, str):
        return template_value # Return as-is if not a string template

    # First, handle secrets: {SECRET:ENV_VAR_NAME_FROM_CONFIG}
    # The ENV_VAR_NAME_FROM_CONFIG is what's literally in the credential_keys map value.
    # E.g., if payload_template has "{SECRET:JENKINS_TOKEN}" and credential_keys has
    # "JENKINS_TOKEN": "ACTUAL_ENV_VAR_FOR_JENKINS_TOKEN", this resolves it.
    # This current implementation assumes credential_keys are ALREADY the env var names.
    # A more complex setup might use worker_config['credential_keys'] to map abstract names to env vars.
    # For simplicity, let's assume direct env var names are in {SECRET:...} for now.

    if template_value.startswith("{SECRET:") and template_value.endswith("}"):
        secret_key_name = template_value[8:-1] # Get ENV_VAR_NAME
        secret_value = os.environ.get(secret_key_name)
        if secret_value is None:
            activity.logger.error(f"Secret environment variable '{secret_key_name}' not found for suite '{suite_id}'.")
            # Raise an application error to indicate a configuration or environment issue
            raise exceptions.ApplicationError(
                f"Configuration error: Secret environment variable '{secret_key_name}' not found.",
                type="SecretNotFoundError"
            )
        return secret_value

    # Then, handle simple placeholders: {input_variable_name}
    # Replace placeholders from user_inputs
    resolved_string = template_value
    # Also add suite_id to available placeholders
    all_inputs = {**user_inputs, "suite_id": suite_id}

    for key, value in all_inputs.items():
        placeholder = f"{{{key}}}"
        # Ensure value is string if replacing into a string template part
        resolved_string = resolved_string.replace(placeholder, str(value))

    # Check if all placeholders were resolved (optional, for stricter validation)
    # if "{" in resolved_string and "}" in resolved_string:
    #     activity.logger.warning(f"Possible unresolved placeholders in '{resolved_string}' for suite '{suite_id}'.")

    return resolved_string


def _resolve_dict_placeholders(template_dict: Dict[str, Any], user_inputs: Dict[str, Any], suite_id: str) -> Dict[str, Any]:
    resolved_dict = {}
    for key, value_template in template_dict.items():
        if isinstance(value_template, dict):
            resolved_dict[key] = _resolve_dict_placeholders(value_template, user_inputs, suite_id)
        elif isinstance(value_template, list):
            resolved_dict[key] = [_resolve_value(item, user_inputs, suite_id) for item in value_template]
        else:
            resolved_dict[key] = _resolve_value(value_template, user_inputs, suite_id)
    return resolved_dict


@activity.defn
async def trigger_test_suite_activity(
    suite_id: str, worker_config: Dict[str, Any], user_inputs: Dict[str, Any]
) -> Dict[str, Any]:
    activity.logger.info(f"Starting activity for test suite: {suite_id}")
    activity.logger.info(f"Worker config: {worker_config}")
    activity.logger.info(f"User inputs: {user_inputs}")

    target_url_template = worker_config.get("target_url_template")
    payload_template = worker_config.get("payload_template") # This should be a dict
    http_method = worker_config.get("type", "http_post").upper() # Default to POST

    if not target_url_template:
        raise exceptions.ApplicationError("target_url_template missing in worker_config.", type="ConfigError")
    if not payload_template:
        raise exceptions.ApplicationError("payload_template missing in worker_config.", type="ConfigError")
    if not isinstance(payload_template, dict):
        raise exceptions.ApplicationError("payload_template must be a dictionary.", type="ConfigError")

    # Resolve URL and payload
    try:
        # Add suite_id to user_inputs for resolving, so {suite_id} can be used in templates
        # This was missing in the initial thought process for _resolve_value
        extended_user_inputs = {**user_inputs, "suite_id": suite_id}

        target_url = _resolve_value(target_url_template, extended_user_inputs, suite_id)
        payload = _resolve_dict_placeholders(payload_template, extended_user_inputs, suite_id)

    except exceptions.ApplicationError:
        raise
    except Exception as e:
        activity.logger.error(f"Error resolving URL or payload for suite '{suite_id}': {e}")
        raise exceptions.ApplicationError(f"Error resolving URL/payload: {str(e)}", type="ResolutionError")


    activity.logger.info(f"Executing {http_method} request to: {target_url}")

    masked_payload = payload.copy()
    for key, value in masked_payload.items():
        if isinstance(value, str) and ("TOKEN" in key.upper() or "API_KEY" in key.upper() or "SECRET" in key.upper()):
            if len(value) > 4:
                masked_payload[key] = value[:2] + '****' + value[-2:]
            else:
                masked_payload[key] = "****"
    activity.logger.info(f"Payload (masked): {masked_payload}")


    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            if http_method == "HTTP_POST":
                response = await client.post(target_url, json=payload)
            elif http_method == "HTTP_GET":
                response = await client.get(target_url, params=payload)
            else:
                raise exceptions.ApplicationError(f"Unsupported HTTP method: {http_method}", type="ConfigError")

            activity.logger.info(f"Response status code for {suite_id}: {response.status_code}")
            response.raise_for_status()

            response_data = {}
            try:
                response_data = response.json()
            except json.JSONDecodeError:
                response_data = {"raw_content": response.text}

            return {
                "status_code": response.status_code,
                "response_body": response_data,
                "message": f"Successfully triggered test suite {suite_id}."
            }

        except httpx.HTTPStatusError as e:
            activity.logger.error(f"HTTP error for {suite_id}: {e.response.status_code} - {e.response.text}")
            raise exceptions.ApplicationError(
                f"HTTP error: {e.response.status_code}. Response: {e.response.text[:200]}",
                type="HttpError",
                details={"status_code": e.response.status_code, "response": e.response.text[:200]}
            )
        except httpx.RequestError as e:
            activity.logger.error(f"Request error for {suite_id}: {e}")
            raise exceptions.ApplicationError(f"Request failed: {str(e)}", type="NetworkError")
