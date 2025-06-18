# Scraper Scheduler Service

This service is responsible for periodically triggering the scraper tasks (`craigslist_scraper` and `facebook_scraper`).

## Functionality

- Uses a shell script (`run_scrapers.sh`) that executes `docker compose run --rm <scraper_service>` for each configured scraper.
- Runs in an infinite loop with a defined sleep interval between cycles.
- The scheduler itself runs in a Docker container built from `scheduler/Dockerfile.scheduler`, which includes Docker CLI and bash.

## Configuration

- **Interval**: The scraping interval is defined in the `CMD` of `scheduler/Dockerfile.scheduler`. The default is 3600 seconds (1 hour).
  To change the interval:
  1. Modify the `sleep <seconds>\` value in the `CMD` line of `scheduler/Dockerfile.scheduler\`.
  2. Rebuild the scheduler image: `docker-compose build scheduler`
  3. Restart the scheduler service: `docker-compose up -d scheduler` (or restart all with `docker-compose up -d\`)

- **Scrapers to Run**: The list of scrapers to run is hardcoded in `scheduler/run_scrapers.sh`. To add/remove scrapers or change their order, modify this script.

## Running

This service starts automatically as part of `docker-compose up`.

To view logs:
```bash
docker-compose logs -f scheduler
```
The logs will show when each scraping cycle starts, which scrapers are triggered, and when the cycle ends before sleeping.
