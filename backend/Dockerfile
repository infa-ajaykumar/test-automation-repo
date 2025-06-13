FROM python:3.10-slim

WORKDIR /app

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install system dependencies if any (e.g., for cryptography or other C extensions)
# RUN apt-get update && apt-get install -y some-package

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
# Use Gunicorn for a more production-ready setup than uvicorn alone for multiple workers.
# For simplicity with uvicorn for now:
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
# Production command with Gunicorn (install gunicorn in requirements.txt):
# CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "main:app", "--bind", "0.0.0.0:8000"]
