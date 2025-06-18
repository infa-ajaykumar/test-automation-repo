import pika
import time
import json

def publish_message():
    # Give RabbitMQ some time to start
    time.sleep(10)

    try:
        credentials = pika.PlainCredentials('user', 'password')
        connection_params = pika.ConnectionParameters('rabbitmq', 5672, '/', credentials)
        connection = pika.BlockingConnection(connection_params)
        channel = connection.channel()

        queue_name = 'property_listings_raw'
        channel.queue_declare(queue=queue_name, durable=True) # Declare a durable queue

        message = {
            'title': 'Test Property',
            'price': '100000 USD',
            'location': 'Testville'
        }

        channel.basic_publish(
            exchange='',
            routing_key=queue_name,
            body=json.dumps(message),
            properties=pika.BasicProperties(
                delivery_mode=pika.spec.PERSISTENT_DELIVERY_MODE # Make message persistent
            )
        )
        print(f" [x] Sent {message}")
    except pika.exceptions.AMQPConnectionError as e:
        print(f"Error connecting to RabbitMQ: {e}")
        print("Make sure RabbitMQ is running. You can start it with: docker-compose up -d rabbitmq")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if 'connection' in locals() and connection.is_open:
            connection.close()

if __name__ == '__main__':
    publish_message()
