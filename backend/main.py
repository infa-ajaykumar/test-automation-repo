from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from temporalio.client import Client, WorkflowHandle # Added WorkflowHandle
from temporalio.exceptions import WorkflowAlreadyStartedError
import uuid
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

TEMPORAL_SERVER_URL = os.getenv("TEMPORAL_SERVER_URL", "localhost:7233")
TASK_QUEUE = os.getenv("TEMPORAL_TASK_QUEUE", "test-suite-task-queue") # Ensure this is used

class TestInput(BaseModel):
    csp: str = Field(..., description="Cloud Service Provider (e.g., AWS, Azure, GCP)")
    region: str = Field(..., description="Region for the test (e.g., us-east-1)")
    product: str = Field(..., description="Product name (e.g., ProductA, ProductB)")
    pod: str | None = Field(None, description="Pod identifier (optional)")
    environment: str = Field(..., description="Environment (e.g., dev, staging, prod)")
    testsuite_type: str = Field(..., description="Type of test suite (e.g., smoke, functional, performance)")

# Keep track of active Temporal clients
# This is a simple way to manage client connections.
# For production, consider a more robust connection management strategy.
_temporal_client = None

async def get_temporal_client():
    global _temporal_client
    if _temporal_client is None or _temporal_client.is_closed:
        _temporal_client = await Client.connect(TEMPORAL_SERVER_URL)
    return _temporal_client

@app.on_event("shutdown")
async def app_shutdown():
    global _temporal_client
    if _temporal_client and not _temporal_client.is_closed:
        await _temporal_client.close()
        print("Temporal client closed.")

@app.post("/trigger-test")
async def trigger_test(input_data: TestInput):
    workflow_id = f"test-suite-{input_data.product.lower()}-{input_data.testsuite_type.lower()}-{uuid.uuid4()}"
    try:
        client = await get_temporal_client()

        # Actually start the workflow
        handle: WorkflowHandle = await client.start_workflow(
            "TestSuiteWorkflow", # Name of the workflow class registered by the worker
            input_data.model_dump(), # Pass the Pydantic model as a dict
            id=workflow_id,
            task_queue=TASK_QUEUE,
            # Other options like timeouts can be set here if needed
            # workflow_execution_timeout=timedelta(hours=1),
        )

        print(f"Successfully started workflow_id='{handle.id}', run_id='{handle.first_execution_run_id}'")

        return {
            "message": "Workflow successfully initiated",
            "workflow_id": handle.id,
            "run_id": handle.first_execution_run_id
        }

    except WorkflowAlreadyStartedError:
        # This specific exception means a workflow with this ID already exists and is running.
        # You might want to fetch its status or just inform the user.
        print(f"Workflow with ID {workflow_id} already started.")
        raise HTTPException(status_code=409, detail=f"Workflow with ID {workflow_id} already exists.")
    except Exception as e:
        # Catching a broader range of Temporal client exceptions or connection issues.
        print(f"Error starting workflow: {e}")
        # Check if it's a known Temporal exception type for more specific error handling
        # For example, if isinstance(e, temporalio.service.RPCError) and e.status == temporalio.service.RPCStatusCode.UNAVAILABLE:
        #    raise HTTPException(status_code=503, detail="Temporal server unavailable")
        raise HTTPException(status_code=500, detail=f"Failed to start test workflow: {str(e)}")

# Example endpoint to get workflow result (requires workflow to complete)
@app.get("/workflow-result/{workflow_id}")
async def get_workflow_result(workflow_id: str, run_id: str | None = None):
    try:
        client = await get_temporal_client()
        handle = client.get_workflow_handle(workflow_id=workflow_id, run_id=run_id) # Use run_id if provided

        # You might want to add a timeout here
        # result = await handle.result(timeout_seconds=60) # Waits for workflow to complete

        # For now, let's just describe it to see its status without waiting for completion
        description = await handle.describe()

        # If you want to wait for result:
        # if description.status == temporalio.WorkflowExecutionStatus.RUNNING:
        #     return {"workflow_id": workflow_id, "status": "RUNNING", "message": "Workflow is still running. Try again later."}
        # elif description.status == temporalio.WorkflowExecutionStatus.COMPLETED:
        #     result = await handle.result() # This will fetch the actual result
        #     return {"workflow_id": workflow_id, "status": "COMPLETED", "result": result}
        # else:
        #     # Handle other statuses like FAILED, TIMED_OUT, TERMINATED, CANCELED
        #     # For failed workflows, you might want to get the error
        #     error_message = "Workflow did not complete successfully."
        #     if description.status == temporalio.WorkflowExecutionStatus.FAILED:
        #         try:
        #             await handle.result() # This will raise the workflow failure exception
        #         except Exception as wf_error:
        #             error_message = str(wf_error)

        return {
            "workflow_id": workflow_id,
            "run_id": description.run_id,
            "status": str(description.status.name), # e.g. RUNNING, COMPLETED, FAILED
            "task_queue": description.task_queue,
            # "result_placeholder": "To get actual result, workflow must complete. This is a describe call."
        }

    except Exception as e: # Catch specific Temporal exceptions if possible
        print(f"Error describing workflow {workflow_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching workflow details: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
