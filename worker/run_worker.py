import asyncio
from temporalio.client import Client
from temporalio.worker import Worker

from config_loader_activity import load_config_file, get_test_suite_config
from execution_activities import trigger_test_suite_activity
from notification_activities import (
    send_email_notification_activity,
    send_teams_notification_activity,
    send_opsgenie_notification_activity
)
from workflows import (
    ConfigReaderWorkflow,
    TestSuiteConfigWorkflow,
    ExecuteTestSuiteWorkflow,
    ScheduledTestSuiteRunnerWorkflow,
    SendNotificationChildWorkflow # New child workflow for notifications
)

async def main():
    client = await Client.connect("localhost:7233")
    worker = Worker(
        client,
        task_queue="my-task-queue",
        workflows=[
            ConfigReaderWorkflow,
            TestSuiteConfigWorkflow,
            ExecuteTestSuiteWorkflow,
            ScheduledTestSuiteRunnerWorkflow,
            SendNotificationChildWorkflow # Register new child workflow
        ],
        activities=[
            load_config_file,
            get_test_suite_config,
            trigger_test_suite_activity,
            send_email_notification_activity, # Add new notification activities
            send_teams_notification_activity,
            send_opsgenie_notification_activity
        ],
    )
    print("Worker started with notification activities and SendNotificationChildWorkflow. Waiting for tasks...")
    await worker.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Worker shutting down...")
