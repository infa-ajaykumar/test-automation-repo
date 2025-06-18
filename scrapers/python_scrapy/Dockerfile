# Use an official Python runtime as a parent image
FROM python:3.9-slim

WORKDIR /usr/src/app/scraper

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# If scrapy.cfg is in python_scrapy/ and craigslist_scraper is in python_scrapy/craigslist_scraper/
# And the Docker build context is python_scrapy/
COPY scrapy.cfg ./
COPY craigslist_scraper ./craigslist_scraper

CMD ["scrapy", "crawl", "listings"]
