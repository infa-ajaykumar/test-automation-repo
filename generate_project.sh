#!/bin/bash

# Script to generate the full-stack test orchestrator project

# Exit immediately if a command exits with a non-zero status.
set -e

echo "Starting project generation..."

# --- Create Root Directories ---
echo "Creating root directories: backend, worker, config, frontend..."
mkdir -p backend worker config

# --- .gitignore ---
echo "Creating .gitignore..."
cat << 'EOF' > .gitignore
# Python
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
env/
venv/
pip-wheel-metadata/
.eggs/
*.egg-info/
dist/
build/

# Node
node_modules/
npm-debug.log*
yarn-debug.log*
yarn-error.log*
# package-lock.json # Usually committed, but can be ignored if generating fresh
# yarn.lock # Usually committed

# IDE / OS
.idea/
.vscode/
*.suo
*.ntvs*
*.njsproj
*.sln
*.sw?
.DS_Store

# Environment files
.env
.env.*
!.env.example

# Temporal
temporal.db

# Build artifacts
/build
/dist
/out
*.tar.gz
*.zip

# Frontend specific
frontend/build
frontend/node_modules
EOF

# --- Backend Files ---
echo "Creating backend files..."
# backend/main.py
cat << 'EOF' > backend/main.py
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from temporalio.client import Client, WorkflowHandle
from temporalio.exceptions import WorkflowAlreadyStartedError
import uuid
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

TEMPORAL_SERVER_URL = os.getenv("TEMPORAL_SERVER_URL", "localhost:7233")
TASK_QUEUE = os.getenv("TEMPORAL_TASK_QUEUE", "test-suite-task-queue")

class TestInput(BaseModel):
    csp: str = Field(..., description="Cloud Service Provider (e.g., AWS, Azure, GCP)")
    region: str = Field(..., description="Region for the test (e.g., us-east-1)")
    product: str = Field(..., description="Product name (e.g., ProductA, ProductB)")
    pod: str | None = Field(None, description="Pod identifier (optional)")
    environment: str = Field(..., description="Environment (e.g., dev, staging, prod)")
    testsuite_type: str = Field(..., description="Type of test suite (e.g., smoke, functional, performance)")

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

@app.post("/api/trigger-test") # Changed to /api/trigger-test for proxying
async def trigger_test(input_data: TestInput):
    workflow_id = f"test-suite-{input_data.product.lower()}-{input_data.testsuite_type.lower()}-{uuid.uuid4()}"
    try:
        client = await get_temporal_client()

        handle: WorkflowHandle = await client.start_workflow(
            "TestSuiteWorkflow",
            input_data.model_dump(),
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )

        print(f"Successfully started workflow_id='{handle.id}', run_id='{handle.first_execution_run_id}'")

        return {
            "message": "Workflow successfully initiated",
            "workflow_id": handle.id,
            "run_id": handle.first_execution_run_id
        }

    except WorkflowAlreadyStartedError:
        print(f"Workflow with ID {workflow_id} already started.")
        raise HTTPException(status_code=409, detail=f"Workflow with ID {workflow_id} already exists.")
    except Exception as e:
        print(f"Error starting workflow: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start test workflow: {str(e)}")

@app.get("/api/workflow-result/{workflow_id}") # Changed to /api for proxying
async def get_workflow_result(workflow_id: str, run_id: str | None = None):
    try:
        client = await get_temporal_client()
        handle = client.get_workflow_handle(workflow_id=workflow_id, run_id=run_id)

        description = await handle.describe()

        return {
            "workflow_id": workflow_id,
            "run_id": description.run_id,
            "status": str(description.status.name),
            "task_queue": description.task_queue,
        }

    except Exception as e:
        print(f"Error describing workflow {workflow_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching workflow details: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
EOF

# backend/requirements.txt
cat << 'EOF' > backend/requirements.txt
fastapi>=0.100.0
uvicorn[standard]>=0.20.0
pydantic>=2.0.0
python-dotenv>=1.0.0
temporalio>=1.0.0
EOF

# backend/.env.example
cat << 'EOF' > backend/.env.example
TEMPORAL_SERVER_URL="localhost:7233"
TEMPORAL_TASK_QUEUE="test-suite-task-queue"
EOF

# --- Worker Files ---
echo "Creating worker files..."
# worker/main.py
cat << 'EOF' > worker/main.py
import asyncio
import os
from dotenv import load_dotenv
import logging

from temporalio.client import Client
from temporalio.worker import Worker

from .activities import load_config_activity, execute_test_suite_activity
from .workflows import TestSuiteWorkflow

load_dotenv()

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

    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[TestSuiteWorkflow],
        activities=[load_config_activity, execute_test_suite_activity],
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
        logger.info("Worker shutdown process complete.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application shutting down...")
EOF

# worker/activities.py
cat << 'EOF' > worker/activities.py
from temporalio import activity
import os
import requests
from dotenv import load_dotenv

from .config_loader import load_yaml_config

load_dotenv()

@activity.defn
async def load_config_activity(product: str, testsuite_type: str) -> dict:
    activity.logger.info(f"Executing load_config_activity for product: {product}, testsuite_type: {testsuite_type}")
    try:
        config = load_yaml_config(product, testsuite_type)

        required_keys = ['target_url', 'http_method']
        for key in required_keys:
            if key not in config:
                raise ValueError(f"Missing required key '{key}' in configuration file for {product} - {testsuite_type}")

        config.setdefault('default_parameters', {})
        config.setdefault('credential_env_keys', {})

        return config
    except FileNotFoundError as e:
        activity.logger.error(f"Configuration file not found: {e}")
        raise ValueError(f"Configuration not found: {str(e)}") from e
    except ValueError as e:
        activity.logger.error(f"Invalid configuration: {e}")
        raise
    except Exception as e:
        activity.logger.error(f"Unexpected error in load_config_activity: {e}")
        raise

@activity.defn
async def execute_test_suite_activity(
    url: str,
    method: str,
    params: dict | None,
    resolved_credentials: dict | None
) -> dict:
    activity.logger.info(f"Executing test suite: {method} to {url}")
    activity.logger.info(f"Parameters: {params}")
    activity.logger.info(f"Headers (credentials keys): {resolved_credentials.keys() if resolved_credentials else 'None'}")

    headers = resolved_credentials if resolved_credentials else {}
    headers.update({
        'Content-Type': 'application/json'
    })

    try:
        request_method = method.upper()
        if request_method == 'POST':
            response = requests.post(url, json=params, headers=headers, timeout=300)
        elif request_method == 'GET':
            response = requests.get(url, params=params, headers=headers, timeout=300)
        else:
            activity.logger.error(f"Unsupported HTTP method: {request_method}")
            return {
                "status_code": 0,
                "response_body": None,
                "error": f"Unsupported HTTP method: {request_method}"
            }

        response_body = ""
        try:
            response_body = response.json()
        except requests.exceptions.JSONDecodeError:
            response_body = response.text

        if response.status_code >= 400:
            activity.logger.error(f"HTTP Error {response.status_code}: {response_body}")
            return {
                "status_code": response.status_code,
                "response_body": response_body,
                "error": f"HTTP Error {response.status_code}"
            }

        activity.logger.info(f"Successfully executed test suite. Status: {response.status_code}")
        return {
            "status_code": response.status_code,
            "response_body": response_body,
            "error": None
        }

    except requests.exceptions.RequestException as e:
        activity.logger.error(f"Request failed: {e}")
        return {
            "status_code": 0,
            "response_body": None,
            "error": f"Request failed: {str(e)}"
        }
    except Exception as e:
        activity.logger.error(f"An unexpected error occurred in execute_test_suite_activity: {e}")
        return {
            "status_code": 0,
            "response_body": None,
            "error": f"An unexpected error occurred: {str(e)}"
        }
EOF

# worker/workflows.py
cat << 'EOF' > worker/workflows.py
from temporalio import workflow, exceptions
from datetime import timedelta
import os

from .activities import load_config_activity, execute_test_suite_activity

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
            config = await workflow.execute_activity(
                load_config_activity,
                args=[product, testsuite_type],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=workflow.RetryPolicy(
                    maximum_attempts=3,
                    non_retryable_error_types=["ValueError"]
                )
            )
            workflow.logger.info(f"Configuration loaded: {config}")

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

            execution_params = config.get("default_parameters", {})
            if "pod" in input_data and input_data["pod"] is not None:
                 execution_params["pod"] = input_data["pod"]
            if "environment" in input_data:
                 execution_params["environment"] = input_data["environment"]

            result = await workflow.execute_activity(
                execute_test_suite_activity,
                args=[
                    config["target_url"],
                    config["http_method"],
                    execution_params,
                    resolved_credentials
                ],
                start_to_close_timeout=timedelta(minutes=15),
                heartbeat_timeout=timedelta(minutes=2),
                retry_policy=workflow.RetryPolicy(
                    maximum_attempts=2,
                    non_retryable_error_types=[]
                )
            )
            workflow.logger.info(f"Test suite execution activity completed. Result: {result}")
            return result

        except exceptions.ActivityError as e:
            workflow.logger.error(f"Activity failed: {e.cause}")
            return {
                "error": f"Activity execution failed: {type(e.cause).__name__} - {str(e.cause)}",
                "details": str(e.cause),
                "status_code": 500
            }
        except Exception as e:
            workflow.logger.error(f"Workflow failed with an unexpected error: {e}")
            return {"error": f"Workflow error: {str(e)}", "status_code": 500}
EOF

# worker/config_loader.py
cat << 'EOF' > worker/config_loader.py
import yaml
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CONFIG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config"))

def load_yaml_config(product: str, testsuite_type: str) -> dict:
    filename = f"{product.lower()}_{testsuite_type.lower()}.yaml"
    filepath = os.path.join(CONFIG_DIR, filename)

    logger.info(f"Attempting to load configuration from: {filepath}")

    if not os.path.exists(CONFIG_DIR):
        logger.error(f"Configuration directory not found: {CONFIG_DIR}")
        raise FileNotFoundError(f"Configuration directory not found: {CONFIG_DIR}")

    try:
        with open(filepath, 'r') as f:
            config_data = yaml.safe_load(f)
            if not isinstance(config_data, dict):
                logger.error(f"Invalid configuration format in {filepath}: Expected a dictionary.")
                raise ValueError(f"Invalid configuration format in {filepath}: Expected a dictionary.")
            logger.info(f"Successfully loaded configuration from {filepath}")
            return config_data
    except FileNotFoundError:
        logger.error(f"Configuration file not found: {filepath}")
        raise FileNotFoundError(f"Configuration file not found: {filepath}")
    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML file {filepath}: {e}")
        raise ValueError(f"Error parsing YAML file {filepath}: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred while loading {filepath}: {e}")
        raise
EOF

# worker/requirements.txt
cat << 'EOF' > worker/requirements.txt
temporalio>=1.0.0
pyyaml>=6.0
requests>=2.20.0
python-dotenv>=1.0.0
EOF

# worker/.env.example
cat << 'EOF' > worker/.env.example
TEMPORAL_SERVER_URL="localhost:7233"
TEMPORAL_TASK_QUEUE="test-suite-task-queue"

# --- Example Credential Environment Variables ---
# These are examples based on the credential_env_keys in the
# example YAML files within the /config directory.
# You should replace the placeholder values with actual secrets.

# For config/producta_functional.yaml:
PRODUCT_A_AUTH_TOKEN="your_actual_product_a_auth_token_here"
PRODUCT_A_CUSTOM_HEADER_VALUE="your_product_a_custom_header_value_here"

# For config/productb_smoketest.yaml:
PRODUCT_B_API_TOKEN="your_actual_product_b_api_token_here"
EOF

# --- Config Files ---
echo "Creating config files..."
# config/producta_functional.yaml
cat << 'EOF' > config/producta_functional.yaml
# Example configuration for Product A - Functional Tests
target_url: "https://jenkins.example.com/job/productA/job/runFunctionalTests"
http_method: "POST"

default_parameters:
  suite_id: "functional_v1"
  timeout_minutes: 60
  notification_email: "dev-team-a@example.com"

credential_env_keys:
  Authorization: "PRODUCT_A_AUTH_TOKEN"
  X-Custom-Header: "PRODUCT_A_CUSTOM_HEADER_VALUE"
EOF

# config/productb_smoketest.yaml
cat << 'EOF' > config/productb_smoketest.yaml
# Example configuration for Product B - Smoke Tests
target_url: "https://api.productb.com/v2/trigger-smoke-suite"
http_method: "POST"

default_parameters:
  test_level: "smoke"
  priority: "high"

credential_env_keys:
  Authorization: "PRODUCT_B_API_TOKEN"
EOF

# config/README.md
cat << 'EOF' > config/README.md
# Configuration Files

This directory stores YAML configuration files for different products and test suite types.
The Temporal worker's `load_config_activity` reads these files to determine how to trigger a test suite.

## Naming Convention

Files should be named in the format: `productname_testsuitetype.yaml`.
For example:
- `producta_functional.yaml`
- `anotherproduct_smoketest.yaml`

The `productname` and `testsuitetype` should match the values provided by the user in the frontend dashboard (converted to lowercase).

## Structure

\`\`\`yaml
target_url: "string"  # REQUIRED: The URL of the test suite executor (e.g., Jenkins job, API endpoint)
http_method: "string" # REQUIRED: The HTTP method to use (e.g., "POST", "GET")

default_parameters: {}  # OPTIONAL: A dictionary of default parameters to send with the request.

credential_env_keys: {} # OPTIONAL: A dictionary mapping header names
                       # to the names of environment variables.
\`\`\`

### `target_url`
The full URL to which the HTTP request will be made.

### `http_method`
The HTTP method to use for the request, commonly "POST" or "GET".

### `default_parameters`
These are key-value pairs that will be sent as the JSON body for POST requests or as query parameters for GET requests by default.

### `credential_env_keys`
This is crucial for security. Instead of storing secrets directly in these config files, you store the *name* of the environment variable that holds the secret.
- The **key** in this dictionary is typically the HTTP Header name (e.g., `Authorization`, `X-API-Key`).
- The **value** is the name of the environment variable that the Temporal worker will read at runtime.
Make sure the corresponding environment variables are set in the environment where the Temporal worker is running.
EOF

# --- Frontend Setup ---
echo "Setting up frontend..."

# Create a temporary directory for our custom frontend files
mkdir -p template_frontend/public
mkdir -p template_frontend/src/components

# template_frontend/public/index.html
cat << 'EOF' > template_frontend/public/index.html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <link rel="icon" href="%PUBLIC_URL%/favicon.ico" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta name="theme-color" content="#000000" />
    <meta
      name="description"
      content="Test Suite Orchestrator Dashboard"
    />
    <link rel="apple-touch-icon" href="%PUBLIC_URL%/logo192.png" />
    <link rel="manifest" href="%PUBLIC_URL%/manifest.json" />
    <title>Test Orchestrator</title>
  </head>
  <body>
    <noscript>You need to enable JavaScript to run this app.</noscript>
    <div id="root"></div>
  </body>
</html>
EOF

# template_frontend/public/manifest.json
cat << 'EOF' > template_frontend/public/manifest.json
{
  "short_name": "TestOrchestrator",
  "name": "Test Suite Orchestrator Dashboard",
  "icons": [
    {
      "src": "favicon.ico",
      "sizes": "64x64 32x32 24x24 16x16",
      "type": "image/x-icon"
    }
  ],
  "start_url": ".",
  "display": "standalone",
  "theme_color": "#000000",
  "background_color": "#ffffff"
}
EOF

# template_frontend/src/index.tsx
cat << 'EOF' > template_frontend/src/index.tsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';

const root = ReactDOM.createRoot(
  document.getElementById('root') as HTMLElement
);
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
EOF

# template_frontend/src/App.tsx
cat << 'EOF' > template_frontend/src/App.tsx
import React from 'react';
import './App.css';
import TestRunnerForm from './components/TestRunnerForm';

function App() {
  return (
    <div className="App">
      <header className="App-header">
        <h1>Test Suite Orchestrator</h1>
      </header>
      <main>
        <TestRunnerForm />
      </main>
      <footer className="App-footer">
        <p>&copy; {new Date().getFullYear()} Test Orchestration System</p>
      </footer>
    </div>
  );
}

export default App;
EOF

# template_frontend/src/components/TestRunnerForm.tsx
cat << 'EOF' > template_frontend/src/components/TestRunnerForm.tsx
import React, { useState, FormEvent } from 'react';
import './TestRunnerForm.css';

interface FormData {
  csp: string;
  region: string;
  product: string;
  pod: string;
  environment: string;
  testsuite_type: string;
}

const cspOptions = ["AWS", "Azure", "GCP", "Other"];
const regionOptions = {
  AWS: ["us-east-1", "us-west-2", "eu-central-1"],
  Azure: ["East US", "West Europe", "Southeast Asia"],
  GCP: ["us-central1", "europe-west1", "asia-east1"],
  Other: ["N/A"],
};
const environmentOptions = ["dev", "staging", "prod", "uat"];
const testsuiteTypeOptions = ["smoke", "functional", "performance", "integration", "security"];

interface ApiResponseSuccess {
  message: string;
  workflow_id: string;
  run_id: string;
}

interface ApiResponseError {
  detail: string | { msg: string; type: string }[];
}

const TestRunnerForm: React.FC = () => {
  const [formData, setFormData] = useState<FormData>({
    csp: 'AWS',
    region: regionOptions['AWS'][0],
    product: 'DemoProduct',
    pod: '',
    environment: 'dev',
    testsuite_type: 'smoke',
  });
  const [responseMessage, setResponseMessage] = useState<string | null>(null);
  const [errorResponseMessage, setErrorResponseMessage] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData(prev => {
      const newState = { ...prev, [name]: value };
      if (name === 'csp') {
        const newCsp = value as keyof typeof regionOptions;
        newState.region = regionOptions[newCsp]?.[0] || '';
      }
      return newState;
    });
  };

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setIsLoading(true);
    setResponseMessage(null);
    setErrorResponseMessage(null);

    const apiUrl = '/api/trigger-test';

    try {
      const response = await fetch(apiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        body: JSON.stringify(formData),
      });

      if (!response.ok) {
        const errorData: ApiResponseError = await response.json();
        let detailMessage = "An unknown error occurred.";
        if (typeof errorData.detail === 'string') {
            detailMessage = errorData.detail;
        } else if (Array.isArray(errorData.detail)) {
            detailMessage = errorData.detail.map(err => `${err.type}: ${err.msg}`).join(', ');
        } else if (typeof errorData.detail === 'object' && errorData.detail !== null) {
            detailMessage = JSON.stringify(errorData.detail);
        }
        throw new Error(`HTTP error ${response.status}: ${detailMessage}`);
      }

      const result: ApiResponseSuccess = await response.json();
      setResponseMessage(`${result.message}. Workflow ID: ${result.workflow_id}, Run ID: ${result.run_id}`);

    } catch (error) {
      console.error("Submission error:", error);
      if (error instanceof Error) {
        setErrorResponseMessage(error.message);
      } else {
        setErrorResponseMessage("An unexpected error occurred during submission.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  const currentRegionOptions = regionOptions[formData.csp as keyof typeof regionOptions] || [];

  return (
    <div className="test-runner-form-container">
      <h2>Trigger New Test Suite</h2>
      <form onSubmit={handleSubmit} className="test-runner-form">
        <div className="form-group">
          <label htmlFor="csp">CSP:</label>
          <select id="csp" name="csp" value={formData.csp} onChange={handleChange} required>
            {cspOptions.map(option => <option key={option} value={option}>{option}</option>)}
          </select>
        </div>
        <div className="form-group">
          <label htmlFor="region">Region:</label>
          <select id="region" name="region" value={formData.region} onChange={handleChange} required disabled={currentRegionOptions.length === 0}>
            {currentRegionOptions.map(option => <option key={option} value={option}>{option}</option>)}
            {currentRegionOptions.length === 0 && <option value="">Select CSP first</option>}
          </select>
        </div>
        <div className="form-group">
          <label htmlFor="product">Product:</label>
          <input type="text" id="product" name="product" value={formData.product} onChange={handleChange} required placeholder="e.g., MyAwesomeApp"/>
        </div>
        <div className="form-group">
          <label htmlFor="pod">Pod (Optional):</label>
          <input type="text" id="pod" name="pod" value={formData.pod} onChange={handleChange} placeholder="e.g., pod-123a"/>
        </div>
        <div className="form-group">
          <label htmlFor="environment">Environment:</label>
          <select id="environment" name="environment" value={formData.environment} onChange={handleChange} required>
            {environmentOptions.map(option => <option key={option} value={option}>{option}</option>)}
          </select>
        </div>
        <div className="form-group">
          <label htmlFor="testsuite_type">Test Suite Type:</label>
          <select id="testsuite_type" name="testsuite_type" value={formData.testsuite_type} onChange={handleChange} required>
            {testsuiteTypeOptions.map(option => <option key={option} value={option}>{option}</option>)}
          </select>
        </div>
        <button type="submit" className="submit-button" disabled={isLoading}>
          {isLoading ? 'Submitting...' : 'Submit Test Suite'}
        </button>
      </form>
      {isLoading && <p className="loading-message">Submitting test workflow...</p>}
      {responseMessage && <div className="response-message success">{responseMessage}</div>}
      {errorResponseMessage && <div className="response-message error">{errorResponseMessage}</div>}
    </div>
  );
};
export default TestRunnerForm;
EOF

# template_frontend/src/App.css
cat << 'EOF' > template_frontend/src/App.css
.App {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  text-align: center;
  font-family: sans-serif;
  background-color: #f4f7f6;
}

.App-header {
  background-color: #282c34;
  padding: 20px 30px;
  color: white;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.App-header h1 {
    margin: 0;
    font-size: 1.8em;
}

main {
  flex-grow: 1;
  padding: 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  width: 100%;
  box-sizing: border-box;
}

.App-footer {
  background-color: #e9ecef;
  padding: 15px;
  text-align: center;
  font-size: 0.9em;
  color: #6c757d;
  margin-top: auto;
  border-top: 1px solid #dee2e6;
}
EOF

# template_frontend/src/index.css
cat << 'EOF' > template_frontend/src/index.css
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen',
    'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue',
    sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

code {
  font-family: source-code-pro, Menlo, Monaco, Consolas, 'Courier New',
    monospace;
}
EOF

# template_frontend/src/components/TestRunnerForm.css
cat << 'EOF' > template_frontend/src/components/TestRunnerForm.css
.test-runner-form-container {
  background-color: #ffffff;
  padding: 25px 30px;
  border-radius: 8px;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
  max-width: 550px;
  margin: 20px auto;
  border: 1px solid #e0e0e0;
}

.test-runner-form-container h2 {
  text-align: center;
  color: #333;
  margin-bottom: 25px;
  font-size: 1.5em;
}

.test-runner-form .form-group {
  margin-bottom: 18px;
}

.test-runner-form .form-group label {
  display: block;
  margin-bottom: 6px;
  font-weight: bold;
  color: #495057;
}

.test-runner-form .form-group input[type="text"],
.test-runner-form .form-group select {
  width: 100%;
  padding: 12px 15px;
  border: 1px solid #ced4da;
  border-radius: 4px;
  box-sizing: border-box;
  font-size: 1rem;
  transition: border-color 0.15s ease-in-out, box-shadow 0.15s ease-in-out;
}

.test-runner-form .form-group input[type="text"]:focus,
.test-runner-form .form-group select:focus {
  border-color: #80bdff;
  outline: 0;
  box-shadow: 0 0 0 0.2rem rgba(0,123,255,.25);
}

.submit-button {
  background-color: #007bff;
  color: white;
  padding: 12px 20px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 1.1rem;
  width: 100%;
  transition: background-color 0.2s ease-in-out;
  margin-top: 10px;
}

.submit-button:hover:not(:disabled) {
  background-color: #0056b3;
}

.submit-button:disabled {
  background-color: #6c757d;
  cursor: not-allowed;
}

.loading-message {
  text-align: center;
  margin-top: 15px;
  color: #495057;
}

.response-message {
  margin-top: 20px;
  padding: 12px 15px;
  border-radius: 4px;
  text-align: center;
  font-size: 1rem;
}

.response-message.success {
  background-color: #d4edda;
  color: #155724;
  border: 1px solid #c3e6cb;
}

.response-message.error {
  background-color: #f8d7da;
  color: #721c24;
  border: 1px solid #f5c6cb;
}
EOF

# Create React App
echo "Running create-react-app for frontend. This may take a few minutes..."
# Using --use-npm to ensure package-lock.json if that's preferred for consistency
# npx create-react-app frontend --template typescript --use-npm
# For faster local generation if CRA is cached, or for CI, this is fine:
npx create-react-app frontend --template typescript

# Copy our custom files into the CRA-generated frontend directory
echo "Copying custom frontend files into CRA structure..."
# -a preserves attributes, -v for verbose (optional)
# Using rsync is more robust for copying directories
rsync -av template_frontend/src/ frontend/src/
rsync -av template_frontend/public/ frontend/public/
# Or use cp:
# cp -R template_frontend/src/* frontend/src/
# cp -R template_frontend/public/* frontend/public/


# Clean up temporary frontend template directory
rm -rf template_frontend

# Create setupProxy.js for API proxying during development
echo "Creating frontend/src/setupProxy.js for API proxying..."
cat << 'EOF' > frontend/src/setupProxy.js
const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function(app) {
  app.use(
    '/api', // Match requests to /api
    createProxyMiddleware({
      target: 'http://localhost:8000', // Your FastAPI backend URL
      changeOrigin: true,
    })
  );
};
EOF
# Note: http-proxy-middleware needs to be in frontend's package.json dependencies.
# CRA will typically pick this up. If not, `npm install http-proxy-middleware` in frontend dir.
echo "NOTE: You might need to install http-proxy-middleware in the frontend directory:"
echo "cd frontend && npm install http-proxy-middleware && cd .."


# --- README.md (Root) ---
# This will be created in the next step by a separate subtask.

# --- Make script executable ---
chmod +x generate_project.sh

echo ""
echo "---------------------------------------------------------------------"
echo "Project generation complete!"
echo "---------------------------------------------------------------------"
echo ""
echo "Next Steps:"
echo ""
echo "1.  Review 'README.md' (will be created in the next step) for setup and run instructions."
echo "2.  Install frontend proxy dependency if prompted:"
echo "    cd frontend && npm install http-proxy-middleware && cd .."
echo "3.  Ensure Docker is running (for Temporal server)."
echo "4.  Set up .env files in 'backend/' and 'worker/' directories using the .env.example files as templates."
echo "5.  Follow instructions in README.md to start:"
echo "    - Temporal server"
echo "    - Backend API"
echo "    - Temporal Worker"
echo "    - Frontend application"
echo ""
echo "To run this script again, ensure you are in an empty directory or"
echo "remove existing 'frontend', 'backend', 'worker', 'config' directories first."
echo "---------------------------------------------------------------------"
