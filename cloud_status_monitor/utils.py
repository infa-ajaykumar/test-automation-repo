import configparser
import os
import json # Added json import
import subprocess # Added for run_test
import logging # Added for logging
import logging.handlers # For RotatingFileHandler

def setup_logging(log_file_path="monitor.log", level="INFO", for_utils=False):
    """
    Sets up logging to console and a rotating file.
    """
    logger_name = "utils_self_test" if for_utils else "cloud_monitor"
    logger = logging.getLogger(logger_name)

    # Avoid duplicate handlers if called multiple times for the main logger
    # For utils_self_test, we always want a fresh setup for clarity during tests.
    if logger.hasHandlers() and not for_utils:
        # This check might be too simple if handlers could be different.
        # A more robust way is to clear existing handlers if re-configuration is desired.
        # For now, assume if it has handlers, it's already configured.
        return logger

    # If for_utils, handlers might be added multiple times if this function is called repeatedly within test.
    # Clear existing handlers for the utils_self_test logger to ensure clean setup each time.
    if for_utils and logger.hasHandlers():
        logger.handlers = []

    # Ensure path is relative to project root (cloud_status_monitor) for the main app
    # This assumes utils.py is in cloud_status_monitor directory
    if not os.path.isabs(log_file_path) and not for_utils:
        # Assuming utils.py is in cloud_status_monitor
        project_root = os.path.dirname(os.path.abspath(__file__))
        log_file_path = os.path.join(project_root, log_file_path)
    elif not os.path.isabs(log_file_path) and for_utils:
        # For utils.py self-test, if a relative path is given,
        # it's relative to where utils.py is run from.
        # If utils.py is run from /app, then "utils_test.log" is /app/utils_test.log.
        # If utils.py is run from /app/cloud_status_monitor, then it's /app/cloud_status_monitor/utils_test.log
        # This is fine for a self-contained test log.
        pass

    log_level_obj = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(log_level_obj)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Console Handler
    ch = logging.StreamHandler()
    ch.setLevel(log_level_obj)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # File Handler (Rotating)
    if not for_utils:
        try:
            log_dir = os.path.dirname(log_file_path)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)

            rfh = logging.handlers.RotatingFileHandler(
                log_file_path, maxBytes=5*1024*1024, backupCount=3 # 5MB per file, 3 backups
            )
            rfh.setLevel(log_level_obj)
            rfh.setFormatter(formatter)
            logger.addHandler(rfh)
        except Exception as e:
            # Use a basic print here if logger itself fails for file handler
            print(f"CRITICAL: Failed to set up file logging to {log_file_path}: {e}")
            if logger.hasHandlers(): # If console handler was added, use it
                 logger.error(f"Failed to set up file logging to {log_file_path}", exc_info=True)
    elif for_utils: # Explicitly state for clarity when testing utils itself
        logger.debug("Skipping file handler setup because for_utils is True.")


    return logger

# Functions load_settings, load_service_map, run_test remain unchanged for now
# as per instruction "can continue using print for their direct error reporting"

def load_settings(config_path="config/settings.ini"):
    """
    Loads settings from the given INI file.
    Returns a dictionary of settings or None if file not found.
    """
    # Ensure the path is relative to the script's directory if not absolute
    if not os.path.isabs(config_path):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, config_path)

    if not os.path.exists(config_path):
        print(f"Error: Configuration file not found at {config_path}") # Stays print for now
        return None

    config = configparser.ConfigParser()
    config.read(config_path)

    settings = {}
    if 'monitor' in config:
        settings['interval_seconds'] = config.getint('monitor', 'interval_seconds', fallback=300)
        settings['mapping_file_path'] = config.get('monitor', 'mapping_file_path', fallback='config/service_map.json')
        settings['log_file'] = config.get('monitor', 'log_file', fallback='cloud_monitor.log')
        settings['log_level'] = config.get('monitor', 'log_level', fallback='INFO').upper()
    else:
        print(f"Error: [monitor] section not found in {config_path}") # Stays print for now
        settings['interval_seconds'] = 300
        settings['mapping_file_path'] = 'config/service_map.json'
        settings['log_file'] = 'cloud_monitor.log'
        settings['log_level'] = 'INFO'

    return settings

def load_service_map(mapping_file_path):
    """
    Loads the service-to-test mapping file (JSON).
    Returns a dictionary of the mapping or None if file not found or invalid JSON.
    """
    if not os.path.isabs(mapping_file_path):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        mapping_file_path = os.path.join(script_dir, mapping_file_path)

    if not os.path.exists(mapping_file_path):
        print(f"Error: Service mapping file not found at {mapping_file_path}") # Stays print
        return None

    try:
        with open(mapping_file_path, 'r') as f:
            service_map = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {mapping_file_path}: {e}") # Stays print
        return None
    except IOError as e:
        print(f"Error: Could not read service mapping file {mapping_file_path}: {e}") # Stays print
        return None

    if not isinstance(service_map, dict):
        print(f"Error: Service mapping file {mapping_file_path} should contain a JSON object.") # Stays print
        return None

    for service, regions in service_map.items():
        if not isinstance(regions, dict):
            print(f"Warning: Service '{service}' in {mapping_file_path} does not have a valid region mapping (should be a dictionary).") # Stays print

    return service_map

def run_test(test_script_path):
    """
    Runs a Python test script using subprocess.
    """
    if not os.path.isabs(test_script_path):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        script_full_path = os.path.join(base_dir, test_script_path)
    else:
        script_full_path = test_script_path

    if not os.path.exists(script_full_path):
        return -1, "", f"Test script not found: {script_full_path}" # Stays print for direct error in tuple

    if not script_full_path.endswith(".py"):
        return -1, "", f"Not a Python file: {script_full_path}" # Stays print

    try:
        process = subprocess.run(
            ['python3', script_full_path],
            capture_output=True,
            text=True,
            timeout=30
        )
        return process.returncode, process.stdout, process.stderr
    except FileNotFoundError:
        print("Error: python3 interpreter not found. Cannot run test script.") # Stays print
        return -1, "", "python3 interpreter not found."
    except subprocess.TimeoutExpired:
        print(f"Error: Test script {script_full_path} timed out.") # Stays print
        return -1, "", f"Test script timed out: {script_full_path}"
    except Exception as e:
        print(f"Error running test script {script_full_path}: {e}") # Stays print
        return -1, "", f"Exception during test execution: {e}"

if __name__ == '__main__':
    # Reverted to print statements for utils.py self-testing to isolate timeout issue
    print("--- Testing load_settings ---")
    print("Testing with default path:")
    current_settings = load_settings()
    if current_settings:
        print("Settings loaded successfully (default path):")
        for key, value in current_settings.items():
            print(f"  {key}: {value}")
    else:
        print("Failed to load settings using default path.")

    print("\nTesting with explicit relative path 'config/settings.ini':")
    explicit_relative_path_settings = "config/settings.ini"
    current_settings_explicit = load_settings(explicit_relative_path_settings)
    if current_settings_explicit:
        print("Settings loaded successfully with explicit relative path:")
        for key, value in current_settings_explicit.items():
            print(f"  {key}: {value}")
    else:
        print(f"Failed to load settings with explicit relative path: {explicit_relative_path_settings}")

    abs_path_to_settings = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config/settings.ini")
    print(f"\nTesting with absolute path: {abs_path_to_settings}")
    current_settings_abs = load_settings(abs_path_to_settings)
    if current_settings_abs:
        print("Settings loaded successfully with absolute path:")
        for key, value in current_settings_abs.items():
            print(f"  {key}: {value}")
    else:
        print(f"Failed to load settings with absolute path: {abs_path_to_settings}")

    print("\n--- Testing load_service_map ---")
    print("\nTesting with path from settings (simulated):")
    if current_settings and 'mapping_file_path' in current_settings:
        map_path_from_settings = current_settings['mapping_file_path']
        print(f"Mapping file path from settings: {map_path_from_settings}")
        service_mappings = load_service_map(map_path_from_settings)
        if service_mappings:
            print("Service map loaded successfully:")
            for service, regions in service_mappings.items():
                print(f"  Service: {service}")
                for region, test_file in regions.items():
                    print(f"    Region: {region} -> Test: {test_file}")
        else:
            print("Failed to load service map using path from settings.")
    else:
        print("Could not load settings or mapping_file_path not found in settings (needed for service map test).")

    print("\nTesting with direct relative path 'config/service_map.json':")
    direct_map_path = "config/service_map.json"
    service_mappings_direct = load_service_map(direct_map_path)
    if service_mappings_direct:
        print("Service map loaded successfully with direct relative path:")
        # print(json.dumps(service_mappings_direct, indent=2)) # For more detail if needed
    else:
        print(f"Failed to load service map with direct relative path: {direct_map_path}")

    print("\nTesting with non-existent file path:")
    non_existent_map_path = "config/non_existent_map.json"
    service_mappings_non_existent = load_service_map(non_existent_map_path)
    if service_mappings_non_existent is None:
        print("Correctly handled non-existent mapping file (returned None).")
    else:
        print(f"Error: Should have returned None for non-existent file: {non_existent_map_path}")

    print("\n--- Testing run_test ---")
    print("\nTesting successful script:")
    success_script_path = "tests/sample_test_success.py"
    return_code, stdout, stderr = run_test(success_script_path)
    print(f"  Return Code: {return_code}")
    print(f"  Stdout:\n{stdout}")
    print(f"  Stderr:\n{stderr}")
    assert return_code == 0, f"Expected return code 0, got {return_code}"

    print("\nTesting failing script:")
    failure_script_path = "tests/sample_test_failure.py"
    return_code, stdout, stderr = run_test(failure_script_path)
    print(f"  Return Code: {return_code}")
    print(f"  Stdout:\n{stdout}")
    print(f"  Stderr:\n{stderr}")
    assert return_code != 0, f"Expected non-zero return code, got {return_code}"

    print("\nTesting non-existent script:")
    non_existent_script_path = "tests/non_existent_test.py"
    return_code, stdout, stderr = run_test(non_existent_script_path)
    print(f"  Return Code: {return_code}")
    print(f"  Stdout:\n{stdout}") # Expected to be empty
    print(f"  Stderr:\n{stderr}") # Expected to contain the error
    assert return_code == -1, f"Expected return code -1 for non-existent, got {return_code}"
    assert "Test script not found" in stderr, f"Expected 'Test script not found' in stderr, got: {stderr}"

    print("\nTesting with a non-python file:")
    non_py_script_path = "config/settings.ini"
    return_code, stdout, stderr = run_test(non_py_script_path)
    print(f"  Return Code: {return_code}")
    print(f"  Stdout:\n{stdout}") # Expected to be empty
    print(f"  Stderr:\n{stderr}") # Expected to contain the error
    assert return_code == -1, f"Expected return code -1 for non-python file, got {return_code}"
    assert "Not a Python file" in stderr, f"Expected 'Not a Python file' in stderr, got: {stderr}"

    print("\nrun_test tests complete.")
