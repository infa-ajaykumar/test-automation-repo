import pika
import time
import json

def consume_message():
    # Give RabbitMQ some time to start, especially if run immediately after docker-compose up
    time.sleep(10)

    try:
        credentials = pika.PlainCredentials('user', 'password')
        connection_params = pika.ConnectionParameters('rabbitmq', 5672, '/', credentials)
        connection = pika.BlockingConnection(connection_params)
        channel = connection.channel()

        queue_name = 'property_listings_raw'
        channel.queue_declare(queue=queue_name, durable=True) # Ensure queue exists and is durable

        print(' [*] Waiting for messages. To exit press CTRL+C')

        def callback(ch, method, properties, body):
            message = json.loads(body.decode())
            print(f" [x] Received {message}")
            # Acknowledge the message
            ch.basic_ack(delivery_tag=method.delivery_tag)
            # To stop consuming after one message for testing:
            # ch.stop_consuming()

        # Set prefetch_count to 1 to ensure that the worker only receives one message at a time
        # This is useful for fair dispatching if multiple consumers are running.
        channel.basic_qos(prefetch_count=1)
        channel.basic_consume(queue=queue_name, on_message_callback=callback)

        channel.start_consuming()

    except pika.exceptions.AMQPConnectionError as e:
        print(f"Error connecting to RabbitMQ: {e}")
        print("Make sure RabbitMQ is running. You can start it with: docker-compose up -d rabbitmq")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if 'connection' in locals() and connection.is_open:
            connection.close()

if __name__ == '__main__':
    consume_message()
