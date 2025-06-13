# test-automation-repo
test-automation-repo

## Security Considerations

### Secrets Management
- **Backend JWT Secret (`APP_SECRET_KEY`)**: The FastAPI backend uses a JWT secret key for signing access tokens. This **MUST** be set via the `APP_SECRET_KEY` environment variable in production to a strong, unique random string. The application will warn if a default development key is used.
- **Worker Secrets**: The Temporal worker requires various secrets for its operation:
    - SMTP server credentials (e.g., `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`) for email notifications.
    - API keys for services like Opsgenie (e.g., `OPSGENIE_FAILURE_API_KEY`).
    - Webhook URLs for services like Microsoft Teams (e.g., `TEAMS_WEBHOOK_CI_SUCCESS`).
- These secrets are typically configured as environment variables for the worker. Refer to `worker_config` definitions in `config/test_suites.yaml` (specifically `credential_keys` for test execution secrets, and notification configurations) to identify the environment variables you need to set for the worker based on your enabled test suites and notifications.
- **Never hardcode secrets in configuration files or source code.** Use environment variables, and in production, leverage secure secret management solutions provided by your deployment platform (e.g., Kubernetes Secrets, Docker Secrets, HashiCorp Vault, AWS Secrets Manager, Azure Key Vault, GCP Secret Manager) to inject these environment variables.

### HTTPS/TLS Enforcement
- All communication between the frontend, backend, and any external services (including the Temporal Web UI if exposed) **MUST** be over HTTPS/TLS in production.
- The FastAPI backend (`backend/main.py`) itself does not handle TLS termination in development. In a production environment, deploy it behind a reverse proxy (e.g., Nginx, Traefik, Caddy) or a cloud load balancer that is configured to handle TLS termination and enforce HTTPS.
- Ensure the `API_BASE_URL` (or `REACT_APP_API_BASE_URL` environment variable) for the frontend is set to the `https://` address of your backend in production.

### Input Validation
- The backend performs server-side validation of inputs using Pydantic models.
- Critical inputs like `cron_string` and `schedule_id` have specific format validations.
- Always ensure any new API endpoints rigorously validate incoming data.

### Dependency Vulnerability Scanning
- Regularly scan project dependencies for known vulnerabilities:
    - For the frontend (Node.js): `npm audit` or `yarn audit`.
    - For Python components (backend, worker): Use tools like `pip-audit` or `safety`.
- Integrate automated security scanning tools like GitHub Dependabot or Snyk into your development lifecycle.
- Keep dependencies updated to their latest secure versions.

### HTTP Security Headers
- For enhanced security, consider configuring your reverse proxy or application gateway to add security-related HTTP headers such as:
    - `Strict-Transport-Security` (HSTS)
    - `X-Content-Type-Options`
    - `X-Frame-Options`
    - `Content-Security-Policy` (CSP)
    - `Referrer-Policy`

### Role-Based Access Control (RBAC)
- The application implements RBAC with predefined roles (admin, editor, viewer). Ensure user roles are managed appropriately and principles of least privilege are followed.
- Sensitive operations are protected by role checks. Review these if you extend API functionality.
