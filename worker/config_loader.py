import yaml
import os
import logging

# Configure basic logging for the loader
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Assume this script is in worker/, so config/ is one level up and then into config/
CONFIG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config"))

def load_yaml_config(product: str, testsuite_type: str) -> dict:
    """
    Loads YAML configuration for a given product and test suite type.
    The filename is expected to be in the format: product_testsuitetype.yaml (case-insensitive).
    Example: producta_functional.yaml
    """
    filename = f"{product.lower()}_{testsuite_type.lower()}.yaml"
    filepath = os.path.join(CONFIG_DIR, filename)

    logger.info(f"Attempting to load configuration from: {filepath}")

    if not os.path.exists(CONFIG_DIR):
        logger.error(f"Configuration directory not found: {CONFIG_DIR}")
        raise FileNotFoundError(f"Configuration directory not found: {CONFIG_DIR}")

    try:
        with open(filepath, 'r') as f:
            config_data = yaml.safe_load(f)
            if not isinstance(config_data, dict):
                logger.error(f"Invalid configuration format in {filepath}: Expected a dictionary.")
                raise ValueError(f"Invalid configuration format in {filepath}: Expected a dictionary.")
            logger.info(f"Successfully loaded configuration from {filepath}")
            return config_data
    except FileNotFoundError:
        logger.error(f"Configuration file not found: {filepath}")
        raise FileNotFoundError(f"Configuration file not found: {filepath}")
    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML file {filepath}: {e}")
        raise ValueError(f"Error parsing YAML file {filepath}: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred while loading {filepath}: {e}")
        raise
