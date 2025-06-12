from temporalio import workflow, exceptions
from datetime import timedelta
from typing import Dict, Any, List

# Import activity stubs
with workflow.unsafe.imports_passed_through():
    from config_loader_activity import load_config_file, get_test_suite_config
    from execution_activities import trigger_test_suite_activity # New activity

@workflow.defn
class ConfigReaderWorkflow:
    @workflow.run
    async def run(self, config_name: str) -> List[Dict[str, Any]]:
        workflow.logger.info(f"Workflow started to read config: {config_name}")
        return await workflow.execute_activity(
            load_config_file,
            config_name,
            start_to_close_timeout=timedelta(seconds=10),
        )

@workflow.defn
class TestSuiteConfigWorkflow:
    @workflow.run
    async def run(self, suite_id: str) -> Dict[str, Any]:
        workflow.logger.info(f"Workflow started to get test suite config for: {suite_id}")
        return await workflow.execute_activity(
            get_test_suite_config,
            suite_id,
            start_to_close_timeout=timedelta(seconds=10),
        )

@workflow.defn
class ExecuteTestSuiteWorkflow:
    @workflow.run
    async def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        suite_id = params["suite_id"]
        worker_config = params["worker_config"]
        user_inputs = params["user_inputs"]
        triggered_by = params.get("triggered_by", {"username": "unknown"})

        workflow.logger.info(
            f"ExecuteTestSuiteWorkflow started for suite_id: {suite_id} "
            f"by user: {triggered_by.get('username')}"
        )

        # Basic retry policy for the activity
        retry_policy = exceptions.RetryPolicy(
            initial_interval=timedelta(seconds=10),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(minutes=1),
            maximum_attempts=3, # Attempt 3 times in total
            non_retryable_error_types=["ConfigError", "SecretNotFoundError", "ResolutionError", "HttpError"] # Don't retry these
        )

        try:
            result = await workflow.execute_activity(
                trigger_test_suite_activity,
                args=[suite_id, worker_config, user_inputs],
                start_to_close_timeout=timedelta(minutes=5), # Timeout for the activity execution
                retry_policy=retry_policy
            )
            workflow.logger.info(f"Test suite {suite_id} triggered successfully. Result: {result.get('status_code')}")
            return {
                "status": "SUCCESS",
                "suite_id": suite_id,
                "message": result.get("message"),
                "details": result # Contains status_code and response_body from activity
            }
        except exceptions.ActivityError as e:
            workflow.logger.error(f"Activity failed for test suite {suite_id}: {e.cause}")
            error_type = "ActivityError"
            error_message = str(e.cause)
            # If the cause is an ApplicationError from the activity, extract its type and message
            if hasattr(e, 'cause') and hasattr(e.cause, 'type') and hasattr(e.cause, 'message'):
                 # Check if e.cause is an instance of ApplicationError if possible,
                 # but hasattr is a simpler check if direct type comparison is tricky due to how Temporal wraps errors
                if hasattr(e.cause, 'non_retryable') and e.cause.non_retryable: # Check if it's ApplicationError like
                    error_type = e.cause.type if e.cause.type else "ApplicationError" # Use type from ApplicationError
                    error_message = str(e.cause.message) if e.cause.message else str(e.cause)


            return {
                "status": "FAILED",
                "suite_id": suite_id,
                "error_type": error_type,
                "message": f"Failed to trigger test suite {suite_id}: {error_message}",
                "details_str": str(e.cause) # String representation of the underlying error
            }
        except Exception as e: # Catch other workflow-level errors
            workflow.logger.error(f"Workflow failed for test suite {suite_id}: {e}")
            return {
                "status": "FAILED",
                "suite_id": suite_id,
                "error_type": "WorkflowError",
                "message": f"Workflow execution error for {suite_id}: {str(e)}",
            }
