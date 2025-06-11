import asyncio
import os
from dotenv import load_dotenv
import logging

from temporalio.client import Client
from temporalio.worker import Worker

# Import activities and workflows
from .activities import load_config_activity, execute_test_suite_activity
from .workflows import TestSuiteWorkflow

# Load environment variables from .env file
load_dotenv()

# Configure basic logging for the worker
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TEMPORAL_SERVER_URL = os.getenv("TEMPORAL_SERVER_URL", "localhost:7233")
TASK_QUEUE = os.getenv("TEMPORAL_TASK_QUEUE", "test-suite-task-queue")

async def main():
    try:
        client = await Client.connect(TEMPORAL_SERVER_URL)
        logger.info(f"Successfully connected to Temporal server at {TEMPORAL_SERVER_URL}")
    except Exception as e:
        logger.error(f"Failed to connect to Temporal server at {TEMPORAL_SERVER_URL}: {e}")
        return

    # Create and run the worker
    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[TestSuiteWorkflow],
        activities=[load_config_activity, execute_test_suite_activity],
        # You can set limits on concurrent activities/workflows if needed
        # max_concurrent_activities=100,
        # max_concurrent_workflow_tasks=100,
    )
    logger.info(f"Worker configured for task queue: {TASK_QUEUE}")
    logger.info(f"Registered workflows: {[wf.__name__ for wf in worker.workflows]}")
    logger.info(f"Registered activities: {[act.name for act in worker.activities]}")

    try:
        logger.info("Starting Temporal worker...")
        await worker.run()
        logger.info("Temporal worker stopped.")
    except KeyboardInterrupt:
        logger.info("Temporal worker shutting down due to KeyboardInterrupt...")
    except Exception as e:
        logger.error(f"Temporal worker failed: {e}")
    finally:
        # May not be reached if run() runs forever or due to abrupt termination
        logger.info("Worker shutdown process complete.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application shutting down...")
