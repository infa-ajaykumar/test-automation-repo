# Use the official Puppeteer image which includes all necessary dependencies for Chrome
FROM ghcr.io/puppeteer/puppeteer:22.6.0

WORKDIR /usr/src/app/scraper
COPY package*.json ./
RUN npm install
COPY . .
CMD ["node", "scraper.js"]
