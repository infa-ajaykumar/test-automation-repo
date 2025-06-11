from temporalio import workflow, exceptions
from datetime import timedelta
import os # For accessing environment variables

# Import activity stubs
from .activities import load_config_activity, execute_test_suite_activity

# Pydantic model for input structure (can be shared or defined as needed)
# For this workflow, we'll assume the input 'input_data' is a dictionary
# similar to the TestInput model defined in the FastAPI backend.

@workflow.defn
class TestSuiteWorkflow:
    @workflow.run
    async def run(self, input_data: dict) -> dict:
        workflow.logger.info(f"Workflow '{workflow.info().workflow_id}' started with input: {input_data}")

        product = input_data.get("product")
        testsuite_type = input_data.get("testsuite_type")

        if not product or not testsuite_type:
            workflow.logger.error("Workflow failed: Missing 'product' or 'testsuite_type' in input_data.")
            return {"error": "Missing 'product' or 'testsuite_type' in input_data", "status_code": 400}

        try:
            # 1. Load configuration
            config = await workflow.execute_activity(
                load_config_activity,
                args=[product, testsuite_type],
                start_to_close_timeout=timedelta(seconds=30), # Increased timeout slightly
                # retry_policy ensures Temporal retries if activity fails (e.g. transient network issue)
                retry_policy=workflow.RetryPolicy(
                    maximum_attempts=3,
                    non_retryable_error_types=["ValueError"] # Don't retry if config is fundamentally invalid/not found
                )
            )
            workflow.logger.info(f"Configuration loaded: {config}")

            # 2. Resolve credentials from environment variables
            resolved_credentials = {}
            credential_env_keys = config.get("credential_env_keys", {})
            if not isinstance(credential_env_keys, dict):
                workflow.logger.warn("credential_env_keys is not a dictionary. Skipping credential resolution.")
                credential_env_keys = {}

            for header_name, env_var_key in credential_env_keys.items():
                env_var_value = os.getenv(env_var_key)
                if env_var_value:
                    resolved_credentials[header_name] = env_var_value
                else:
                    workflow.logger.warn(f"Environment variable '{env_var_key}' for credential '{header_name}' not found.")

            workflow.logger.info(f"Resolved credentials for headers: {list(resolved_credentials.keys())}")

            # 3. Prepare parameters for the test execution
            # Merge default_parameters from config with relevant input_data
            # For now, we pass all input_data along with default_parameters.
            # A more sophisticated merge could be done if needed.
            execution_params = config.get("default_parameters", {})
            # Add or override with specific user inputs if necessary.
            # For example, if pod or environment from input_data should be sent:
            if "pod" in input_data and input_data["pod"] is not None:
                 execution_params["pod"] = input_data["pod"]
            if "environment" in input_data:
                 execution_params["environment"] = input_data["environment"]
            # Add any other relevant fields from input_data to execution_params
            # execution_params.update(input_data) # Or a more selective update


            # 4. Execute the test suite
            result = await workflow.execute_activity(
                execute_test_suite_activity,
                args=[
                    config["target_url"],
                    config["http_method"],
                    execution_params, # Parameters for the HTTP request body/query
                    resolved_credentials  # Headers for authentication etc.
                ],
                start_to_close_timeout=timedelta(minutes=15), # Allow more time for actual test execution
                heartbeat_timeout=timedelta(minutes=2), # If activity sends heartbeats
                retry_policy=workflow.RetryPolicy(
                    maximum_attempts=2, # Retry once on failure
                    non_retryable_error_types=[] # Retry on all error types unless activity raises ApplicationError with non_retryable=True
                )
            )
            workflow.logger.info(f"Test suite execution activity completed. Result: {result}")
            return result

        except exceptions.ActivityError as e:
            workflow.logger.error(f"Activity failed: {e.cause}")
            # e.cause is the original exception from the activity
            # Return a structured error
            return {
                "error": f"Activity execution failed: {type(e.cause).__name__} - {str(e.cause)}",
                "details": str(e.cause),
                "status_code": 500 # Generic server-side error for activity failure
            }
        except Exception as e:
            workflow.logger.error(f"Workflow failed with an unexpected error: {e}")
            return {"error": f"Workflow error: {str(e)}", "status_code": 500}
