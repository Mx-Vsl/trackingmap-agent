""" Database handler for SQLite and Azure SQL databases

This module manages databases for storing tracker information
"""

import os
from datetime import datetime, timedelta
import logging

LOG = logging.getLogger(__name__)

# --- Configuration ---
DB_PATH = "tracker_data.db"

# --- Tracker info structure (for reference) ---
tracker_info = {
    "tracker_id": "",
    "longitude": 0.0,
    "latitude": 0.0,
    "battery": 0,
    "timestamp": "",
    "gw-rssi": -70,
    "gw-name": "",
    "gw-longitude": 0.0,
    "gw-latitude": 0.0,
    "gw-timestamp": ""
}


def init_db(db_path=DB_PATH, use_azure_sql=False):
    """
    Initialize the database (SQLite or Azure SQL).

    Args:
        db_path (str): Path to the SQLite database file (ignored for Azure SQL).
        use_azure_sql (bool): Whether to use Azure SQL instead of SQLite.

    Returns:
        Connection object or None on failure.
    """
    if use_azure_sql:
        return init_azure_sql_db()
    else:
        return init_sqlite_db(db_path)


def init_sqlite_db(db_path=DB_PATH):
    """
    Initialize the SQLite database.

    If the database file does not exist, it creates a new one and
    defines the schema for the 'tracker_data' table.

    Args:
        db_path (str): Path to the SQLite database file.

    Returns:
        sqlite3.Connection: SQLite connection object or None on failure.
    """
    try:
        import sqlite3
        db_exists = os.path.exists(db_path)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        if not db_exists:
            # Create data table if the DB is new
            cursor.execute("""
                CREATE TABLE tracker_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tracker_id TEXT,
                    longitude REAL,
                    latitude REAL,
                    battery INTEGER,
                    timestamp DATETIME,
                    gw_rssi INTEGER,
                    gw_name TEXT,
                    gw_longitude REAL,
                    gw_latitude REAL,
                    gw_timestamp DATETIME
                )
            """)
            conn.commit()

            # Create config table if the DB is new
            cursor.execute("""
                CREATE TABLE tracker_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tracker_id TEXT,
                    tracker_name TEXT,
                    tracker_symbol TEXT,
                    tracker_symbol_color TEXT,
                    tracker_waypoint_max INTEGER,
                    tracker_waypoint_timeout INTEGER,
                    tracker_waypoint_color TEXT
                )
            """)
            conn.commit()

            # Create invalid tracker data table if the DB is new
            cursor.execute("""
                CREATE TABLE tracker_data_invalid (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tracker_id TEXT,
                    longitude REAL,
                    latitude REAL,
                    battery INTEGER,
                    timestamp DATETIME,
                    gw_rssi INTEGER,
                    gw_name TEXT,
                    gw_longitude REAL,
                    gw_latitude REAL,
                    gw_timestamp DATETIME,
                    validation_errors TEXT,
                    stored_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

        return conn  # Return connection for reuse
    except Exception as e:
        LOG.error(f"SQLite error during init: {e}")
        return None


def init_azure_sql_db():
    """
    Initialize the Azure SQL database connection.

    Returns:
        pyodbc.Connection: Azure SQL connection object or None on failure.
    """
    try:
        import pyodbc

        # Get connection string from environment variables
        server = os.environ.get('AZURE_SQL_SERVER')
        database = os.environ.get('AZURE_SQL_DATABASE')
        username = os.environ.get('AZURE_SQL_USERNAME')
        password = os.environ.get('AZURE_SQL_PASSWORD')

        if not all([server, database, username, password]):
            raise ValueError("Missing Azure SQL connection environment variables")

        driver = '{ODBC Driver 18 for SQL Server}'
        connection_string = f'DRIVER={driver};SERVER={server};DATABASE={database};UID={username};PWD={password};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;'

        conn = pyodbc.connect(connection_string)
        cursor = conn.cursor()

        # Check if tables exist, create if not
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='tracker_data' AND xtype='U')
            CREATE TABLE tracker_data (
                id INT IDENTITY(1,1) PRIMARY KEY,
                tracker_id NVARCHAR(255),
                longitude FLOAT,
                latitude FLOAT,
                battery INT,
                timestamp DATETIME2,
                gw_rssi INT,
                gw_name NVARCHAR(255),
                gw_longitude FLOAT,
                gw_latitude FLOAT,
                gw_timestamp DATETIME2
            )
        """)
        conn.commit()

        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='tracker_config' AND xtype='U')
            CREATE TABLE tracker_config (
                id INT IDENTITY(1,1) PRIMARY KEY,
                tracker_id NVARCHAR(255),
                tracker_name NVARCHAR(255),
                tracker_symbol NVARCHAR(255),
                tracker_symbol_color NVARCHAR(255),
                tracker_waypoint_max INT,
                tracker_waypoint_timeout INT,
                tracker_waypoint_color NVARCHAR(255)
            )
        """)
        conn.commit()

        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='tracker_data_invalid' AND xtype='U')
            CREATE TABLE tracker_data_invalid (
                id INT IDENTITY(1,1) PRIMARY KEY,
                tracker_id NVARCHAR(255),
                longitude FLOAT,
                latitude FLOAT,
                battery INT,
                timestamp DATETIME2,
                gw_rssi INT,
                gw_name NVARCHAR(255),
                gw_longitude FLOAT,
                gw_latitude FLOAT,
                gw_timestamp DATETIME2,
                validation_errors NVARCHAR(MAX),
                stored_at DATETIME2 DEFAULT GETUTCDATE()
            )
        """)
        conn.commit()

        return conn
    except Exception as e:
        LOG.error(f"Azure SQL error during init: {e}")
        return None


def insert_tracker_info(conn, data):
    """
    Insert a row of tracker data into the database.

    Args:
        conn: Database connection object (SQLite or Azure SQL).
        data (dict): A dictionary containing tracker info.
    """
    try:
        # Check if it's an Azure SQL connection (has driver attribute) or SQLite
        if hasattr(conn, 'getinfo'):  # pyodbc connection
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO tracker_data (
                    tracker_id, latitude, longitude, battery, timestamp,
                    gw_rssi, gw_name, gw_latitude, gw_longitude, gw_timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data["tracker_id"],
                data["latitude"],
                data["longitude"],
                data["battery"],
                data["timestamp"],
                data["gw-rssi"],
                data["gw-name"],
                data["gw-latitude"],
                data["gw-longitude"],
                data["gw-timestamp"]
            ))
        else:  # SQLite connection
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO tracker_data (
                    tracker_id, latitude, longitude, battery, timestamp,
                    gw_rssi, gw_name, gw_latitude, gw_longitude, gw_timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data["tracker_id"],
                data["latitude"],
                data["longitude"],
                data["battery"],
                data["timestamp"],
                data["gw-rssi"],
                data["gw-name"],
                data["gw-latitude"],
                data["gw-longitude"],
                data["gw-timestamp"]
            ))
        conn.commit()
    except Exception as e:
        LOG.error(f"Database error during insert: {e}")


def validate_tracker_data(data):
    """
    Validate tracker data and return errors (but don't reject it).
    
    Args:
        data (dict): Tracker data to validate.
        
    Returns:
        tuple: (is_valid: bool, errors: list of error messages)
    """
    errors = []
    required_fields = [
        "tracker_id", "latitude", "longitude", "battery", "timestamp",
        "gw-rssi", "gw-name", "gw-latitude", "gw-longitude", "gw-timestamp"
    ]
    
    # 1. Check required fields
    for field in required_fields:
        if field not in data:
            errors.append(f"Missing: {field}")
        elif data[field] is None:
            errors.append(f"None: {field}")
    
    # 2. Validate coordinate ranges
    if "latitude" in data and data["latitude"] is not None:
        try:
            lat = float(data["latitude"])
            if not -90 <= lat <= 90:
                errors.append(f"Latitude out of range: {lat}")
        except (ValueError, TypeError):
            errors.append(f"Latitude not numeric: {data['latitude']}")
    
    if "longitude" in data and data["longitude"] is not None:
        try:
            lon = float(data["longitude"])
            if not -180 <= lon <= 180:
                errors.append(f"Longitude out of range: {lon}")
        except (ValueError, TypeError):
            errors.append(f"Longitude not numeric: {data['longitude']}")
    
    # 3. Validate battery
    if "battery" in data and data["battery"] is not None:
        try:
            battery = int(data["battery"])
            if not 0 <= battery <= 100:
                errors.append(f"Battery out of range: {battery}%")
        except (ValueError, TypeError):
            errors.append(f"Battery not numeric: {data['battery']}")
    
    # 4. Validate timestamps
    if "timestamp" in data and data["timestamp"] is not None:
        try:
            if isinstance(data["timestamp"], str):
                from trackingmap_agent.trackingmap_agent import parse_iso_datetime
                parse_iso_datetime(data["timestamp"])
        except Exception as e:
            errors.append(f"Invalid timestamp: {data['timestamp']}")
    
    if "gw-timestamp" in data and data["gw-timestamp"] is not None:
        try:
            if isinstance(data["gw-timestamp"], str):
                from trackingmap_agent.trackingmap_agent import parse_iso_datetime
                parse_iso_datetime(data["gw-timestamp"])
        except Exception as e:
            errors.append(f"Invalid gw-timestamp: {data['gw-timestamp']}")
    
    return len(errors) == 0, errors


def insert_tracker_info_with_error_logging(conn, data):
    """
    Insert tracker data. If validation fails, store in invalid table instead.
    
    Args:
        conn: Database connection object.
        data (dict): Tracker data to insert.
        
    Returns:
        tuple: (success: bool, message: str, was_invalid: bool)
    """
    is_valid, errors = validate_tracker_data(data)
    
    try:
        if is_valid:
            # Valid data - use normal insert
            insert_tracker_info(conn, data)
            return True, f"OK: {data.get('tracker_id', 'unknown')}", False
        else:
            # Invalid data - store in invalid table
            error_msg = " | ".join(errors)
            
            if hasattr(conn, 'getinfo'):  # Azure SQL
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO tracker_data_invalid (
                        tracker_id, latitude, longitude, battery, timestamp,
                        gw_rssi, gw_name, gw_latitude, gw_longitude, gw_timestamp, validation_errors
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    data.get("tracker_id"),
                    data.get("latitude"),
                    data.get("longitude"),
                    data.get("battery"),
                    data.get("timestamp"),
                    data.get("gw-rssi"),
                    data.get("gw-name"),
                    data.get("gw-latitude"),
                    data.get("gw-longitude"),
                    data.get("gw-timestamp"),
                    error_msg
                ))
            else:  # SQLite
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO tracker_data_invalid (
                        tracker_id, latitude, longitude, battery, timestamp,
                        gw_rssi, gw_name, gw_latitude, gw_longitude, gw_timestamp, validation_errors
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    data.get("tracker_id"),
                    data.get("latitude"),
                    data.get("longitude"),
                    data.get("battery"),
                    data.get("timestamp"),
                    data.get("gw-rssi"),
                    data.get("gw-name"),
                    data.get("gw-latitude"),
                    data.get("gw-longitude"),
                    data.get("gw-timestamp"),
                    error_msg
                ))
            
            conn.commit()
            LOG.warning(f"INVALID DATA stored for {data.get('tracker_id', 'unknown')}: {error_msg}")
            return True, f"STORED (invalid): {data.get('tracker_id', 'unknown')} - {error_msg}", True
    
    except Exception as e:
        LOG.error(f"Error storing tracker data: {e}")
        return False, f"ERROR: {str(e)}", False


def get_invalid_tracker_data(conn, limit=100):
    """
    Retrieve invalid tracker data for analysis.
    
    Args:
        conn: Database connection object.
        limit (int): Maximum records to return.
        
    Returns:
        list: List of invalid tracker records with error messages.
    """
    try:
        cursor = conn.cursor()
        if hasattr(conn, 'getinfo'):  # Azure SQL
            cursor.execute("SELECT TOP (?) * FROM tracker_data_invalid ORDER BY stored_at DESC", (limit,))
        else:  # SQLite
            cursor.execute("SELECT * FROM tracker_data_invalid ORDER BY stored_at DESC LIMIT ?", (limit,))
        
        columns = [column[0] for column in cursor.description]
        results = []
        for row in cursor.fetchall():
            results.append(dict(zip(columns, row)))
        
        return results
    except Exception as e:
        LOG.error(f"Error retrieving invalid tracker data: {e}")
        return []


def delete_invalid_tracker_data(conn, tracker_id=None, keep_days=30):
    """
    Delete invalid tracker data. Can filter by tracker_id or keep only recent.
    
    Args:
        conn: Database connection object.
        tracker_id (str, optional): Delete only for specific tracker.
        keep_days (int): Keep data not older than X days (default: 30).
        
    Returns:
        int: Number of records deleted.
    """
    try:
        cursor = conn.cursor()
        cutoff_date = datetime.utcnow() - timedelta(days=keep_days)
        
        if tracker_id:
            if hasattr(conn, 'getinfo'):  # Azure SQL
                cursor.execute("DELETE FROM tracker_data_invalid WHERE tracker_id = ? AND stored_at < ?", 
                              (tracker_id, cutoff_date))
            else:  # SQLite
                cursor.execute("DELETE FROM tracker_data_invalid WHERE tracker_id = ? AND stored_at < ?", 
                              (tracker_id, cutoff_date))
        else:
            if hasattr(conn, 'getinfo'):  # Azure SQL
                cursor.execute("DELETE FROM tracker_data_invalid WHERE stored_at < ?", (cutoff_date,))
            else:  # SQLite
                cursor.execute("DELETE FROM tracker_data_invalid WHERE stored_at < ?", (cutoff_date,))
        
        deleted_count = cursor.rowcount
        conn.commit()
        LOG.info(f"Deleted {deleted_count} invalid tracker records older than {keep_days} days")
        return deleted_count
    except Exception as e:
        LOG.error(f"Error deleting invalid tracker data: {e}")
        return 0


def insert_tracker_info(conn, data):
    """
    Insert a row of tracker data into the database.

    Args:
        conn: Database connection object (SQLite or Azure SQL).
        data (dict): A dictionary containing tracker info.
    """
    try:
        # Check if it's an Azure SQL connection (has driver attribute) or SQLite
        if hasattr(conn, 'getinfo'):  # pyodbc connection
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO tracker_data (
                    tracker_id, latitude, longitude, battery, timestamp,
                    gw_rssi, gw_name, gw_latitude, gw_longitude, gw_timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data["tracker_id"],
                data["latitude"],
                data["longitude"],
                data["battery"],
                data["timestamp"],
                data["gw-rssi"],
                data["gw-name"],
                data["gw-latitude"],
                data["gw-longitude"],
                data["gw-timestamp"]
            ))
        else:  # SQLite connection
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO tracker_data (
                    tracker_id, latitude, longitude, battery, timestamp,
                    gw_rssi, gw_name, gw_latitude, gw_longitude, gw_timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data["tracker_id"],
                data["latitude"],
                data["longitude"],
                data["battery"],
                data["timestamp"],
                data["gw-rssi"],
                data["gw-name"],
                data["gw-latitude"],
                data["gw-longitude"],
                data["gw-timestamp"]
            ))
        conn.commit()
    except Exception as e:
        LOG.error(f"Database error during insert: {e}")


def get_tracker_data(conn, limit=1000):
    """
    Retrieve tracker data from the database.

    Args:
        conn: Database connection object.
        limit (int): Maximum number of records to return.

    Returns:
        list: List of tracker data dictionaries.
    """
    try:
        cursor = conn.cursor()
        if hasattr(conn, 'getinfo'):  # Azure SQL
            cursor.execute("SELECT TOP (?) tracker_id, latitude, longitude, battery, timestamp, gw_rssi, gw_name, gw_latitude, gw_longitude, gw_timestamp FROM tracker_data ORDER BY timestamp DESC", (limit,))
        else:  # SQLite
            cursor.execute("SELECT tracker_id, latitude, longitude, battery, timestamp, gw_rssi, gw_name, gw_latitude, gw_longitude, gw_timestamp FROM tracker_data ORDER BY timestamp DESC LIMIT ?", (limit,))

        columns = [column[0] for column in cursor.description]
        results = []
        for row in cursor.fetchall():
            results.append(dict(zip(columns, row)))

        return results
    except Exception as e:
        LOG.error(f"Database error during select: {e}")
        return []
