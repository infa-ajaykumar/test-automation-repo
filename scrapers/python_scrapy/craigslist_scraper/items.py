import scrapy

class PropertyListingItem(scrapy.Item):
    title = scrapy.Field()
    price = scrapy.Field()
    location = scrapy.Field()
    bedrooms = scrapy.Field()
    bathrooms = scrapy.Field() # Not always available directly, might need parsing
    area = scrapy.Field() # e.g., sqft
    images = scrapy.Field() # List of image URLs
    description = scrapy.Field()
    url = scrapy.Field() # URL of the original listing
    date_posted = scrapy.Field()

    # Added by pipeline
    source_site = scrapy.Field()
    scrape_timestamp = scrapy.Field()
