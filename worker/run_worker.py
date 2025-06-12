import asyncio
from temporalio.client import Client
from temporalio.worker import Worker

# Import activities and workflows
from config_loader_activity import load_config_file, get_test_suite_config
from execution_activities import trigger_test_suite_activity # New activity
from workflows import ConfigReaderWorkflow, TestSuiteConfigWorkflow, ExecuteTestSuiteWorkflow # New workflow

async def main():
    client = await Client.connect("localhost:7233")

    worker = Worker(
        client,
        task_queue="my-task-queue",
        workflows=[ConfigReaderWorkflow, TestSuiteConfigWorkflow, ExecuteTestSuiteWorkflow], # Add new workflow
        activities=[load_config_file, get_test_suite_config, trigger_test_suite_activity], # Add new activity
    )
    print("Worker started with ExecuteTestSuiteWorkflow and trigger_test_suite_activity. Waiting for tasks...")
    await worker.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Worker shutting down...")
