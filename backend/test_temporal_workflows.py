import asyncio
from temporalio.client import Client
from temporalio.exceptions import WorkflowFailureError # Import for error handling

# Assuming workflows are defined with these names in the worker
# These are placeholder class names if you don't have the actual workflow definitions
# available directly for import in this standalone script.
# In a real monorepo structure, you might share type definitions.
WORKFLOW_CONFIG_READER = "ConfigReaderWorkflow"
WORKFLOW_TEST_SUITE_CONFIG = "TestSuiteConfigWorkflow"

async def main():
    try:
        client = await Client.connect("localhost:7233") # Ensure Temporal server is running
        print("Connected to Temporal server.")

        # Test 1: Trigger ConfigReaderWorkflow to get 'products.yaml'
        print("\n--- Testing ConfigReaderWorkflow for 'products' ---")
        try:
            products_config = await client.execute_workflow(
                WORKFLOW_CONFIG_READER,
                "products", # Argument for the workflow's run method
                id="test-config-reader-products-workflow",
                task_queue="my-task-queue", # Must match the worker's task queue
            )
            print("Successfully fetched 'products' config via Temporal workflow:")
            print(products_config)
        except WorkflowFailureError as e:
            print(f"Workflow ConfigReaderWorkflow for 'products' FAILED.")
            print(f"Cause: {e.cause}") # Provides more details on the failure within the workflow/activity
            if e.cause and hasattr(e.cause, 'message'):
                 print(f"Failure message: {e.cause.message}")
        except Exception as e:
            print(f"An unexpected error occurred while testing ConfigReaderWorkflow: {e}")


        # Test 2: Trigger ConfigReaderWorkflow for a non-existent config
        print("\n--- Testing ConfigReaderWorkflow for 'non_existent_config' ---")
        try:
            non_existent_data = await client.execute_workflow(
                WORKFLOW_CONFIG_READER,
                "non_existent_config",
                id="test-config-reader-non-existent-workflow",
                task_queue="my-task-queue",
            )
            print("Fetched 'non_existent_config' (this should ideally fail gracefully):")
            print(non_existent_data)
        except WorkflowFailureError as e:
            print(f"Workflow ConfigReaderWorkflow for 'non_existent_config' FAILED as expected.")
            # Check if the cause is FileNotFoundError or ValueError from the activity
            if e.cause and (isinstance(e.cause, FileNotFoundError) or isinstance(e.cause, ValueError)):
                print(f"Reason: {e.cause}")
            else:
                print(f"Unexpected failure reason: {e.cause}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")


        # Test 3: Trigger TestSuiteConfigWorkflow for 'suite_login'
        print("\n--- Testing TestSuiteConfigWorkflow for 'suite_login' ---")
        try:
            suite_login_config = await client.execute_workflow(
                WORKFLOW_TEST_SUITE_CONFIG,
                "suite_login", # Argument: suite_id
                id="test-suite-config-login-workflow",
                task_queue="my-task-queue",
            )
            print("Successfully fetched 'suite_login' config via Temporal workflow:")
            # Basic check if structure is as expected
            if suite_login_config and isinstance(suite_login_config, dict) and suite_login_config.get('id') == 'suite_login':
                print("Config structure looks good.")
                print(f"Name: {suite_login_config.get('name')}")
            else:
                print("Config structure is NOT as expected.")
            # print(suite_login_config) # Optionally print full config
        except WorkflowFailureError as e:
            print(f"Workflow TestSuiteConfigWorkflow for 'suite_login' FAILED.")
            print(f"Cause: {e.cause}")
            if e.cause and hasattr(e.cause, 'message'):
                 print(f"Failure message: {e.cause.message}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

        # Test 4: Trigger TestSuiteConfigWorkflow for a non-existent suite_id
        print("\n--- Testing TestSuiteConfigWorkflow for 'non_existent_suite' ---")
        try:
            non_existent_suite_data = await client.execute_workflow(
                WORKFLOW_TEST_SUITE_CONFIG,
                "non_existent_suite",
                id="test-suite-config-non-existent-workflow",
                task_queue="my-task-queue",
            )
            print("Fetched 'non_existent_suite' (this should fail gracefully):")
            print(non_existent_suite_data)
        except WorkflowFailureError as e:
            print(f"Workflow TestSuiteConfigWorkflow for 'non_existent_suite' FAILED as expected.")
            if e.cause and isinstance(e.cause, ValueError) and "not found" in str(e.cause).lower(): # Check for specific error
                print(f"Reason: {e.cause}")
            else:
                print(f"Unexpected failure reason: {e.cause}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

    except ConnectionRefusedError:
        print("Could not connect to Temporal server at localhost:7233. Ensure it's running.")
    except Exception as e:
        print(f"An overall error occurred: {e}")


if __name__ == "__main__":
    asyncio.run(main())
