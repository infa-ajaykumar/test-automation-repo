# Full-Stack Test Suite Orchestrator

This project implements a full-stack application to trigger and monitor test suites using Temporal as the workflow orchestrator. It includes a React frontend, a FastAPI backend, and a Python Temporal worker.

## Project Structure

```
.
├── backend/            # FastAPI backend API
│   ├── main.py
│   ├── requirements.txt
│   └── .env.example
├── worker/             # Python Temporal worker
│   ├── main.py
│   ├── workflows.py
│   ├── activities.py
│   ├── config_loader.py
│   ├── requirements.txt
│   └── .env.example
├── config/             # YAML configurations for test suites
│   ├── producta_functional.yaml
│   ├── productb_smoketest.yaml
│   └── README.md
├── frontend/           # React + TypeScript frontend dashboard
│   ├── public/
│   ├── src/
│   │   ├── components/
│   │   │   └── TestRunnerForm.tsx
│   │   ├── App.tsx
│   │   ├── index.tsx
│   │   ├── App.css
│   │   ├── index.css
│   │   └── setupProxy.js  # For dev API proxying
│   ├── package.json
│   └── tsconfig.json
├── generate_project.sh # Script to generate this project structure
└── README.md           # This file
```

## Prerequisites

*   **Python**: 3.9 or higher.
*   **Node.js**: v18.x or v20.x (for React frontend). Includes npm.
*   **Docker**: Latest version (for running Temporal server).
*   **Git**: For cloning if obtained from a repository.

## Setup Instructions

1.  **Generate Project (If not already generated):**
    If you only have the `generate_project.sh` script, run it to create the full project structure:
    ```bash
    bash generate_project.sh
    ```
    This will create all necessary directories and files.

2.  **Set Up Environment Variables:**
    Copy the `.env.example` files in the `backend` and `worker` directories to `.env` and customize them:
    *   **Backend:**
        ```bash
        cp backend/.env.example backend/.env
        ```
        Edit `backend/.env` if your Temporal server is not at `localhost:7233`.
    *   **Worker:**
        ```bash
        cp worker/.env.example worker/.env
        ```
        Edit `worker/.env`.
        *   Ensure `TEMPORAL_SERVER_URL` is correct.
        *   **Crucially, provide actual values for the credential environment variables** (e.g., `PRODUCT_A_AUTH_TOKEN`, `PRODUCT_B_API_TOKEN`) based on the test systems you intend to trigger. These are referenced by the YAML files in the `config/` directory.

3.  **Install Dependencies:**

    *   **Backend API:**
        ```bash
        python -m venv backend/venv  # Create a virtual environment
        source backend/venv/bin/activate # Or backend\venv\Scripts\activate on Windows
        pip install -r backend/requirements.txt
        # Deactivate if you wish: deactivate
        ```

    *   **Temporal Worker:**
        ```bash
        python -m venv worker/venv
        source worker/venv/bin/activate # Or worker\venv\Scripts\activate on Windows
        pip install -r worker/requirements.txt
        # Deactivate if you wish: deactivate
        ```

    *   **Frontend Dashboard:**
        The `generate_project.sh` script runs `npx create-react-app`, which should install initial dependencies. However, `http-proxy-middleware` might need to be added for the development proxy to work:
        ```bash
        cd frontend
        npm install http-proxy-middleware
        # You can also run 'npm install' here to ensure all dependencies are fresh if needed
        cd ..
        ```

## Running the Application

You'll need to run four components: Temporal Server, Backend API, Temporal Worker, and Frontend.

**1. Start Temporal Server:**
   The easiest way to get a local Temporal server running for development is using Temporalite (a distribution of Temporal that runs as a single process with no dependencies) via Docker:
   ```bash
   docker run --rm -p 7233:7233 --name temporalite temporalio/temporalite:latest start --namespace default --ip 0.0.0.0
   ```
   Or, for a more persistent setup or if you prefer `auto-setup`:
   ```bash
   # docker run --rm -p 7233:7233 --name temporal temporalio/auto-setup:latest
   ```
   Keep this terminal window open. The server will be accessible at `localhost:7233`.

**2. Start the Backend API:**
   Open a new terminal.
   ```bash
   # If you created a venv for backend:
   source backend/venv/bin/activate # Or backend\venv\Scripts\activate on Windows

   uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
   ```
   The API will be available at `http://localhost:8000`. The `--reload` flag enables auto-reloading on code changes.

**3. Start the Temporal Worker:**
   Open another new terminal.
   ```bash
   # If you created a venv for worker:
   source worker/venv/bin/activate # Or worker\venv\Scripts\activate on Windows

   python -m worker.main
   ```
   The worker will connect to the Temporal server and start listening for tasks on the `test-suite-task-queue`. Ensure your `.env` file in the `worker` directory has the correct `TEMPORAL_SERVER_URL` and any required credential environment variables.

**4. Start the Frontend Application:**
   Open a final new terminal.
   ```bash
   cd frontend
   npm start
   ```
   This will start the React development server, typically opening the application in your default web browser at `http://localhost:3000`. The `setupProxy.js` file will ensure that API calls from the frontend (to `/api/...`) are proxied to the backend API running on port 8000.

## How to Use

1.  **Access the Dashboard:** Open `http://localhost:3000` in your web browser.
2.  **Fill the Form:**
    *   **CSP:** Select the Cloud Service Provider.
    *   **Region:** Select the region (options change based on CSP).
    *   **Product:** Enter the product name (e.g., `ProductA`, `ProductB`). This should match the prefix of a YAML file in the `config/` directory (case-insensitive).
    *   **Pod (Optional):** Enter a specific pod identifier if applicable.
    *   **Environment:** Select the target environment (e.g., `dev`, `staging`).
    *   **Testsuite Type:** Select the type of test suite (e.g., `functional`, `smoketest`). This should match the suffix of a YAML file in `config/` (case-insensitive).
3.  **Submit:** Click "Submit Test Suite".
4.  **Observe:**
    *   The frontend will display a message indicating the workflow has been initiated, along with a Workflow ID and Run ID.
    *   In the **Backend API terminal**, you'll see logs for the `/api/trigger-test` request and workflow start.
    *   In the **Temporal Worker terminal**, you'll see logs indicating the workflow and activities are being processed (config loading, HTTP call).
    *   The HTTP call specified in the corresponding `config/product_testsuite.yaml` will be made.
    *   The result of the HTTP call (success or error) will be the result of the workflow.
    *   You can use the Temporal Web UI (usually at `http://localhost:7233` for Temporalite, or `http://localhost:8088` for older `auto-setup`) to observe the workflow's progress and result.
    *   The frontend currently doesn't automatically poll for results, but the backend has an endpoint (`/api/workflow-result/{workflow_id}`) that can be used to check status.

## Development Notes

*   **Configuration:** To add new test suites or products, create new YAML files in the `config/` directory following the established naming convention and structure. Ensure corresponding credential environment variables are set for the worker if needed.
*   **Backend API Proxy:** The frontend uses a proxy (via `frontend/src/setupProxy.js`) to route API requests to the backend during development. This avoids CORS issues. In a production deployment, you would typically configure your web server (like Nginx) or cloud platform to handle this routing.
*   **Temporal UI:** For Temporalite, the UI is often bundled. For other setups, you might need to run the Temporal Web UI separately if not included. The default Temporalite image (`temporalio/temporalite`) serves the UI at `http://localhost:7233`.
