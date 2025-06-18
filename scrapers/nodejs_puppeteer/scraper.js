const puppeteer = require('puppeteer');
const amqp = require('amqplib');

// Note: For authenticated proxies with Puppeteer (e.g., user:pass@host:port),
// simple --proxy-server arg might not work. It often requires page.authenticate()
// or using a library like puppeteer-extra with puppeteer-extra-plugin-proxy.
const PROXY_SERVER_ENV = process.env.PUPPETEER_PROXY_SERVER; // e.g., 'http://proxy-ip:port' or 'socks5://proxy-ip:port'

const RABBITMQ_URL = 'amqp://user:password@rabbitmq:5672'; // Matches docker-compose
const QUEUE_NAME = 'property_listings_raw';

// --- Configuration ---
const TARGET_URL = 'https://www.facebook.com/marketplace/boston/search/?query=apartment%20for%20rent';
// const TARGET_URL = 'https://www.facebook.com/marketplace/category/propertyrentals';

const SCROLL_ATTEMPTS = 5;
const SCROLL_DELAY = 3000;
const ITEMS_TO_SCRAPE_LIMIT = 20;

async function sendToQueue(data) {
    let connection;
    try {
        connection = await amqp.connect(RABBITMQ_URL);
        const channel = await connection.createChannel();
        await channel.assertQueue(QUEUE_NAME, { durable: true });

        const message = {
            ...data,
            source_site: 'Facebook Marketplace',
            scrape_timestamp: new Date().toISOString()
        };
        channel.sendToQueue(QUEUE_NAME, Buffer.from(JSON.stringify(message)), { persistent: true });
        console.log(`[x] Sent '${data.title ? data.title.substring(0,30) : 'N/A'}' to queue`);
        await channel.close();
    } catch (error) {
        console.error('Error sending to RabbitMQ:', error);
    } finally {
        if (connection) await connection.close();
    }
}

async function scrapeFacebookMarketplace() {
    console.log('Launching browser...');
    const browser = await puppeteer.launch({
        headless: true,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-infobars',
            '--window-position=0,0',
            '--ignore-certifcate-errors',
            '--ignore-certifcate-errors-spki-list',
            '--user-agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.85 Safari/537.36"',
            '--disable-blink-features=AutomationControlled',
            PROXY_SERVER_ENV ? `--proxy-server=${PROXY_SERVER_ENV}` : '',
        ].filter(Boolean) // Filter out empty strings from args list
    });

    const page = await browser.newPage();
    await page.setExtraHTTPHeaders({ 'Accept-Language': 'en-US,en;q=0.9' });
    await page.setViewport({ width: 1280, height: 800 });

    console.log(`Navigating to ${TARGET_URL}...`);
    try {
        await page.goto(TARGET_URL, { waitUntil: 'networkidle2', timeout: 60000 });
    } catch (e) {
        console.error(`Timeout or error navigating to ${TARGET_URL}: ${e.message}`);
        await page.screenshot({ path: 'error_screenshot.png' });
        console.log('Screenshot saved to error_screenshot.png due to navigation error.');
        await browser.close();
        return;
    }

    console.log('Page loaded. Starting scrape attempt...');
    const itemLinkSelector = 'a[href*="/marketplace/item/"]';
    let itemsScraped = 0;

    try {
        for (let i = 0; i < SCROLL_ATTEMPTS; i++) {
            console.log(`Scrolling attempt ${i + 1}/${SCROLL_ATTEMPTS}...`);
            await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
            await new Promise(resolve => setTimeout(resolve, SCROLL_DELAY));
        }

        await page.waitForSelector(itemLinkSelector, { timeout: 15000 }).catch(() => {
            console.log("No item links found. FB structure might have changed or page didn't load as expected.");
        });

        const listingLinks = await page.$$eval(itemLinkSelector, anchors =>
            anchors.map(a => a.href).filter((href, index, self) => self.indexOf(href) === index)
        );

        console.log(`Found ${listingLinks.length} potential listing links.`);

        for (const link of listingLinks) {
            if (itemsScraped >= ITEMS_TO_SCRAPE_LIMIT) break;
            console.log(`Scraping detail page: ${link}`);
            const itemPage = await browser.newPage();
            await itemPage.setViewport({ width: 1280, height: 800 });
            await itemPage.setExtraHTTPHeaders({ 'Accept-Language': 'en-US,en;q=0.9' });
            await itemPage.setUserAgent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.85 Safari/537.36");

            try {
                await itemPage.goto(link, { waitUntil: 'networkidle2', timeout: 45000 });

                // Selectors are placeholders - WILL LIKELY FAIL without adjustment
                let title = await itemPage.$eval('span[dir="auto"]:not([class])', el => el.textContent.trim()).catch(() => 'N/A');
                let price = 'N/A';
                try {
                    const priceElements = await itemPage.$$('span');
                    for (const el of priceElements) {
                        const text = await itemPage.evaluate(element => element.textContent, el);
                        if (text && text.includes('$') && text.length < 30) { // Basic heuristic for price
                            price = text.trim();
                            break;
                        }
                    }
                } catch (e) { /* Price not found */ }

                let location = 'N/A';
                // Crude location attempt, needs proper selectors or smarter logic
                try {
                     const spans = await itemPage.$$eval('span', els => els.map(el => el.innerText));
                     for (let s of spans) {
                        if (s.length > 5 && s.length < 50 && !s.includes('$') && !s.includes('Posted') && !s.includes('ago')) {
                            // This is a weak heuristic, might pick up random text
                            // A better way would be to look for spans near a map pin icon or with certain keywords.
                            // For example: const locationText = await itemPage.$eval('div[aria-label="Location"] span', el => el.textContent);
                            // This is a placeholder and needs verification.
                            location = s.trim();
                            break;
                        }
                     }
                } catch (e) { /* location not found */ }


                let description = 'N/A';
                try {
                    // Trying to find a larger block of text for description
                    const potentialDescriptions = await itemPage.$$eval('div[data-ad-preview="message"] span[dir="auto"], div > span[dir="auto"]', spans => spans.map(s => s.textContent.trim()));
                    description = potentialDescriptions.find(d => d.length > 50) || 'N/A';
                } catch (e) { /* description not found */ }


                let images = await itemPage.$$eval('img[data-imgperflogname="marketplacePhotoGrid"], img[alt*="Photo"]', imgs => imgs.map(img => img.src)).catch(() => []);

                const propertyData = {
                    title, price, location, images, description, url: link,
                    bedrooms: null, bathrooms: null, area: null, date_posted: null
                };

                console.log('Scraped data:', propertyData.title ? propertyData.title.substring(0,30) : 'N/A');
                await sendToQueue(propertyData);
                itemsScraped++;

            } catch (itemError) {
                console.error(`Error scraping item page ${link}: ${itemError.message}`);
                await itemPage.screenshot({ path: 'error_screenshot_item.png' });
            } finally {
                await itemPage.close();
            }
        }
    } catch (error) {
        console.error('Error during scraping process:', error);
        await page.screenshot({ path: 'error_screenshot_main.png' });
        console.log('Screenshot saved to error_screenshot_main.png');
    } finally {
        console.log('Closing browser...');
        await browser.close();
    }
}

scrapeFacebookMarketplace().catch(e => {
    console.error("Unhandled rejection in scrapeFacebookMarketplace:", e);
    // Attempt to take a screenshot if possible, though page context might be lost
    // This is a fallback.
    // if (global.page) { // Assuming page is made global or passed around for this
    //     global.page.screenshot({ path: 'unhandled_error_screenshot.png' })
    //         .then(() => console.log('Screenshot taken for unhandled error.'))
    //         .catch(ssError => console.error('Could not take screenshot for unhandled error:', ssError));
    // }
});
