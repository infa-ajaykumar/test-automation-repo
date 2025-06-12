from temporalio import activity
import yaml
from pathlib import Path
from typing import Dict, Any, List

CONFIG_PATH = Path("../config") # Relative to worker directory

@activity.defn
async def load_config_file(config_name: str) -> List[Dict[str, Any]]:
    activity.logger.info(f"Loading configuration file: {config_name}.yaml")
    allowed_configs = ["csps", "regions", "environments", "products", "test_suites"]
    if config_name not in allowed_configs:
        activity.logger.error(f"Configuration type '{config_name}' not allowed.")
        raise ValueError(f"Configuration type '{config_name}' not allowed. Allowed types: {', '.join(allowed_configs)}")
    file_path = CONFIG_PATH / f"{config_name}.yaml"
    if not file_path.exists() or not file_path.is_file():
        activity.logger.error(f"Configuration file {config_name}.yaml not found at {file_path}.")
        raise FileNotFoundError(f"Configuration file {config_name}.yaml not found at {file_path}.")
    try:
        with open(file_path, 'r') as f:
            config_data = yaml.safe_load(f)
            if config_data is None:
                return []
            if not isinstance(config_data, list):
                 activity.logger.error(f"Configuration file {config_name}.yaml is not in the expected list format.")
                 raise ValueError(f"Configuration file {config_name}.yaml is not in the expected list format.")
            activity.logger.info(f"Successfully loaded {config_name}.yaml")
            return config_data
    except yaml.YAMLError as e:
        activity.logger.error(f"Error parsing YAML file {config_name}.yaml: {e}")
        raise ValueError(f"Error parsing YAML file {config_name}.yaml: {e}")
    except Exception as e:
        activity.logger.error(f"An unexpected error occurred while reading {config_name}.yaml: {e}")
        raise RuntimeError(f"An unexpected error occurred while reading {config_name}.yaml: {str(e)}")

@activity.defn
async def get_test_suite_config(suite_id: str) -> Dict[str, Any]:
    activity.logger.info(f"Attempting to find test suite config for ID: {suite_id}")
    test_suites_config = await load_config_file("test_suites")
    for suite in test_suites_config:
        if suite.get("id") == suite_id:
            activity.logger.info(f"Found test suite config for ID: {suite_id}")
            return suite
    activity.logger.error(f"Test suite with ID '{suite_id}' not found in test_suites.yaml.")
    raise ValueError(f"Test suite with ID '{suite_id}' not found in test_suites.yaml.")
