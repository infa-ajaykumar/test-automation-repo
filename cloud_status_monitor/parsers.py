import requests
from bs4 import BeautifulSoup
import datetime
import hashlib # For generating unique IDs for incidents
import os # Added for potential future use, not strictly in original but good practice

# Define a common structure for incident data
# Incident = {
#     "id": "unique_incident_identifier", # e.g., hash of service, title, and initial timestamp
#     "service": "service_name", # e.g., "AWS", "Azure"
#     "region": "affected_region", # e.g., "us-east-1", "Global"
#     "title": "incident_title_or_description",
#     "status_summary": "current_status_summary", # e.g., "Investigating", "Resolved"
#     "timestamp_utc": "datetime_object_utc", # When the incident was last updated or first posted
#     "url": "url_to_incident_details_if_available"
# }

def generate_incident_id(service, title, initial_timestamp_str):
    """Generates a unique ID for an incident."""
    id_string = f"{service}-{title}-{initial_timestamp_str}"
    return hashlib.md5(id_string.encode()).hexdigest()

def parse_aws_status():
    """
    Parses the AWS status page by fetching its RSS feed (https://status.aws.amazon.com/rss/all.rss).
    Returns a list of incident dictionaries.
    """
    service_name = "AWS"
    # The main status page is hard to scrape due to JS. RSS is more reliable.
    # url = "https://status.aws.amazon.com/"
    rss_url = "https://status.aws.amazon.com/rss/all.rss"
    incidents = []

    try:
        # First, try the "all services" RSS feed
        response_rss = requests.get(rss_url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'}) # Reduced timeout
        response_rss.raise_for_status() # Raise an exception for HTTP errors
        soup_rss = BeautifulSoup(response_rss.content, 'xml') # Use 'xml' parser for RSS

        for item in soup_rss.find_all('item'):
            title = item.find('title').text if item.find('title') else "N/A"
            link = item.find('link').text if item.find('link') else rss_url # Fallback to rss url
            pub_date_str = item.find('pubDate').text if item.find('pubDate') else None
            description = item.find('description').text if item.find('description') else ""

            timestamp_utc = datetime.datetime.now(datetime.timezone.utc) # Default to now if no pubDate
            if pub_date_str:
                try:
                    # Format: Tue, 11 Jun 2024 09:46:54 +0000
                    # Sometimes it might be 'Z' for UTC e.g. 2023-04-15T10:30:00Z
                    parsed_time = None
                    try:
                        parsed_time = datetime.datetime.strptime(pub_date_str, '%a, %d %b %Y %H:%M:%S %z')
                    except ValueError:
                        # Try ISO format with Z
                        if pub_date_str.endswith('Z'):
                            parsed_time = datetime.datetime.strptime(pub_date_str, '%Y-%m-%dT%H:%M:%SZ')
                            parsed_time = parsed_time.replace(tzinfo=datetime.timezone.utc)
                        else: # Add other formats if necessary
                            raise

                    if parsed_time:
                       timestamp_utc = parsed_time.astimezone(datetime.timezone.utc)

                except ValueError as e:
                    print(f"AWS Parser: Error parsing date '{pub_date_str}': {e}. Using current time as fallback.")
                    # Fallback to current time is already set

            # Simplified parsing for status and region:
            status_summary = "Investigating" # Default status
            region = "Unknown" # Default region

            # Attempt to infer region from title (e.g., "Amazon EC2 (N. Virginia) - Performance Issues")
            # AWS titles can be:
            # "Service Name status" for resolutions (e.g. "Amazon Simple Storage Service (S3) resolution")
            # "Service Name (Region) status" (e.g. "Amazon Elastic Compute Cloud (N. Virginia) Increased API Error Rates")
            title_lower = title.lower()

            if "(" in title and ")" in title:
                try:
                    region_candidate = title.split('(', 1)[1].split(')', 1)[0]
                    # Basic check if it's a plausible region or just some other parenthetical text
                    # AWS regions are typically like 'us-east-1', 'N. Virginia', 'Global', etc.
                    if any(char.islower() for char in region_candidate.replace('-', '').replace('.', '')) and any(char.isupper() for char in region_candidate):
                         region = region_candidate
                    elif region_candidate.lower() == "global":
                         region = "Global"
                    # Add more specific region checks if needed
                except Exception:
                    pass # Could not parse region from title as expected

            if "resolved" in title_lower or "resolution" in title_lower or "completed" in title_lower:
                status_summary = "Resolved"
            elif "experiencing issues" in title_lower or "investigating" in title_lower or "increased error rates" in title_lower or "degraded performance" in title_lower:
                status_summary = "Investigating"
            # If "operating normally" is in description and not a resolution, it's an informational update.
            # We should decide if we want to include these. For now, we only include if it's a clear "Resolved" state.
            # Or if it implies an ongoing issue.
            # Messages like "[Informational] Amazon S3 is operating normally" are usually skipped.
            if "operating normally" in description.lower() and status_summary != "Resolved":
                # This is likely an informational message about normal operations, not an active incident or resolution.
                # Let's skip these to focus on actual disruptions or their resolutions.
                continue

            inc_id = generate_incident_id(service_name, title, pub_date_str if pub_date_str else str(timestamp_utc))

            incidents.append({
                "id": inc_id,
                "service": service_name,
                "region": region,
                "title": title,
                "status_summary": status_summary,
                "timestamp_utc": timestamp_utc,
                "url": link,
                "raw_description": description # Keep raw description for potential further processing
            })

    except requests.exceptions.RequestException as e:
        print(f"AWS Parser: Error fetching RSS feed {rss_url}: {e}")
        return []
    except Exception as e:
        print(f"AWS Parser: An unexpected error occurred: {e}")
        return []

    return incidents

# Placeholder parsers for other services
def parse_azure_status():
    print("Azure Parser: Not yet implemented.")
    return []

def parse_gcp_status():
    print("GCP Parser: Not yet implemented.")
    return []

def parse_oracle_status():
    print("Oracle Parser: Not yet implemented.")
    return []

def parse_jfrog_status():
    print("JFrog Parser: Not yet implemented.")
    return []

def parse_artifactory_status():
    print("Artifactory (CloudRepo) Parser: Not yet implemented.")
    return []

def parse_mongodb_status():
    print("MongoDB Parser: Not yet implemented.")
    return []

# Main function for testing (optional)
if __name__ == '__main__':
    print("--- Testing AWS Status Parser ---")
    # To ensure User-Agent is set for tests if any function here uses requests directly
    # For parse_aws_status, it's handled inside.
    aws_incidents = parse_aws_status()
    if aws_incidents: # Check if list is not empty
        print(f"Found {len(aws_incidents)} AWS incident(s)/update(s) from RSS feed:")
        for incident in aws_incidents:
            print(f"  ID: {incident['id']}")
            print(f"  Service: {incident['service']}")
            print(f"  Region: {incident['region']}")
            print(f"  Title: {incident['title']}")
            print(f"  Status: {incident['status_summary']}")
            print(f"  Timestamp: {incident['timestamp_utc'].strftime('%Y-%m-%d %H:%M:%S %Z') if incident['timestamp_utc'] else 'N/A'}")
            print(f"  URL: {incident['url']}")
            # print(f"  Description: {incident['raw_description'][:100]}...") # Optional: print snippet of description
            print("-" * 20)
    elif aws_incidents == []:
        print("AWS Parser returned no incidents (this could be normal if no active issues or an error occurred).")
    else: # Should not happen if parser returns [] on error
        print("AWS Parser failed to return a list (unexpected).")

    # Example calls to other parsers (will just print "Not yet implemented")
    # print("\n--- Testing Other Parsers (Placeholders) ---")
    # parse_azure_status()
    # parse_gcp_status()
