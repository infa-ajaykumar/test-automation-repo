import scrapy
from craigslist_scraper.items import PropertyListingItem
from urllib.parse import urljoin
import datetime

class ListingsSpider(scrapy.Spider):
    name = 'listings'
    # Example: New York City apartments for rent. Make this configurable later.
    start_urls = ['https://newyork.craigslist.org/d/apartments-housing-for-rent/search/apa']
    # To be more robust, we should handle different city subdomains and search paths.

    def parse(self, response):
        # Extract listing links from the main page
        listings = response.css('li.cl-static-search-result a.cl-app-anchor')
        for listing_link_tag in listings:
            # Extract title and link directly if possible, or follow to detail page
            # For craigslist, it's usually better to follow to the detail page
            href = listing_link_tag.attrib.get('href')
            if href:
                yield response.follow(href, self.parse_listing_detail)

        # Handle pagination
        next_page = response.css('nav.cl-pagination a.cl-next-page::attr(href)').get()
        if next_page is not None:
            yield response.follow(next_page, self.parse)

    def parse_listing_detail(self, response):
        item = PropertyListingItem()

        item['title'] = response.css('span#titletextonly::text').get('').strip()
        item['price'] = response.css('span.price::text').get('').strip() # Might need cleaning (e.g. remove '$')

        location_tag = response.css('div.mapAndAttrs small::text').get()
        item['location'] = location_tag.strip().replace('(', '').replace(')', '') if location_tag else None

        # Attributes like bedrooms, area are often in a group
        attrs = response.css('div.mapAndAttrs p.attrgroup span')
        bedrooms_text = None
        area_text = None
        for attr in attrs:
            attr_text = "".join(attr.css('::text').getall()).strip()
            if 'BR' in attr_text or 'br' in attr_text:
                bedrooms_text = attr_text
            elif 'ft2' in attr_text or 'm2' in attr_text: # or other area units
                area_text = attr_text

        item['bedrooms'] = bedrooms_text # Needs further parsing to get just number
        item['area'] = area_text # Needs further parsing for just number

        # Bathrooms are harder on CL, often in description or not listed
        item['bathrooms'] = None # Placeholder

        item['description'] = "".join(response.css('section#postingbody::text').getall()).strip()
        item['url'] = response.url

        date_posted_iso = response.css('time.date::attr(datetime)').get()
        item['date_posted'] = date_posted_iso

        image_urls = response.css('div.gallery img::attr(src)').getall()
        # CL images might be small initially, need to check if larger versions are available
        # For simplicity, taking what's directly available
        item['images'] = image_urls

        # These will be filled by the pipeline
        item['source_site'] = self.name # Or "Craigslist"
        item['scrape_timestamp'] = datetime.datetime.utcnow().isoformat()

        yield item
