from temporalio import activity, exceptions
import httpx
import smtplib
from email.mime.text import MIMEText
import os
import json # For Opsgenie payload
from typing import Dict, Any, List, Optional

# Helper to resolve templates in notification messages
def _resolve_notification_template(template_string: str, context: Dict[str, Any]) -> str:
    resolved_string = template_string
    for key, value in context.items():
        placeholder = f"{{{key}}}"
        resolved_string = resolved_string.replace(placeholder, str(value))
    return resolved_string

@activity.defn
async def send_email_notification_activity(
    recipients: List[str], subject: str, body: str, smtp_config_env_prefix: str = "SMTP"
) -> Dict[str, Any]:
    activity.logger.info(f"Attempting to send email to: {recipients} with subject: {subject}")

    host = os.environ.get(f"{smtp_config_env_prefix}_HOST")
    port_str = os.environ.get(f"{smtp_config_env_prefix}_PORT", "587")
    user = os.environ.get(f"{smtp_config_env_prefix}_USER")
    password = os.environ.get(f"{smtp_config_env_prefix}_PASSWORD")
    sender_email = os.environ.get(f"{smtp_config_env_prefix}_SENDER_EMAIL")
    use_tls_str = os.environ.get(f"{smtp_config_env_prefix}_USE_TLS", "true").lower() # Default to true for port 587

    if not all([host, sender_email]):
        activity.logger.error(f"SMTP configuration ({smtp_config_env_prefix}_HOST, {smtp_config_env_prefix}_SENDER_EMAIL) missing.")
        raise exceptions.ApplicationError("SMTP configuration incomplete.", type="NotificationConfigError")

    try:
        port = int(port_str)
    except ValueError:
        activity.logger.error(f"Invalid SMTP port: {port_str}. Must be an integer.")
        raise exceptions.ApplicationError("Invalid SMTP port configuration.", type="NotificationConfigError")

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = ", ".join(recipients)

    try:
        server_kwargs = {'host': host, 'port': port, 'timeout': 30} # Added timeout

        if port == 465: # SSL
            server = smtplib.SMTP_SSL(**server_kwargs)
        else: # Standard SMTP
            server = smtplib.SMTP(**server_kwargs)
            if use_tls_str == "true": # Check if STARTTLS is configured (e.g. if port is 587)
                 server.starttls()

        if user and password:
            server.login(user, password)

        server.sendmail(sender_email, recipients, msg.as_string())
        server.quit()
        activity.logger.info("Email sent successfully.")
        return {"status": "success", "message": "Email sent."}
    except Exception as e:
        activity.logger.error(f"Failed to send email: {type(e).__name__} - {e}")
        raise exceptions.ApplicationError(f"Email sending failed: {type(e).__name__} - {str(e)}", type="EmailSendError")


@activity.defn
async def send_teams_notification_activity(webhook_env_var: str, message_payload: Dict[str, Any]) -> Dict[str, Any]:
    webhook_url = os.environ.get(webhook_env_var)
    if not webhook_url:
        activity.logger.error(f"Teams webhook URL environment variable '{webhook_env_var}' not set.")
        raise exceptions.ApplicationError(f"Teams webhook URL env var '{webhook_env_var}' not set.", type="NotificationConfigError")

    activity.logger.info(f"Attempting to send Teams notification using webhook from env var '{webhook_env_var}'.")

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(webhook_url, json=message_payload)
            response.raise_for_status()
            activity.logger.info(f"Teams notification sent successfully via {webhook_env_var}.")
            return {"status": "success", "message": "Teams notification sent."}
        except httpx.HTTPStatusError as e:
            activity.logger.error(f"Failed to send Teams notification via {webhook_env_var}: {e.response.status_code} - {e.response.text[:200]}")
            raise exceptions.ApplicationError(f"Teams API error: {e.response.status_code}", type="TeamsApiError", details={"response": e.response.text[:200]})
        except Exception as e:
            activity.logger.error(f"Failed to send Teams notification via {webhook_env_var}: {type(e).__name__} - {e}")
            raise exceptions.ApplicationError(f"Teams notification failed: {str(e)}", type="TeamsSendError")


@activity.defn
async def send_opsgenie_notification_activity(
    api_key_env_var: str, message: str, alias: str, priority: str, details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    api_key = os.environ.get(api_key_env_var)
    if not api_key:
        activity.logger.error(f"Opsgenie API key environment variable '{api_key_env_var}' not set.")
        raise exceptions.ApplicationError(f"Opsgenie API key env var '{api_key_env_var}' not set.", type="NotificationConfigError")

    activity.logger.info(f"Attempting to send Opsgenie alert: {message[:50]}... with priority {priority} using key from '{api_key_env_var}'.")

    opsgenie_api_url = os.environ.get("OPSGENIE_API_URL", "https://api.opsgenie.com/v2/alerts")

    headers = {"Authorization": f"GenieKey {api_key}", "Content-Type": "application/json"}
    payload = {"message": message, "alias": alias, "priority": priority, "details": details or {}}

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(opsgenie_api_url, json=payload, headers=headers)
            response.raise_for_status()
            activity.logger.info(f"Opsgenie alert created successfully via {api_key_env_var}.")
            return {"status": "success", "message": "Opsgenie alert created.", "result": response.json()}
        except httpx.HTTPStatusError as e:
            activity.logger.error(f"Failed to send Opsgenie alert via {api_key_env_var}: {e.response.status_code} - {e.response.text[:200]}")
            raise exceptions.ApplicationError(f"Opsgenie API error: {e.response.status_code}", type="OpsgenieApiError", details={"response": e.response.text[:200]})
        except Exception as e:
            activity.logger.error(f"Failed to send Opsgenie alert via {api_key_env_var}: {type(e).__name__} - {e}")
            raise exceptions.ApplicationError(f"Opsgenie alert failed: {str(e)}", type="OpsgenieSendError")
