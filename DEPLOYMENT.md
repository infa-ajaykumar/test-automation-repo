# DEPLOYMENT.MD

This document provides guidance on deploying the containerized Full-Stack Test Orchestration Platform. The application consists of a Frontend (React/Nginx), Backend API (FastAPI), and a Temporal Worker (Python), along with a Temporal Server.

## Prerequisites

1.  **Docker**: Docker must be installed on your deployment targets or your local machine for building images.
2.  **Container Registry**: You'll need a container registry (e.g., Docker Hub, AWS ECR, Azure ACR, GCP Artifact Registry) to store your built Docker images if deploying to a multi-node environment like Kubernetes.
3.  **Temporal Server**: A running Temporal Server instance is required. See [Temporal Cluster Deployment Guides](https://docs.temporal.io/cluster-deployment-guide/overview) for production setup options (Kubernetes, Docker, etc.). For local testing, the `docker-compose.yml` included in this project provides a Temporal server.
4.  **Configuration Files**: The `config/` directory contains YAML files crucial for the application's behavior. Decide on your strategy for managing these in production:
    *   **Bake into images**: Copy them into the backend and worker images during their Docker build process (remove the `volumes` mount for `/app/config` in `docker-compose.yml` or your production deployment specs). This is simpler but requires image rebuilds for config changes.
    *   **Volume Mounts/ConfigMaps**: In environments like Kubernetes, mount these configuration files from ConfigMaps or persistent volumes into the backend and worker containers at `/app/config`. This allows config changes without rebuilding images.
    *   **Git Sync**: Have containers sync these files from a dedicated Git repository at startup (more complex, requires git tooling in containers and access credentials).

## Building Docker Images

Navigate to the project root directory where the `docker-compose.yml` is located.

1.  **Frontend Image**:
    ```bash
    docker build -t your-registry/test-orchestrator-frontend:latest -f frontend/Dockerfile ./frontend
    ```
    *   **Build-time Configuration**: You can set the backend API URL at build time:
        ```bash
        docker build --build-arg REACT_APP_API_BASE_URL=https://your-backend-api.example.com/api -t your-registry/test-orchestrator-frontend:latest -f frontend/Dockerfile ./frontend
        ```

2.  **Backend API Image**:
    ```bash
    docker build -t your-registry/test-orchestrator-backend:latest -f backend/Dockerfile ./backend
    ```

3.  **Temporal Worker Image**:
    ```bash
    docker build -t your-registry/test-orchestrator-worker:latest -f worker/Dockerfile ./worker
    ```

4.  **(Optional) Push to Registry**:
    ```bash
    docker push your-registry/test-orchestrator-frontend:latest
    docker push your-registry/test-orchestrator-backend:latest
    docker push your-registry/test-orchestrator-worker:latest
    ```

## Deployment Strategies

The following are general guidelines. Specifics will vary based on your chosen platform.

### 1. Docker Compose (for Single-Node or Advanced Local/Test)

The provided `docker-compose.yml` can be adapted for a single-node production-like deployment, but ensure:
-   You are **NOT** using the `temporalio/auto-setup` image for a production Temporal server. Deploy Temporal robustly.
-   Environment variables (especially secrets) in `docker-compose.yml` are placeholders. Manage production secrets securely, e.g., using Docker secrets or by injecting them from a secure source if your Docker environment supports it.
-   Consider removing the local `./config` volume mounts and baking configs into the images or using Docker named volumes with pre-populated config data for backend and worker.

### 2. Kubernetes (Recommended for Scalability & Resilience)

-   **Temporal Server**: Deploy a production-grade Temporal cluster, typically using the [Temporal Helm Charts](https://github.com/temporalio/helm-charts) or the Temporal Operator.
-   **Application Components**:
    *   Create Kubernetes `Deployment` manifests for the frontend, backend, and worker.
    *   Use `Service` manifests to expose the frontend and backend.
    *   Use `Ingress` (with an Ingress controller like Nginx or Traefik) to manage external access to the frontend and backend, handle HTTPS termination, and potentially path-based routing.
    *   **Configuration (`config/` files)**:
        *   Store YAML files from the `config/` directory in Kubernetes `ConfigMap` resources.
        *   Mount these ConfigMaps into the backend and worker pods at `/app/config`.
    *   **Environment Variables & Secrets**:
        *   Store non-sensitive environment variables in `ConfigMap`s or directly in Deployment specs.
        *   Store all sensitive secrets (e.g., `APP_SECRET_KEY`, SMTP passwords, API keys for notifications, `credential_keys` values) in Kubernetes `Secret` resources.
        *   Mount these secrets as environment variables into the backend and worker pods.
    *   **Scaling**: Configure `HorizontalPodAutoscaler` (HPA) for the backend and worker deployments based on CPU/memory or custom metrics. The frontend is typically scaled by increasing replicas if serving static content.

### 3. Cloud-Specific Container Services

(e.g., AWS ECS, Azure Container Apps, Google Cloud Run)

-   **Temporal Server**: Deploy Temporal separately (e.g., on EC2/VMs with Docker, or using a managed Temporal service if available). Ensure it's network-accessible to your container services.
-   **Application Components**:
    *   Push your built Docker images to your cloud provider's container registry (ECR, ACR, Artifact Registry).
    *   Define "Task Definitions" (ECS), "Container Apps" (Azure), or "Services" (Cloud Run) for each component (frontend, backend, worker).
    *   **Configuration (`config/` files)**:
        *   Similar to Kubernetes, you might bake configs into images or mount them from a service like AWS S3 (requiring an entrypoint script in the container to fetch them), Azure Files, or by injecting them as environment variables if they are small enough (less ideal for structured YAML).
    *   **Environment Variables & Secrets**: Use the cloud provider's integrated secret management (AWS Secrets Manager, Azure Key Vault, GCP Secret Manager) to store and inject secrets as environment variables into your container instances.
    *   **Networking & Load Balancing**:
        *   Configure load balancers (ALB, Application Gateway, Cloud Load Balancing) to expose the frontend and backend services.
        *   Ensure HTTPS termination is handled at the load balancer level.

## Environment Variable Configuration (Summary)

Refer to the `.env.example` files (if created) or the `docker-compose.yml` for a list of critical environment variables.

### Backend (`your-registry/test-orchestrator-backend`)
-   `APP_SECRET_KEY`: **CRITICAL** - JWT signing key.
-   `TEMPORAL_SERVER_ADDRESS`: Address of your Temporal gRPC frontend (e.g., `your-temporal-frontend.namespace.svc.cluster.local:7233` or `localhost:7233`).
-   (Potentially database connection strings if not using SQLite via volume).

### Worker (`your-registry/test-orchestrator-worker`)
-   `TEMPORAL_SERVER_ADDRESS`: Address of your Temporal gRPC frontend.
-   `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_SENDER_EMAIL`, `SMTP_USE_TLS`: For email notifications.
-   `TEAMS_WEBHOOK_...`: Specific Teams webhook URLs (e.g., `TEAMS_WEBHOOK_CI_SUCCESS`).
-   `OPSGENIE_..._API_KEY`: Specific Opsgenie API keys.
-   `OPSGENIE_API_URL`: (Optional) Override Opsgenie API endpoint.
-   Any environment variables referenced by `credential_keys` in your `config/test_suites.yaml` files (e.g., `PROD_A_LOGIN_JENKINS_TOKEN_VAR`).

### Frontend (`your-registry/test-orchestrator-frontend`)
-   `REACT_APP_API_BASE_URL`: (Typically set at build time or via Nginx config) The base URL for the backend API.
-   Nginx within the container can be further configured via its own config files if more advanced serving logic is needed (e.g., runtime environment variable injection into JS, though this is complex for static builds).

## Reverse Proxy for Backend (HTTPS Termination)

Regardless of the deployment platform (except perhaps simple Docker Compose on a trusted local network), the backend API should be served via a reverse proxy that handles HTTPS termination.

**Example Nginx Reverse Proxy Snippet (conceptual):**
```nginx
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name your-api-domain.example.com;

    ssl_certificate /path/to/your/fullchain.pem;
    ssl_certificate_key /path/to/your/privkey.pem;
    # ... other SSL/TLS settings (protocols, ciphers, HSTS) ...

    location /api/ { # Assuming your backend serves under /api/
        proxy_pass http://<backend_internal_ip_or_service_name>:<backend_port>/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        # Add other necessary proxy headers
    }
}
```
This proxy would typically run on a separate machine/container or be a service provided by your cloud platform/Ingress controller.

## Final Checks
- Ensure network policies/firewall rules allow communication:
    - Frontend to Backend API.
    - Backend API to Temporal Server.
    - Worker to Temporal Server.
    - Worker to external services (Jenkins, SMTP, Teams, Opsgenie).
- Monitor application logs from all components.
- Set up appropriate resource requests and limits for your containers in orchestrated environments.
