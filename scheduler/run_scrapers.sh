#!/bin/bash
echo "-------------------------------------------"
echo "Scheduler: Triggering scrapers at $(date)"
echo "-------------------------------------------"

# Ensure we are in the project directory where docker-compose.yml is, if needed
# This script will be run from a Docker container that has the project root mounted.
# So, assuming docker-compose commands can be run directly if docker-compose.yml is in WORKDIR.
# Or, specify the project directory if mounted elsewhere. For now, assume current dir is fine.

echo "Triggering craigslist_scraper..."
# Using 'docker compose' (v2 syntax) instead of 'docker-compose' (v1)
# The container needs docker-cli and access to docker socket.
# Using `docker compose run` ensures it uses the services defined in the compose file.
docker compose run --rm craigslist_scraper
CRAIGSLIST_EXIT_CODE=$?
if [ $CRAIGSLIST_EXIT_CODE -eq 0 ]; then
    echo "Craigslist scraper finished successfully."
else
    echo "Craigslist scraper failed with exit code $CRAIGSLIST_EXIT_CODE."
fi

echo "Waiting for a bit before triggering the next scraper (e.g., 1 minute)..."
sleep 60

echo "Triggering facebook_scraper..."
docker compose run --rm facebook_scraper
FACEBOOK_EXIT_CODE=$?
if [ $FACEBOOK_EXIT_CODE -eq 0 ]; then
    echo "Facebook scraper finished successfully."
else
    echo "Facebook scraper failed with exit code $FACEBOOK_EXIT_CODE."
fi

echo "-------------------------------------------"
echo "Scheduler: Scraper runs finished at $(date)"
echo "-------------------------------------------"
