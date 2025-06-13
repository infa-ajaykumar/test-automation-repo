from temporalio import workflow, exceptions
from temporalio.common import CronSchedule # For CronSchedule definition
from datetime import timedelta
from typing import Dict, Any, List, Optional # Added Optional

with workflow.unsafe.imports_passed_through():
    from config_loader_activity import load_config_file, get_test_suite_config
    from execution_activities import trigger_test_suite_activity
    from notification_activities import ( # Import new notification activities
        send_email_notification_activity,
        send_teams_notification_activity,
        send_opsgenie_notification_activity,
        _resolve_notification_template # Import helper
    )

# ConfigReaderWorkflow and TestSuiteConfigWorkflow remain the same
@workflow.defn
class ConfigReaderWorkflow:
    @workflow.run
    async def run(self, config_name: str) -> List[Dict[str, Any]]:
        workflow.logger.info(f"Workflow started to read config: {config_name}")
        return await workflow.execute_activity(load_config_file, config_name, start_to_close_timeout=timedelta(seconds=10))

@workflow.defn
class TestSuiteConfigWorkflow:
    @workflow.run
    async def run(self, suite_id: str) -> Dict[str, Any]:
        workflow.logger.info(f"Workflow started to get test suite config for: {suite_id}")
        return await workflow.execute_activity(get_test_suite_config, suite_id, start_to_close_timeout=timedelta(seconds=10))


@workflow.defn
class ExecuteTestSuiteWorkflow:
    @workflow.run
    async def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        suite_id = params["suite_id"]
        worker_config = params["worker_config"]
        user_inputs = params["user_inputs"]
        triggered_by = params.get("triggered_by", {"username": "unknown", "type": "manual"})

        workflow_id = workflow.info().workflow_id
        run_id = workflow.info().run_id

        workflow.logger.info(f"ExecuteTestSuiteWorkflow {workflow_id} (RunId: {run_id}) started for suite_id: {suite_id}. Triggered by: {triggered_by.get('type', 'N/A')} user/schedule {triggered_by.get('username', triggered_by.get('name', 'N/A'))}.")
        workflow.logger.debug(f"Worker Config (keys): {list(worker_config.keys()) if worker_config else 'None'}")
        workflow.logger.debug(f"User Inputs: {user_inputs}")

        retry_policy = exceptions.RetryPolicy(
            initial_interval=timedelta(seconds=worker_config.get("retry_initial_interval_seconds", 10)),
            backoff_coefficient=worker_config.get("retry_backoff_coefficient", 2.0),
            maximum_interval=timedelta(seconds=worker_config.get("retry_maximum_interval_seconds", 60)),
            maximum_attempts=worker_config.get("retry_maximum_attempts", 3),
            non_retryable_error_types=["ConfigError", "SecretConfigError", "SecretNotFoundError", "ResolutionError", "HttpError"]
        )
        activity_timeout_minutes = worker_config.get("activity_timeout_minutes", 5)

        main_activity_result: Optional[Dict[str, Any]] = None
        main_activity_error: Optional[Dict[str, Any]] = None
        final_status = "UNKNOWN" # Should be SUCCESS or FAILED

        try:
            workflow.logger.info(f"Executing trigger_test_suite_activity for {suite_id}...")
            result = await workflow.execute_activity(
                trigger_test_suite_activity,
                args=[suite_id, worker_config, user_inputs],
                start_to_close_timeout=timedelta(minutes=activity_timeout_minutes),
                retry_policy=retry_policy,
            )
            workflow.logger.info(f"Activity for {suite_id} completed. Status: {result.get('status_code')}")
            main_activity_result = result
            final_status = "SUCCESS"
        except exceptions.ActivityError as e:
            workflow.logger.error(f"Activity failed for {suite_id}. Cause: {type(e.cause).__name__} - {e.cause}")
            error_type = type(e.cause).__name__ if e.cause else "ActivityError"
            error_message = str(e.cause)
            details_str = str(e.cause)
            if isinstance(e.cause, exceptions.ApplicationError):
                error_type = e.cause.type or error_type
                error_message = e.cause.message or str(e.cause)
                if e.cause.details: details_str = f"Message: {error_message}, Details: {e.cause.details}"

            main_activity_error = {"error_type": error_type, "message": error_message, "details_str": details_str}
            final_status = "FAILED"
        except Exception as e: # Catch other workflow-level errors (less common if activity is well-behaved)
            workflow.logger.error(f"Unexpected workflow error for {suite_id}: {type(e).__name__} - {e}")
            main_activity_error = {"error_type": "WorkflowError", "message": str(e), "details_str": str(e)}
            final_status = "FAILED"


        # --- Handle Notifications ---
        notification_configs = worker_config.get("notifications", {})
        notification_context = {
            "suite_id": suite_id, "workflow_id": workflow_id, "run_id": run_id, "status": final_status,
            "triggered_by_type": triggered_by.get("type", "N/A"),
            "triggered_by_user": triggered_by.get("username", triggered_by.get("name", "N/A")),
            "activity_result_message": main_activity_result.get("message", "") if main_activity_result else "",
            "activity_status_code": main_activity_result.get("status_code", "") if main_activity_result else "",
            "error_message": main_activity_error.get("message", "") if main_activity_error else "",
            "error_details": main_activity_error.get("details_str", "") if main_activity_error else "",
            "error_type": main_activity_error.get("error_type", "") if main_activity_error else ""
        }

        selected_notifications_rules = []
        if final_status == "SUCCESS" and notification_configs.get("on_success"):
            selected_notifications_rules = notification_configs["on_success"]
        elif final_status == "FAILED" and notification_configs.get("on_failure"):
            selected_notifications_rules = notification_configs["on_failure"]

        if selected_notifications_rules:
            workflow.logger.info(f"Processing {len(selected_notifications_rules)} {final_status} notifications for {suite_id}.")
            for notif_conf in selected_notifications_rules:
                try:
                    notif_type = notif_conf.get("type")
                    # Use a child workflow for each notification for isolation and independent retries
                    # This makes the main workflow more resilient to notification failures.
                    # Child workflow ID should be unique for idempotency if the parent retries this block.
                    child_wf_id = f"{workflow_id}-notif-{notif_type}-{workflow.uuid4()}"

                    if notif_type == "email":
                        subject = _resolve_notification_template(notif_conf.get("subject_template", "WF {workflow_id} - Suite {suite_id} {status}"), notification_context)
                        body_template = notif_conf.get("body_template", "Suite: {suite_id}\nStatus: {status}\nTrigger: {triggered_by_type} by {triggered_by_user}\nResult: {activity_result_message}\nError: {error_message}\nDetails: {error_details}")
                        body = _resolve_notification_template(body_template, notification_context)
                        await workflow.execute_child_workflow(
                            "SendNotificationChildWorkflow", # A generic child workflow for notifications
                            args=[{
                                "type": "email", "recipients": notif_conf.get("recipients", []),
                                "subject": subject, "body": body,
                                "smtp_config_env_prefix": notif_conf.get("smtp_config_env_prefix", "SMTP")
                            }], id=child_wf_id, start_to_close_timeout=timedelta(minutes=2) # Short overall timeout for child
                        )
                    elif notif_type == "teams":
                        webhook_env_var = notif_conf.get("webhook_env_var")
                        if not webhook_env_var: workflow.logger.warn("Teams 'webhook_env_var' missing."); continue
                        teams_msg = _resolve_notification_template(notif_conf.get("message_template", "Suite {suite_id} {status}. Details: {activity_result_message}{error_message}"), notification_context)
                        await workflow.execute_child_workflow(
                            "SendNotificationChildWorkflow",
                            args=[{"type": "teams", "webhook_env_var": webhook_env_var, "message_payload": {"text": teams_msg}}],
                            id=child_wf_id, start_to_close_timeout=timedelta(minutes=1)
                        )
                    elif notif_type == "opsgenie":
                        api_key_env_var = notif_conf.get("api_key_env_var")
                        if not api_key_env_var: workflow.logger.warn("Opsgenie 'api_key_env_var' missing."); continue
                        og_msg = _resolve_notification_template(notif_conf.get("message_template", "Suite {suite_id} {status} ({workflow_id})"), notification_context)
                        og_alias = _resolve_notification_template(notif_conf.get("alias_template", "{suite_id}-{workflow_id}-{status}"), notification_context)
                        og_pri = notif_conf.get("priority", "P3")
                        og_details = {k:v for k,v in notification_context.items() if k not in ["error_details"]} # Avoid huge details in main alert
                        og_details["raw_error_details_str"] = notification_context["error_details"] # Add full error string
                        await workflow.execute_child_workflow(
                            "SendNotificationChildWorkflow",
                            args=[{"type": "opsgenie", "api_key_env_var": api_key_env_var, "message": og_msg, "alias": og_alias, "priority": og_pri, "details": og_details}],
                            id=child_wf_id, start_to_close_timeout=timedelta(minutes=1)
                        )
                    else: workflow.logger.warn(f"Unsupported notification type: {notif_type}")
                except Exception as ne: workflow.logger.error(f"Failed to start child notification workflow for type '{notif_conf.get('type')}': {ne}")

        # Final return from ExecuteTestSuiteWorkflow
        if final_status == "SUCCESS":
            return {"status": "SUCCESS", "suite_id": suite_id, "triggered_by": triggered_by, "message": main_activity_result.get("message") if main_activity_result else "Completed", "details": main_activity_result}
        else:
            return {"status": "FAILED", "suite_id": suite_id, "triggered_by": triggered_by, "error_type": main_activity_error.get("error_type") if main_activity_error else "WorkflowError", "message": main_activity_error.get("message") if main_activity_error else "N/A", "details_str": main_activity_error.get("details_str") if main_activity_error else "N/A"}


@workflow.defn
class SendNotificationChildWorkflow:
    @workflow.run
    async def run(self, notification_params: Dict[str, Any]) -> None:
        notif_type = notification_params["type"]
        workflow.logger.info(f"SendNotificationChildWorkflow started for type: {notif_type}")

        # Define a simple retry policy for notification activities
        retry_policy = exceptions.RetryPolicy(
            initial_interval=timedelta(seconds=5),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(seconds=30),
            maximum_attempts=3,
            non_retryable_error_types=["NotificationConfigError"] # Don't retry if config is bad
        )
        activity_timeout = timedelta(seconds=45) # Slightly less than child workflow timeout

        try:
            if notif_type == "email":
                await workflow.execute_activity(
                    send_email_notification_activity,
                    args=[notification_params["recipients"], notification_params["subject"], notification_params["body"], notification_params.get("smtp_config_env_prefix", "SMTP")],
                    start_to_close_timeout=activity_timeout, retry_policy=retry_policy
                )
            elif notif_type == "teams":
                await workflow.execute_activity(
                    send_teams_notification_activity,
                    args=[notification_params["webhook_env_var"], notification_params["message_payload"]],
                    start_to_close_timeout=activity_timeout, retry_policy=retry_policy
                )
            elif notif_type == "opsgenie":
                await workflow.execute_activity(
                    send_opsgenie_notification_activity,
                    args=[notification_params["api_key_env_var"], notification_params["message"], notification_params["alias"], notification_params["priority"], notification_params.get("details")],
                    start_to_close_timeout=activity_timeout, retry_policy=retry_policy
                )
            workflow.logger.info(f"Notification type '{notif_type}' processed successfully.")
        except Exception as e:
            workflow.logger.error(f"Notification activity for type '{notif_type}' failed: {e}")
            # Decide if this child workflow should raise an error to be retried by parent if this matters
            # For now, child workflow failure is logged but doesn't propagate to ExecuteTestSuiteWorkflow's main result
            raise # Re-raise to let Temporal handle retries for this child workflow if applicable


# ScheduledTestSuiteRunnerWorkflow remains the same
@workflow.defn
class ScheduledTestSuiteRunnerWorkflow:
    @workflow.run
    async def run(self, schedule_params: Dict[str, Any]) -> None:
        suite_id = schedule_params["suite_id"]; worker_config = schedule_params["worker_config"]; user_inputs = schedule_params["user_inputs"]; schedule_name = schedule_params.get("schedule_name", f"cron_{suite_id}")
        trigger_info = {"type": "schedule", "username": schedule_name, "name": schedule_name}
        workflow.logger.info(f"ScheduledTestSuiteRunnerWorkflow: Triggering for schedule '{schedule_name}', suite_id '{suite_id}'.")
        execution_params = {"suite_id": suite_id, "worker_config": worker_config, "user_inputs": user_inputs, "triggered_by": trigger_info}
        child_workflow_id = f"scheduled-{schedule_name}-{suite_id}-{workflow.uuid4()}"
        try:
            await workflow.start_child_workflow(ExecuteTestSuiteWorkflow, args=[execution_params], id=child_workflow_id)
            workflow.logger.info(f"Successfully started child workflow '{child_workflow_id}' for schedule '{schedule_name}'.")
        except Exception as e:
            workflow.logger.error(f"Failed to start child workflow for schedule '{schedule_name}', suite_id '{suite_id}'. Error: {type(e).__name__} - {e}")
            pass
