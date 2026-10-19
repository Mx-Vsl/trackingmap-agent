
import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import os
import sys
from io import BytesIO
from datetime import datetime, timedelta
import requests

# Backend connection configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
BACKEND_AVAILABLE = False
try:
    # Teste Verbindung zum Backend
    import streamlit as st
    import psycopg2, os

    try:
        # conn = get_db_connection()
        # st.success("DB connection OK ✅")
        # conn.close()
        BACKEND_AVAILABLE = True

    except Exception as e:
        st.error(e)
        BACKEND_AVAILABLE = False


    # response = requests.get(f"{BACKEND_URL}/health", timeout=5)
    # if response.status_code == 200:
    #     BACKEND_AVAILABLE = True
except Exception:
    BACKEND_AVAILABLE = False

st.set_page_config(layout="wide", page_title="Tracker Map")

EXPECTED_COLUMNS = [
    'tracker_id', 'latitude', 'longitude', 'battery', 'timestamp',
    'gw-rssi', 'gw-name', 'gw-latitude', 'gw-longitude', 'gw-timestamp'
]

COLUMN_ALIASES = {
    # tracker_id
    "tracker": "tracker_id", "trackerid": "tracker_id", "id": "tracker_id",
    "device_id": "tracker_id", "deviceid": "tracker_id",

    # coords
    "lat": "latitude", "latitude": "latitude",
    "lon": "longitude", "lng": "longitude", "long": "longitude", "longitude": "longitude",

    # timestamp
    "time": "timestamp", "datetime": "timestamp", "ts": "timestamp", "timestamp": "timestamp",
    "gwrssi": "gw-rssi", "gwlatitude": "gw-latitude", "gwlongitude": "gw-longitude",
    "gwtimestamp": "gw-timestamp", "gwname": "gw-name"
}

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename_map = {}
    for c in df.columns:
        key = str(c).strip().lower().replace(" ", "").replace("_", "")
        rename_map[c] = COLUMN_ALIASES.get(key, c)
    df = df.rename(columns=rename_map)

    for col in EXPECTED_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA
    return df

def coerce_types(df: pd.DataFrame) -> pd.DataFrame:
    for col in ["latitude", "longitude", "gw-latitude", "gw-longitude", "battery", "gw-rssi"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    else:
        df["timestamp"] = pd.NaT

    if "gw-timestamp" in df.columns:
        df["gw-timestamp"] = pd.to_datetime(df["gw-timestamp"], errors="coerce")

    return df

def drop_invalid_coords(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    mask = df["latitude"].between(-90, 90, inclusive="both") & df["longitude"].between(-180, 180, inclusive="both")
    return df[mask].copy()

def empty_df() -> pd.DataFrame:
    return pd.DataFrame(columns=EXPECTED_COLUMNS)


def get_db_connection():
    return psycopg2.connect(
        host=os.environ["POSTGRES_HOST"],
        port=os.environ["POSTGRES_PORT"],
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        sslmode="require"
    )


# -----------------------------
# Loaders
# -----------------------------
def load_from_db(limit: int = 5000) -> pd.DataFrame:
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    tracker_id,
                    latitude,
                    longitude,
                    battery,
                    timestamp,
                    gw_rssi,
                    gw_name,
                    gw_latitude,
                    gw_longitude,
                    gw_timestamp
                FROM tracker_data
                ORDER BY timestamp DESC
                LIMIT %s;
            """, (limit,))

            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()

            data = [dict(zip(columns, row)) for row in rows]
            # return json.dumps(db_data, default=str).encode('utf-8')
            df = pd.DataFrame(data)
            df = normalize_columns(df)
            df = coerce_types(df)
            df = drop_invalid_coords(df)
            return df
    finally:
        if conn is not None:
            conn.close()

def load_from_backend(limit: int = 5000) -> pd.DataFrame:
    try:
        response = requests.get(f"{BACKEND_URL}/tracker?limit={limit}", timeout=10)
        if response.status_code != 200:
            return empty_df()
        data = response.json()
        if not data:
            return empty_df()
    except Exception:
        return empty_df()

    df = pd.DataFrame(data)
    df = normalize_columns(df)
    df = coerce_types(df)
    df = drop_invalid_coords(df)
    return df

def load_from_csv_bytes(file_bytes: bytes) -> pd.DataFrame:
    # Erst normal (Komma), dann Semikolon (DE-Export)
    try:
        df = pd.read_csv(BytesIO(file_bytes))
    except Exception:
        df = pd.read_csv(BytesIO(file_bytes), sep=";")

    df = normalize_columns(df)
    df = coerce_types(df)
    df = drop_invalid_coords(df)
    return df

def load_from_csv_path(path: str) -> pd.DataFrame:
    with open(path, "rb") as f:
        return load_from_csv_bytes(f.read())

# -----------------------------
# UI: Data Source
# -----------------------------
st.sidebar.title("Data Source")

# Initialize session state
if "source_mode" not in st.session_state:
    st.session_state.source_mode = "Auto"
if "backend_limit" not in st.session_state:
    st.session_state.backend_limit = 5000
if "csv_path" not in st.session_state:
    st.session_state.csv_path = os.getenv("TRACKER_CSV_PATH", "tracker_data.csv")
if "csv_fallback_path" not in st.session_state:
    st.session_state.csv_fallback_path = os.getenv("TRACKER_CSV_PATH", "tracker_data.csv")

# Source mode selection
source_options = ["Auto", "DB", "CSV Upload", "CSV Path"]
if BACKEND_AVAILABLE:
    source_options.insert(1, "Backend")

source_mode = st.sidebar.radio("Source", source_options, key="source_mode")

# Backend limit input (always show if backend available)
if BACKEND_AVAILABLE:
    backend_limit = st.sidebar.number_input(
        "Backend limit",
        min_value=100,
        max_value=100000,
        value=st.session_state.backend_limit,
        step=100,
        key="backend_limit"
    )
else:
    backend_limit = st.session_state.backend_limit

# CSV upload (always show)
uploaded = st.sidebar.file_uploader("Upload CSV", type=["csv"], key="csv_upload")

# CSV path input (always show)
csv_path = st.sidebar.text_input("CSV Path", value=st.session_state.csv_path, key="csv_path")

# CSV fallback path input (always show for Auto mode)
csv_fallback_path = st.sidebar.text_input("CSV fallback path", value=st.session_state.csv_fallback_path, key="csv_fallback_path")

# Load data based on source mode
@st.cache_data(ttl=60)
def load_data(source_mode, backend_limit, uploaded_file, csv_path, csv_fallback_path): #TODO DB VS BACKEND!
    """Load data based on the selected source mode."""
    if source_mode == "Backend":
        if not BACKEND_AVAILABLE:
            return empty_df(), "Backend not available"
        df = load_from_backend(limit=int(backend_limit))
        if df.empty:
            return df, "Keine Backend-Daten oder Backend-Verbindung fehlgeschlagen."
        return df, "Backend"
    elif source_mode == "DB":
        df = load_from_db(limit=int(backend_limit))
        if df.empty:
            return df, "Keine DB-Daten oder DB-Verbindung fehlgeschlagen."
        return df, "DB"

    elif source_mode == "CSV Upload":
        if uploaded_file is not None:
            # Use file content hash for caching
            file_content = uploaded_file.getvalue()
            df = load_from_csv_bytes(file_content)
            return df, "CSV Upload"
        else:
            return empty_df(), "Bitte links eine CSV hochladen."

    elif source_mode == "CSV Path":
        if csv_path and os.path.exists(csv_path):
            df = load_from_csv_path(csv_path)
            return df, "CSV Path"
        else:
            return empty_df(), f"CSV nicht gefunden: {csv_path}"

    else:  # Auto
        # Try backend first
        df_db = load_from_db(limit=int(backend_limit))
        if not df_db.empty:
            return df_db, "Auto: using DB"

        # Fallback to CSV
        if csv_fallback_path and os.path.exists(csv_fallback_path):
            df = load_from_csv_path(csv_fallback_path)
            return df, "Auto: using CSV fallback path"
        else:
            return empty_df(), "Auto: Backend leer/nicht erreichbar und CSV fallback nicht gefunden."

# Load the data
df, status_message = load_data(source_mode, backend_limit, uploaded, csv_path, csv_fallback_path)

# Show status message
if status_message.startswith("Auto:"):
    st.sidebar.caption(status_message)
elif status_message.startswith("Bitte") or status_message.startswith("Keine") or status_message.startswith("CSV nicht"):
    if status_message.startswith("Bitte"):
        st.sidebar.info(status_message)
    else:
        st.sidebar.warning(status_message)
elif status_message == "Backend not available":
    st.sidebar.error(status_message)


# -----------------------------
# Colors
# -----------------------------
colors = ['red', 'blue', 'green', 'orange', 'purple', 'pink', 'brown', 'gray', 'olive', 'cyan']
tracker_colors = {}
unique_trackers = df["tracker_id"].dropna().unique().tolist() if (not df.empty and "tracker_id" in df.columns) else []
for i, tracker in enumerate(unique_trackers):
    tracker_colors[tracker] = colors[i % len(colors)]

# -----------------------------
# Filters
# -----------------------------
st.sidebar.title("Filters")

if not df.empty and "timestamp" in df.columns and not df["timestamp"].isna().all():
    min_ts = df["timestamp"].min()
    max_ts = df["timestamp"].max()

    # Ensure we have valid datetime objects
    try:
        min_dt = min_ts.to_pydatetime()
        max_dt = max_ts.to_pydatetime()
    except (AttributeError, ValueError):
        # Fallback if to_pydatetime fails
        min_dt = pd.Timestamp(min_ts).to_pydatetime()
        max_dt = pd.Timestamp(max_ts).to_pydatetime()

    if "time_filter_mode" not in st.session_state:
        st.session_state.time_filter_mode = "Slider"

    # Initialize or validate session state values
    if "start_dt" not in st.session_state or not isinstance(st.session_state.start_dt, datetime):
        st.session_state.start_dt = min_dt
    if "end_dt" not in st.session_state or not isinstance(st.session_state.end_dt, datetime):
        st.session_state.end_dt = max_dt

    # Ensure values are within valid range
    if st.session_state.start_dt < min_dt:
        st.session_state.start_dt = min_dt
    if st.session_state.start_dt > max_dt:
        st.session_state.start_dt = max_dt
    if st.session_state.end_dt < min_dt:
        st.session_state.end_dt = min_dt
    if st.session_state.end_dt > max_dt:
        st.session_state.end_dt = max_dt

    time_filter_mode = st.sidebar.radio(
        "Time selection mode",
        ["Slider", "Date & time range"],
        key="time_filter_mode"
    )

    if time_filter_mode == "Slider":
        time_range = st.sidebar.slider(
            "Time Range",
            min_value=min_dt,
            max_value=max_dt,
            value=(st.session_state.start_dt, st.session_state.end_dt),
            format="YYYY-MM-DD HH:mm",
            key="time_range"
        )
        st.session_state.start_dt, st.session_state.end_dt = time_range
    else:
        if "filter_start" not in st.session_state:
            st.session_state.filter_start = min_dt.date()
        if "filter_end" not in st.session_state:
            st.session_state.filter_end = max_dt.date()

        # For date_input, ensure min_value < max_value
        if min_dt >= max_dt:
            # If all timestamps are the same, add a small buffer
            max_dt = min_dt + timedelta(hours=1)

        # Start date and time
        st.sidebar.subheader("Startdatum & Startzeit")
        col1, col2 = st.sidebar.columns(2)
        
        with col1:
            start_date = st.date_input(
                "Startdatum",
                value=st.session_state.start_dt.date() if isinstance(st.session_state.start_dt, datetime) else st.session_state.start_dt,
                min_value=min_dt.date(),
                max_value=max_dt.date(),
                key="start_date"
            )
        
        with col2:
            start_time = st.time_input(
                "Startzeit",
                value=st.session_state.start_dt.time() if isinstance(st.session_state.start_dt, datetime) else datetime.min.time(),
                key="start_time"
            )

        # End date and time
        st.sidebar.subheader("Enddatum & Endzeit")
        col3, col4 = st.sidebar.columns(2)
        
        with col3:
            end_date = st.date_input(
                "Enddatum",
                value=st.session_state.end_dt.date() if isinstance(st.session_state.end_dt, datetime) else st.session_state.end_dt,
                min_value=min_dt.date(),
                max_value=max_dt.date(),
                key="end_date"
            )
        
        with col4:
            end_time = st.time_input(
                "Endzeit",
                value=st.session_state.end_dt.time() if isinstance(st.session_state.end_dt, datetime) else datetime.max.time(),
                key="end_time"
            )

        # Convert dates and times back to datetime for filtering
        start_dt = datetime.combine(start_date, start_time)
        end_dt = datetime.combine(end_date, end_time)

        if start_dt > end_dt:
            st.sidebar.error("Startzeit muss vor Endzeit liegen.")
            time_range = (end_dt, start_dt)
        else:
            time_range = (start_dt, end_dt)
else:
    time_range = (pd.Timestamp.min.to_pydatetime(), pd.Timestamp.max.to_pydatetime())

default_selected = st.session_state.get("selected_trackers", list(unique_trackers))
if not isinstance(default_selected, list):
    default_selected = list(unique_trackers)
else:
    default_selected = [t for t in default_selected if t in unique_trackers]
if not default_selected and unique_trackers:
    default_selected = list(unique_trackers)

selected_trackers = st.sidebar.multiselect(
    "Select Trackers",
    options=unique_trackers,
    default=default_selected,
    key="selected_trackers"
)
if not selected_trackers and unique_trackers:
    selected_trackers = unique_trackers

if "display_mode" not in st.session_state:
    st.session_state.display_mode = "Both"

display_mode = st.sidebar.radio(
    "Display Mode",
    ["Both", "Lines Only", "Points Only"],
    key="display_mode"
)

# Apply filters safely
if df.empty:
    df_filtered = df
else:
    df_filtered = df[
        (df["timestamp"] >= pd.Timestamp(time_range[0])) &
        (df["timestamp"] <= pd.Timestamp(time_range[1])) &
        (df["tracker_id"].isin(selected_trackers))
    ].copy()

# -----------------------------
# Map creation
# -----------------------------
@st.cache_data
def create_map(df_filtered, selected_trackers, display_mode, tracker_colors):
    """Create the Folium map with cached data."""
    if not df_filtered.empty:
        center_lat = df_filtered["latitude"].mean()
        center_lon = df_filtered["longitude"].mean()
    elif not df.empty:
        center_lat = df["latitude"].mean()
        center_lon = df["longitude"].mean()
    else:
        center_lat, center_lon = 0.0, 0.0

    m = folium.Map(location=[center_lat, center_lon], zoom_start=2)

    # Lines
    if display_mode in ["Both", "Lines Only"] and not df_filtered.empty:
        for tracker in selected_trackers:
            tdf = df_filtered[df_filtered["tracker_id"] == tracker].sort_values("timestamp")
            coords = tdf[["latitude", "longitude"]].dropna().values.tolist()
            if len(coords) > 1:
                folium.PolyLine(
                    locations=coords,
                    color=tracker_colors.get(tracker, "blue"),
                    weight=3,
                    opacity=0.7
                ).add_to(m)

    # Points
    if display_mode in ["Both", "Points Only"] and not df_filtered.empty:
        for _, row in df_filtered.iterrows():
            tracker_id = row["tracker_id"]
            popup_text = f"Tracker: {tracker_id}<br>Timestamp: {row['timestamp']}"
            folium.CircleMarker(
                location=[row["latitude"], row["longitude"]],
                radius=5,
                color=tracker_colors.get(tracker_id, "blue"),
                fill=True,
                fill_color=tracker_colors.get(tracker_id, "blue"),
                fill_opacity=0.8,
                popup=popup_text,
                tooltip=str(tracker_id)
            ).add_to(m)

    return m

# Create the map
m = create_map(df_filtered, selected_trackers, display_mode, tracker_colors)

# -----------------------------
# Render
# -----------------------------
st.title("Tracker Map")
st.write(f"Showing {len(df_filtered)} data points")

if df.empty:
    st.info("Keine Daten geladen.")
else:
    with st.expander("Preview (first 50 rows)"):
        st.dataframe(df_filtered.head(50))

# Use st_folium with key to prevent unnecessary reruns
st_folium(m, width=None, height=800, key="tracker_map")
