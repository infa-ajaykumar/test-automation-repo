import time
import datetime
import sys # For sys.exit at the end of main

# Assuming utils.py and parsers.py are in the same directory (cloud_status_monitor)
try:
    from utils import load_settings, load_service_map, run_test
except ImportError:
    print("Error: Failed to import from utils.py. Make sure it's in the same directory or PYTHONPATH is set.")
    sys.exit(1)

try:
    from parsers import (
        parse_aws_status, parse_azure_status, parse_gcp_status,
        parse_oracle_status, parse_jfrog_status, parse_artifactory_status,
        parse_mongodb_status
    )
except ImportError:
    print("Error: Failed to import from parsers.py. Make sure it's in the same directory or PYTHONPATH is set.")
    sys.exit(1)


# In-memory store for seen incidents (from previous step)
SEEN_INCIDENTS = {}
ACTIVE_INCIDENTS = {}
INCIDENT_EXPIRY_HOURS = 72 # How long to keep a resolved incident in SEEN_INCIDENTS

def is_new_or_updated_incident(incident_data):
    """
    Checks if an incident is new or if its status has been updated.
    Updates SEEN_INCIDENTS and ACTIVE_INCIDENTS.
    """
    incident_id = incident_data['id']
    current_status = incident_data['status_summary']
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    SEEN_INCIDENTS[incident_id] = now_utc # Update last seen time for this specific incident ID

    if incident_id not in ACTIVE_INCIDENTS:
        # New incident
        ACTIVE_INCIDENTS[incident_id] = incident_data.copy()
        # Using print for logging temporarily
        print(f"LOG: New incident detected: {incident_id} - Title: '{incident_data.get('title', 'N/A')}' - Status: {current_status}")
        return True
    else:
        # Existing incident, check for status change
        previous_status = ACTIVE_INCIDENTS[incident_id]['status_summary']
        if previous_status != current_status:
            print(f"LOG: Incident status change: {incident_id} - From '{previous_status}' to '{current_status}'")
            ACTIVE_INCIDENTS[incident_id] = incident_data.copy() # Update with new data
            return True
        # If status is the same, it's not "new" for triggering actions again.
        # print(f"LOG: Incident {incident_id} seen again, status '{current_status}' unchanged.")
        return False

def cleanup_old_incidents():
    """
    Removes old incidents from SEEN_INCIDENTS and resolved incidents from ACTIVE_INCIDENTS.
    """
    now_utc = datetime.datetime.now(datetime.timezone.utc)

    # Cleanup SEEN_INCIDENTS
    expired_ids_seen = [
        inc_id for inc_id, seen_time in SEEN_INCIDENTS.items()
        if (now_utc - seen_time).total_seconds() > INCIDENT_EXPIRY_HOURS * 3600
    ]
    for inc_id in expired_ids_seen:
        if inc_id in SEEN_INCIDENTS: # Check before deleting
             del SEEN_INCIDENTS[inc_id]
        print(f"LOG: Removed expired incident ID {inc_id} from SEEN_INCIDENTS.")

    # Cleanup ACTIVE_INCIDENTS: remove resolved incidents that are also old
    resolved_and_old_active_ids = []
    for inc_id, incident_data in list(ACTIVE_INCIDENTS.items()): # Iterate over a copy for safe deletion
        status = incident_data.get('status_summary', '').lower()
        # Consider various terms for resolved status
        is_resolved = any(term in status for term in ["resolved", "completed", "closed", "normal operation", "operating normally"])

        if is_resolved:
            # If it's resolved and hasn't been "seen"/updated for a while (e.g., > 1 hour), remove from active list.
            if inc_id in SEEN_INCIDENTS:
                last_seen_time = SEEN_INCIDENTS[inc_id]
                # How long to keep a resolved incident in ACTIVE_INCIDENTS after its last update
                if (now_utc - last_seen_time).total_seconds() > 3600: # 1 hour
                    resolved_and_old_active_ids.append(inc_id)
            elif inc_id not in SEEN_INCIDENTS:
                resolved_and_old_active_ids.append(inc_id)


    for inc_id in resolved_and_old_active_ids:
        if inc_id in ACTIVE_INCIDENTS: # Check again before deleting
            print(f"LOG: Removing resolved and stale incident {inc_id} (status: {ACTIVE_INCIDENTS[inc_id].get('status_summary')}) from ACTIVE_INCIDENTS.")
            del ACTIVE_INCIDENTS[inc_id]


# Mapping of service names (keys used in service_map.json) to their parser functions
SERVICE_PARSERS = {
    "AWS": parse_aws_status,
    "Azure": parse_azure_status,
    "GCP": parse_gcp_status,
    "Oracle": parse_oracle_status,
    "JFrog": parse_jfrog_status,
    "Artifactory": parse_artifactory_status, # Key used in service_map.json
    "MongoDB": parse_mongodb_status,
}

def main_loop():
    print("LOG: Monitor starting...")
    print("LOG: Loading settings...")
    settings = load_settings("config/settings.ini")
    if not settings:
        print("FATAL: Could not load settings. Exiting.")
        sys.exit(1) # Use sys.exit
    print("LOG: Settings loaded.")

    monitor_interval = settings.get('interval_seconds', 300)
    mapping_file_path = settings.get('mapping_file_path', "config/service_map.json")

    print(f"LOG: Loading service map from {mapping_file_path}...")
    service_map = load_service_map(mapping_file_path)
    if not service_map:
        print(f"FATAL: Could not load service map from {mapping_file_path}. Exiting.")
        sys.exit(1) # Use sys.exit
    print("LOG: Service map loaded.")

    print(f"LOG: Monitoring interval: {monitor_interval} seconds.")
    print(f"LOG: Service map loaded for {len(service_map)} services.")

    try:
        for i_cycle in range(1): # Run only once for testing
            cycle_start_time = datetime.datetime.now(datetime.timezone.utc)
            print(f"\nLOG: Starting monitoring cycle {i_cycle + 1} at {cycle_start_time.isoformat()}")

            for service_name_in_map, parser_func in SERVICE_PARSERS.items():
                parser_call_start_time = datetime.datetime.now(datetime.timezone.utc)
                print(f"LOG: [{service_name_in_map}] Calling parser function at {parser_call_start_time.isoformat()}...")
                incidents = []
                try:
                    incidents = parser_func()
                except Exception as e:
                    print(f"ERROR: [{service_name_in_map}] Parser failed: {e}")
                    continue
                parser_call_end_time = datetime.datetime.now(datetime.timezone.utc)
                print(f"LOG: [{service_name_in_map}] Parser function finished at {parser_call_end_time.isoformat()}. Duration: {(parser_call_end_time - parser_call_start_time).total_seconds()}s")

                if not incidents:
                    print(f"LOG: [{service_name_in_map}] No incidents reported or parser returned no data.")
                    continue

                print(f"LOG: [{service_name_in_map}] Parser found {len(incidents)} item(s). Processing...")

                for incident_idx, incident in enumerate(incidents):
                    incident_process_start_time = datetime.datetime.now(datetime.timezone.utc)
                    print(f"LOG: [{service_name_in_map}] Processing incident {incident_idx + 1}/{len(incidents)} (ID: {incident.get('id','MISSING_ID')}) at {incident_process_start_time.isoformat()}")
                    required_keys = ['id', 'service', 'region', 'title', 'status_summary', 'timestamp_utc']
                    if not all(k in incident for k in required_keys):
                        print(f"LOG: [{service_name_in_map}] Warning - Malformed incident data (ID: {incident.get('id','MISSING_ID')}). Missing keys. Skipping.")
                        continue

                    incident_service_key = incident['service']
                    is_actionable_start_time = datetime.datetime.now(datetime.timezone.utc)
                    actionable = is_new_or_updated_incident(incident)
                    is_actionable_end_time = datetime.datetime.now(datetime.timezone.utc)
                    print(f"LOG: [{service_name_in_map}] Incident ID {incident['id']} actionable check took {(is_actionable_end_time - is_actionable_start_time).total_seconds()}s. Actionable: {actionable}")

                    if actionable:
                        print(f"LOG: [{service_name_in_map}] Actionable Incident: ID={incident['id']}, Service={incident_service_key}, Region={incident['region']}, Title='{incident['title']}'")
                        affected_region_key = incident['region']

                        if incident_service_key in service_map:
                            service_region_map = service_map[incident_service_key]
                            test_script_to_run = None
                            if affected_region_key in service_region_map:
                                test_script_to_run = service_region_map[affected_region_key]
                            elif "global" in service_region_map:
                                print(f"LOG: [{service_name_in_map}] Region '{affected_region_key}' not specific in map, using 'global' test.")
                                test_script_to_run = service_region_map["global"]

                            if test_script_to_run:
                                test_run_start_time = datetime.datetime.now(datetime.timezone.utc)
                                print(f"LOG: [{service_name_in_map}] Match found: Triggering test: {test_script_to_run} at {test_run_start_time.isoformat()}")
                                return_code, stdout, stderr = run_test(test_script_to_run)
                                test_run_end_time = datetime.datetime.now(datetime.timezone.utc)
                                print(f"LOG: [{service_name_in_map}] Test execution for {test_script_to_run} finished at {test_run_end_time.isoformat()}. Duration: {(test_run_end_time - test_run_start_time).total_seconds()}s")
                                print(f"  Return Code: {return_code}")
                                if stdout.strip(): print(f"  Stdout: {stdout.strip()}")
                                if stderr.strip(): print(f"  Stderr: {stderr.strip()}")
                            else:
                                print(f"LOG: [{service_name_in_map}] No specific test script mapped for {incident_service_key}/{affected_region_key} (and no 'global' fallback). No tests run.")
                        else:
                            print(f"LOG: [{service_name_in_map}] Service '{incident_service_key}' from incident not found in service_map.json. No tests run.")
                    incident_process_end_time = datetime.datetime.now(datetime.timezone.utc)
                    print(f"LOG: [{service_name_in_map}] Finished processing incident {incident_idx + 1}/{len(incidents)} (ID: {incident.get('id','MISSING_ID')}) at {incident_process_end_time.isoformat()}. Duration: {(incident_process_end_time - incident_process_start_time).total_seconds()}s")

            cycle_end_time = datetime.datetime.now(datetime.timezone.utc)
            print(f"\nLOG: Monitoring cycle {i_cycle + 1} complete at {cycle_end_time.isoformat()}. Duration: {(cycle_end_time - cycle_start_time).total_seconds()}s")
            print(f"LOG: Active incidents at end of cycle: {len(ACTIVE_INCIDENTS)}")

            cleanup_start_time = datetime.datetime.now(datetime.timezone.utc)
            cleanup_old_incidents()
            cleanup_end_time = datetime.datetime.now(datetime.timezone.utc)
            print(f"LOG: Cleanup finished at {cleanup_end_time.isoformat()}. Duration: {(cleanup_end_time - cleanup_start_time).total_seconds()}s")
            # time.sleep(monitor_interval) # Sleep commented out for single run test

    except KeyboardInterrupt:
        print("LOG: Monitoring stopped by user (KeyboardInterrupt).")
    except Exception as e:
        import traceback
        print(f"FATAL: An unexpected error occurred in the main loop: {e}")
        print("Traceback:")
        print(traceback.format_exc())
    finally:
        print("LOG: Monitor shutting down.")


if __name__ == '__main__':
    main_loop()
    print("LOG: main_loop function finished. Monitor script ending.")
