import random
import logging
from scrapy.exceptions import NotConfigured

logger = logging.getLogger(__name__)

class RandomProxyMiddleware(object):
    def __init__(self, settings):
        self.proxies = settings.getlist('HTTP_PROXIES')
        if not self.proxies:
            # If no proxies are configured, this middleware will do nothing.
            # Scrapy will proceed without a proxy or use system-configured proxies if any.
            logger.info("No HTTP_PROXIES configured. RandomProxyMiddleware will not be active.")
            # Raise NotConfigured to disable the middleware if no proxies are set.
            # This is cleaner than letting it run and do nothing.
            raise NotConfigured("HTTP_PROXIES setting is empty or not found.")
        else:
            logger.info(f"RandomProxyMiddleware enabled with {len(self.proxies)} proxies.")

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler.settings)

    def process_request(self, request, spider):
        # This method is called for each request being processed.
        if not self.proxies: # Should not happen if NotConfigured is raised
            return

        # Don't override proxy if it's already set (e.g. by another middleware or specific request meta)
        if 'proxy' in request.meta:
            logger.debug(f"Proxy already set for {request.url}, not overriding.")
            return

        chosen_proxy = random.choice(self.proxies)
        request.meta['proxy'] = chosen_proxy
        logger.debug(f"Using proxy {chosen_proxy} for request {request.url}")

    def process_exception(self, request, exception, spider):
        # Called when a download handler or a process_request() method
        # (from this or other downloader middleware) raises an exception.
        proxy = request.meta.get('proxy')
        if proxy:
            logger.warning(f"Request {request.url} failed using proxy {proxy}. Exception: {exception}")
        # Depending on the exception type, you might want to retry with a different proxy,
        # or temporarily ban the failing proxy. For basic setup, just log.
        return None # Return None to let other exception handlers process it or Scrapy to fail the request.

# Placeholder for other middlewares if you had them, e.g.:
# class CraigslistScraperSpiderMiddleware:
#     ...
# class CraigslistScraperDownloaderMiddleware:
#     ...
