#!/bin/bash
# generate_project_structure.sh

echo "Generating project structure for Test Orchestration Platform..."

# Create root directories
mkdir -p frontend/public frontend/src/components frontend/src/contexts frontend/src/services
mkdir -p backend
mkdir -p worker
mkdir -p config

# --- Root Files ---
echo "# Test Orchestration Platform - Full Stack" > README.md
echo "Comprehensive full-stack test orchestration platform..." >> README.md
# Add more to main README.md if needed, like links to component READMEs, DEPLOYMENT.md
echo "See [DEPLOYMENT.md](DEPLOYMENT.md) for deployment instructions." >> README.md
echo "Created README.md"

# DEPLOYMENT.md - use existing if available, otherwise placeholder
if [ -f "DEPLOYMENT.md" ]; then
    echo "DEPLOYMENT.md already exists, not overwriting with placeholder."
else
    echo "# DEPLOYMENT.md - Placeholder" > DEPLOYMENT.md
    echo "Deployment instructions will be detailed here." >> DEPLOYMENT.md
    echo "Created DEPLOYMENT.md (placeholder)"
fi

# docker-compose.yml - use existing if available, otherwise placeholder
if [ -f "docker-compose.yml" ]; then
    echo "docker-compose.yml already exists, not overwriting with placeholder."
else
    echo "# docker-compose.yml - Placeholder" > docker-compose.yml
    echo "version: '3.8'" >> docker-compose.yml
    echo "services:" >> docker-compose.yml
    echo "  # Define frontend, backend, worker, temporal services here" >> docker-compose.yml
    echo "Created docker-compose.yml (placeholder)"
fi


# --- Frontend ---
echo "Setting up frontend..."
# package.json (basic placeholder, actual one is extensive)
cat << EOF > frontend/package.json
{
  "name": "frontend",
  "version": "0.1.0",
  "private": true,
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-scripts": "5.0.1",
    "axios": "^1.2.6",
    "react-router-dom": "^6.8.1",
    "@types/jest": "^27.5.2",
    "@types/node": "^16.18.11",
    "@types/react": "^18.0.27",
    "@types/react-dom": "^18.0.10",
    "typescript": "^4.9.5"
  },
  "scripts": {
    "start": "react-scripts start",
    "build": "react-scripts build",
    "test": "react-scripts test",
    "eject": "react-scripts eject"
  },
  "eslintConfig": { "extends": ["react-app", "react-app/jest"] },
  "browserslist": {
    "production": [">0.2%", "not dead", "not op_mini all"],
    "development": ["last 1 chrome version", "last 1 firefox version", "last 1 safari version"]
  }
}
EOF
echo "Created frontend/package.json"

# tsconfig.json (basic placeholder)
cat << EOF > frontend/tsconfig.json
{
  "compilerOptions": {
    "target": "es5", "lib": ["dom", "dom.iterable", "esnext"], "allowJs": true,
    "skipLibCheck": true, "esModuleInterop": true, "allowSyntheticDefaultImports": true,
    "strict": true, "forceConsistentCasingInFileNames": true, "noFallthroughCasesInSwitch": true,
    "module": "esnext", "moduleResolution": "node", "resolveJsonModule": true,
    "isolatedModules": true, "noEmit": true, "jsx": "react-jsx"
  },
  "include": ["src"]
}
EOF
echo "Created frontend/tsconfig.json"

echo "# Frontend" > frontend/README.md
echo "Instructions for frontend setup and development." >> frontend/README.md
echo "Created frontend/README.md"

# Placeholder for Dockerfile & nginx.conf as they are more complex
echo "# Dockerfile for frontend" > frontend/Dockerfile
echo "FROM node:18-alpine AS build..." >> frontend/Dockerfile
echo "Created frontend/Dockerfile (placeholder)"
echo "# nginx.conf for frontend SPA" > frontend/nginx.conf
echo "server { listen 80; ... }" >> frontend/nginx.conf
echo "Created frontend/nginx.conf (placeholder)"

# Basic src structure
echo "// frontend/src/index.tsx - Main entry point" > frontend/src/index.tsx
echo "import React from 'react';" >> frontend/src/index.tsx
echo "import ReactDOM from 'react-dom/client';" >> frontend/src/index.tsx
echo "import App from './App';" >> frontend/src/index.tsx
echo "const root = ReactDOM.createRoot(document.getElementById('root') as HTMLElement);" >> frontend/src/index.tsx
echo "root.render(<React.StrictMode><App /></React.StrictMode>);" >> frontend/src/index.tsx
echo "Created frontend/src/index.tsx"

echo "// frontend/src/App.tsx - Main application component" > frontend/src/App.tsx
echo "import React from 'react';" >> frontend/src/App.tsx
echo "function App() { return (<h1>Test Orchestrator Frontend</h1>); }" >> frontend/src/App.tsx
echo "export default App;" >> frontend/src/App.tsx
echo "Created frontend/src/App.tsx"

echo "/* frontend/src/App.css - Main app styles */" > frontend/src/App.css
echo "/* frontend/src/index.css - Global styles */" > frontend/src/index.css
echo "<!DOCTYPE html><html><head><title>Frontend</title></head><body><div id=\"root\"></div></body></html>" > frontend/public/index.html
touch frontend/public/favicon.ico
echo "Created basic frontend/src files and public/index.html"

# --- Backend ---
echo "Setting up backend..."
echo "# Backend API" > backend/README.md
echo "Instructions for backend setup and development." >> backend/README.md
echo "Created backend/README.md"
echo "fastapi
uvicorn[standard]
pydantic
PyYAML
python-multipart
temporalio
passlib[bcrypt]
PyJWT
httpx" > backend/requirements.txt
echo "Created backend/requirements.txt"
echo "# Dockerfile for backend" > backend/Dockerfile
echo "FROM python:3.10-slim..." >> backend/Dockerfile
echo "Created backend/Dockerfile (placeholder)"
echo "# backend/main.py - FastAPI application" > backend/main.py
echo "from fastapi import FastAPI" >> backend/main.py
echo "app = FastAPI(title='Backend API')" >> backend/main.py
echo "@app.get('/')" >> backend/main.py
echo "async def root(): return {'message': 'Backend API for Test Orchestrator'}" >> backend/main.py
echo "Created backend/main.py"

# --- Worker ---
echo "Setting up worker..."
echo "# Temporal Worker" > worker/README.md
echo "Instructions for worker setup and development." >> worker/README.md
echo "Created worker/README.md"
echo "temporalio
PyYAML
httpx" > worker/requirements.txt
echo "Created worker/requirements.txt"
echo "# Dockerfile for worker" > worker/Dockerfile
echo "FROM python:3.10-slim..." >> worker/Dockerfile
echo "Created worker/Dockerfile (placeholder)"
echo "# worker/run_worker.py - Temporal worker script" > worker/run_worker.py
echo "import asyncio" >> worker/run_worker.py
echo "async def main(): print('Worker starting...') # Add actual worker logic here" >> worker/run_worker.py
echo "if __name__ == '__main__': asyncio.run(main())" >> worker/run_worker.py
echo "Created worker/run_worker.py"

# --- Config ---
echo "Setting up config..."
echo "# Configuration Files" > config/README.md
echo "YAML configuration files for products, test suites, etc." >> config/README.md
echo "Created config/README.md"

echo "- id: \"example_product\"
  name: \"Example Product Alpha\"
  description: \"Manages customer data and analytics.\"
  test_suites:
    - \"suite_login\"
    - \"suite_data_processing\"" > config/products.yaml
echo "Created config/products.yaml"

echo "- id: \"suite_login\"
  name: \"Login and Authentication Tests\"
  description: \"Tests user login, logout, and session management.\"
  product_ids: [\"example_product\"]
  inputs:
    - name: \"username\"
      label: \"Test Username\"
      type: \"text\"
      required: true
  worker_config:
    type: \"http_post\"
    target_url_template: \"http://example.com/test/login\"
    payload_template:
      USERNAME: \"{username}\"
      TOKEN: \"{SECRET:TEST_TOKEN}\"
    credential_keys:
      TEST_TOKEN: \"ENV_VAR_FOR_TEST_TOKEN\"" > config/test_suites.yaml
echo "Created config/test_suites.yaml"


echo ""
echo "Project structure generation complete."
echo "Note: This script creates a basic structure with placeholder content for many files."
echo "The actual project contains much more detailed implementations."
echo "Run 'chmod +x generate_project_structure.sh' to make this script executable."
