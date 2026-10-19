"""The main module with the program entry point.

This modul handle the mqtt connection and uses submodules for database handling and user interface
"""
# TODO: event Name speichern

# ******************************************************************************
# Copyright (c) 2024, Achim Brunner
# License: BSD 3 Clause
# ******************************************************************************

# Imports **********************************************************************

import sys
import logging
import os
import argparse
import json
import ssl
import csv
import threading
import http.server
import socketserver
import re
import urllib.parse
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta
from dotenv import load_dotenv
import paho.mqtt.client as mqtt
import trackingmap_agent.tracker_db

try:
    from trackingmap_agent.version import __version__, __author__, __email__, __repository__, __license__
except ModuleNotFoundError:
    # provide dummy information when not installed as package but called directly
    # also necessary to get sphinx running without error
    __version__ = 'dev'
    __author__ = 'development'
    __email__ = 'none'
    __repository__ = 'none'
    __license__ = 'none'

# Variables ********************************************************************

LOG: logging.Logger = logging.getLogger(__name__)
TOPIC = "v3/+/devices/+/up"    # all uplinks of all devices

# Classes **********************************************************************

class HealthCheckHandler(http.server.BaseHTTPRequestHandler):
    """Simple HTTP handler for health checks and tracker data requests."""

    db_conn = None

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        if parsed_url.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status": "healthy", "service": "trackingmap-agent"}')
        elif parsed_url.path == '/tracker':
            self.handle_tracker(parsed_url.query)
        else:
            self.send_response(404)
            self.end_headers()

    def handle_tracker(self, query: str):
        params = urllib.parse.parse_qs(query)
        try:
            limit = int(params.get('limit', ['1000'])[0])
        except ValueError:
            limit = 1000

        if limit < 1:
            limit = 1

        if self.db_conn is None:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"error": "Database connection not available"}')
            return

        try:
            records = trackingmap_agent.tracker_db.get_tracker_data(self.db_conn, limit=limit)
        except Exception as e:
            LOG.error(f"Failed to fetch tracker data: {e}")
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Failed to fetch tracker data"}).encode('utf-8'))
            return

        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(records, default=str).encode('utf-8'))

    def log_message(self, format, *args):
        # Suppress default HTTP server logs
        return

def start_health_server(port=8000, db_conn=None):
    """Start a simple HTTP server for health checks in a separate thread."""
    HealthCheckHandler.db_conn = db_conn
    try:
        with socketserver.TCPServer(("", port), HealthCheckHandler) as httpd:
            LOG.info(f"Health check server started on port {port}")
            httpd.serve_forever()
    except Exception as e:
        LOG.error(f"Failed to start health check server: {e}")


def parse_iso_datetime(value: str) -> datetime:
    """Parse ISO datetime strings and normalize fractional seconds for Python 3.9."""
    value = value.replace("Z", "+00:00")
    match = re.match(r"(?P<prefix>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(?P<fraction>\d+))?(?P<tz>[+-].*)?", value)
    if not match:
        return datetime.fromisoformat(value)

    prefix = match.group("prefix")
    fraction = match.group("fraction") or ""
    tz = match.group("tz") or ""

    if fraction and len(fraction) > 6:
        fraction = fraction[:6]

    normalized = f"{prefix}.{fraction}{tz}" if fraction else f"{prefix}{tz}"
    return datetime.fromisoformat(normalized)

# Functions ********************************************************************


def on_connect(cl, userdata, flags, rc, _):
    """
    Callback function triggered upon successful connection to the MQTT broker.
    Subscribes to the specified topic for device uplinks.

    Args:
        cl: The MQTT client instance.
        userdata: User-defined data of any type (not used).
        flags: Response flags sent by the broker.
        rc: The connection result (0 indicates success).
        _: Deprecated or unused parameter (kept for compatibility).
    """

    if rc == 0:
        LOG.info("Connected RC = %s", rc)
        cl.subscribe(TOPIC)
        LOG.info("Subscribed: %s", TOPIC)
    else:
        LOG.error("Connection failed: %s", rc)


def on_message(cl, userdata, msg):
    """
    Callback function triggered when a message is received on a subscribed topic.
    Parses the JSON payload and prints device ID and decoded payload.

    Args:
        cl: The MQTT client instance.
        userdata: User-defined data (contains db_conn).
        msg: The received MQTT message object.
    """
    db_conn = userdata  # Get database connection from user data

    tracker_info = {
        "tracker_id": "",
        "latitude": 0.0,
        "longitude": 0.0,
        "battery": 0,  # Percenct
        "timestamp": "",
        "gw-rssi": -70,    # Signalstrength in dBm
        "gw-name": "",
        "gw-latitude": 0.0,
        "gw-longitude": 0.0,
        "gw-timestamp": ""


    }

    try:
        LOG.debug("Payload: %s", msg.payload)
        data = json.loads(msg.payload)
    except json.JSONDecodeError as e:
        LOG.error("Json Decoding error: %s", e)
        return

    try:
        dev = data["end_device_ids"]["device_id"]
    except KeyError as e:
        LOG.error("Error in message processing: %s for device id", e)
        LOG.debug("Payload Data: %s", data)
        return

    try:
        uplink_message = data["uplink_message"]
        decoded_payload = uplink_message["decoded_payload"]
        messages = decoded_payload.get("messages", [])
        if not messages:
            raise KeyError("uplink_message.decoded_payload.messages is empty or missing")
        payl = messages[0]

        rx_metadata_list = uplink_message.get("rx_metadata", [])
        if not rx_metadata_list:
            raise KeyError("uplink_message.rx_metadata is empty or missing")
        rx_metadata = rx_metadata_list[0]

        LOG.debug("Device: [%s] %s", dev, payl)
        LOG.debug("Metadata: %s", rx_metadata)

        tracker_info["tracker_id"] = dev
        tracker_info["gw-name"] = rx_metadata["gateway_ids"]["gateway_id"]
        tracker_info["gw-rssi"] = rx_metadata["rssi"]
        if "location" in rx_metadata:
            tracker_info["gw-latitude"] = rx_metadata["location"]["latitude"]
            tracker_info["gw-longitude"] = rx_metadata["location"]["longitude"]
        else:
            tracker_info["gw-latitude"] = 0.0
            tracker_info["gw-longitude"] = 0.0
        timestamp_str = rx_metadata["time"]
        gw_dt = parse_iso_datetime(timestamp_str)
        tracker_info["gw-timestamp"] = (gw_dt + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")

        for measurement in payl:
            if measurement["measurementId"] == '4197':
                tracker_info["longitude"] = measurement["measurementValue"]
                utc_dt = datetime.fromtimestamp(
                    int(measurement["timestamp"])/1000, tz=ZoneInfo("Europe/Berlin"))
                tracker_info["timestamp"] = utc_dt.strftime('%Y-%m-%d %H:%M:%S')
            if measurement["measurementId"] == '4198':
                tracker_info["latitude"] = measurement["measurementValue"]
            if measurement["measurementId"] == '3000':
                tracker_info["battery"] = measurement["measurementValue"]
        LOG.info("Update for %s at %s",
                 tracker_info["tracker_id"], tracker_info["timestamp"])
        if tracker_info["timestamp"]:  # Changed condition to check if timestamp is set (indicating longitude measurement was received)
            trackingmap_agent.tracker_db.save_tracker_data_to_file(tracker_info)
            success, message, was_invalid = trackingmap_agent.tracker_db.insert_tracker_info_with_error_logging(db_conn, tracker_info)
            if not success:
                LOG.error(f"Failed to store tracker data: {message}")
            elif was_invalid:
                LOG.warning(f"Stored invalid data: {message}")
    except (KeyError, TypeError, IndexError) as e:
        LOG.error("Error in message processing: %s for device: %s", e, dev)
        LOG.debug("Payload Data: %s", data)
        return


def init_csv_writer(file_path, fieldnames):
    """
    Initialize CSV output of received tracker data

    Args:
        file_path (str): File name and path
        fieldnames (dict): Dictionary with field names

    Returns:
        handle: Handler to writer object
    """
    file_exists = os.path.isfile(file_path)
    file = open(file_path, mode='a', newline='', encoding='utf-8', buffering=1)
    writer = csv.DictWriter(file, fieldnames=fieldnames)

    if not file_exists:
        writer.writeheader()

    return writer


def main() -> int:
    """ The program entry point function.

    .. uml::

        Alice -> Bob: Hi!
        Alice <- Bob: How are you?

    Returns:
        int: System exit status.
    """
    logging.basicConfig(level=logging.INFO)

    # Create an ArgumentParser object
    parser = argparse.ArgumentParser(
        description="A simple example of parsing command-line arguments.")

    # Add arguments
    parser.add_argument('--verbose', action='store_true',
                        help='Increase output verbosity')
    parser.add_argument('--version', action='version',
                        version='%(prog)s' + __version__)

    args = parser.parse_args()  # Parse the arguments

    if args.verbose:
        print("Verbose mode is enabled.")
        LOG.setLevel(logging.DEBUG)

    # Load environment variables
    load_dotenv(".env", override=True)                                       # liest .env ein

    try:
        app_id = os.environ["TTN_APP_ID"]
        tenant = os.getenv("TTN_TENANT", "ttn")
        region = os.getenv("TTN_REGION", "eu1")
        api_key = os.environ["TTN_API_KEY"]
    except KeyError as e:
        # If required env vars are missing, check if DUMMY_MODE is set
        if os.getenv("DUMMY_MODE", "").lower() in ("true", "1", "yes"):
            LOG.info("Dummy mode enabled - using dummy credentials")
            app_id = "dummy-app-id"
            tenant = "ttn"
            region = "eu1"
            api_key = "dummy-api-key"
        else:
            raise RuntimeError(f"Missing required environment variable: {e}")

    # Check if running with dummy credentials (for health check/testing)
    is_dummy_mode = (app_id == "dummy-app-id" and api_key == "dummy-api-key")

    # Set up MQTT variables
    MQTT_HOST = f"{region}.cloud.thethings.network"
    CLIENT_ID = app_id
    USERNAME = app_id
    PASSWORD = api_key
    global TOPIC
    TOPIC = "v3/+/devices/+/up"    # all uplinks of all devices

    # Initialize database connection
    use_azure_sql = os.getenv("USE_AZURE_SQL", "false").lower() == "true"
    use_postgres = os.getenv("USE_POSTGRES", "false").lower() == "true"
    db_conn = trackingmap_agent.tracker_db.init_db(use_azure_sql=use_azure_sql, use_postgres=use_postgres)
    
    LOG.info("Database connection initialized: %s", "Azure SQL" if use_azure_sql else "PostgreSQL" if use_postgres else "None")
    LOG.info("Application started")
    LOG.debug("Client ID: %s", CLIENT_ID)
    LOG.debug("Credentials: %s - %s", USERNAME, PASSWORD)

    # Start health check server in background thread (only if not in dummy mode)
    if not is_dummy_mode:
        health_thread = threading.Thread(target=start_health_server, args=(8000, db_conn), daemon=True)
        health_thread.start()

    # Skip MQTT connection in dummy mode
    if is_dummy_mode:
        LOG.info("Dummy mode: skipping MQTT connection")
        return 0

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         CLIENT_ID, protocol=mqtt.MQTTv311, userdata=db_conn)
    client.username_pw_set(USERNAME, PASSWORD)
    client.tls_set(cert_reqs=ssl.CERT_REQUIRED)         # TLS, Port 8883
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(MQTT_HOST, port=8883)
    # client.connect(mqtt_host, port=8883, keepalive=120)
    # client.connect(mqtt_host, port=1883, keepalive=60)
    client.loop_forever()

    return 0  # return without errors

# For CSV File init only
tracker_info = {
    "tracker_id": "",
    "latitude": 0.0,
    "longitude": 0.0,
    "battery": 0,
    "timestamp": "",
    "gw-rssi": -1,
    "gw-name": "",
    "gw-latitude": 0.0,
    "gw-longitude": 0.0,
    "gw-timestamp": ""
}

if __name__ == "__main__":
    sys.exit(main())
