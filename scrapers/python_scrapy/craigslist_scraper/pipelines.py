import pika
import json
import logging
import datetime

class RabbitMQPipeline:
    def __init__(self, rabbitmq_host, rabbitmq_port, rabbitmq_queue, rabbitmq_user, rabbitmq_pass):
        self.rabbitmq_host = rabbitmq_host
        self.rabbitmq_port = rabbitmq_port
        self.rabbitmq_queue = rabbitmq_queue
        self.rabbitmq_user = rabbitmq_user
        self.rabbitmq_pass = rabbitmq_pass
        self.connection = None
        self.channel = None

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            rabbitmq_host=crawler.settings.get('RABBITMQ_HOST', 'rabbitmq'),
            rabbitmq_port=crawler.settings.get('RABBITMQ_PORT', 5672),
            rabbitmq_queue=crawler.settings.get('RABBITMQ_QUEUE', 'property_listings_raw'),
            rabbitmq_user=crawler.settings.get('RABBITMQ_USER', 'user'),
            rabbitmq_pass=crawler.settings.get('RABBITMQ_PASS', 'password')
        )

    def open_spider(self, spider):
        try:
            credentials = pika.PlainCredentials(self.rabbitmq_user, self.rabbitmq_pass)
            self.connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=self.rabbitmq_host, port=self.rabbitmq_port, credentials=credentials, virtual_host='/')
            )
            self.channel = self.connection.channel()
            self.channel.queue_declare(queue=self.rabbitmq_queue, durable=True)
            logging.info("RabbitMQ connection opened.")
        except Exception as e:
            logging.error(f"Failed to connect to RabbitMQ: {e}")
            # Handle connection failure appropriately, maybe raise an exception
            # or set a flag to prevent processing if connection is critical.

    def close_spider(self, spider):
        if self.connection and self.connection.is_open:
            self.connection.close()
            logging.info("RabbitMQ connection closed.")

    def process_item(self, item, spider):
        if not self.channel or not self.connection or self.connection.is_closed:
            logging.error("RabbitMQ connection not available. Item not sent.")
            # Decide how to handle this: drop item, try to reconnect, etc.
            return item # Or raise DropItem

        try:
            # Add common fields if not already present (spider should ideally add them)
            item_dict = dict(item)
            item_dict.setdefault('source_site', spider.name) # Use spider name as default source
            item_dict.setdefault('scrape_timestamp', datetime.datetime.utcnow().isoformat())

            message_body = json.dumps(item_dict)
            self.channel.basic_publish(
                exchange='',
                routing_key=self.rabbitmq_queue,
                body=message_body,
                properties=pika.BasicProperties(
                    delivery_mode=pika.spec.PERSISTENT_DELIVERY_MODE,
                ))
            logging.debug(f"Item sent to RabbitMQ: {item['url']}")
        except Exception as e:
            logging.error(f"Failed to send item to RabbitMQ: {e}. Item: {item.get('url')}")
            # Handle publish failure
        return item
