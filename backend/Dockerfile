# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /usr/src/app/api

# Install system dependencies that might be needed by psycopg2 or other packages
# For psycopg2, libpq-dev is often needed if not using a binary version or if it needs to compile
# However, psycopg2-binary should include precompiled binaries.
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     # libpq-dev # Example, if needed
#     && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt ./

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY main.py ./
# Add other .py files if you split the logic (e.g., into routers, models, services)

# Expose the port the app runs on
EXPOSE 8000

# The command to run when the container launches
# Uvicorn is a lightning-fast ASGI server, recommended for FastAPI
# Use 0.0.0.0 to bind to all interfaces, making it accessible from outside the container
# --reload is for development; remove or disable for production
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
# For production, you might use:
# CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"] # Example with 4 workers
