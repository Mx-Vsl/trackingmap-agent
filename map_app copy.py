import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import os
import sys
import logging

# Add src to path to import trackingmap_agent
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
import trackingmap_agent.tracker_db

st.set_page_config(layout="wide", page_title="Tracker Map")

# Load the tracker data
@st.cache_data(ttl=60)  # Cache for 60 seconds
def load_data():
    # Initialize database connection
    use_azure_sql = os.getenv('USE_AZURE_SQL', 'false').lower() == 'true'
    use_postgres = os.getenv('USE_POSTGRES', 'false').lower() == 'true'
    db_conn = trackingmap_agent.tracker_db.init_db(use_azure_sql=use_azure_sql, use_postgres=use_postgres)

    if db_conn is None:
        st.error("Failed to connect to database")
        return pd.DataFrame(columns=[
            'tracker_id', 'latitude', 'longitude', 'battery', 'timestamp',
            'gw-rssi', 'gw-name', 'gw-latitude', 'gw-longitude', 'gw-timestamp'
        ])

    # Get data from database
    data = trackingmap_agent.tracker_db.get_tracker_data(db_conn, limit=5000)

    if not data:
        return pd.DataFrame(columns=[
            'tracker_id', 'latitude', 'longitude', 'battery', 'timestamp',
            'gw-rssi', 'gw-name', 'gw-latitude', 'gw-longitude', 'gw-timestamp'
        ])

    df = pd.DataFrame(data)
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    else:
        df['timestamp'] = pd.NaT

    return df

df = load_daat()

# Define colors for unique trackers
colors = ['red', 'blue', 'green', 'orange', 'purple', 'pink', 'brown', 'gray', 'olive', 'cyan']
colors = ['red', 'blue', 'green', 'orange', 'purple', 'pink', 'brown', 'gray', 'olive', 'cyan']
tracker_colors = {}
if 'tracker_id' in df.columns and not df.empty:
    unique_trackers = df['tracker_id'].unique()
else:
    unique_trackers = []
for i, tracker in enumerate(unique_trackers):
    tracker_colors[tracker] = colors[i % len(colors)]

# Sidebar filters
st.sidebar.title("Filters")

# Time range filter
if not df.empty and 'timestamp' in df.columns and not df['timestamp'].isna().all():
    min_ts = df['timestamp'].min()
    max_ts = df['timestamp'].max()
    time_range = st.sidebar.slider(
        "Time Range",
        min_value=min_ts.to_pydatetime(),
        max_value=max_ts.to_pydatetime(),
        value=(min_ts.to_pydatetime(), max_ts.to_pydatetime()),
        format="YYYY-MM-DD HH:mm"
    )
else:
    time_range = (pd.Timestamp.min.to_pydatetime(), pd.Timestamp.max.to_pydatetime())

# Tracker selection
selected_trackers = st.sidebar.multiselect(
    "Select Trackers",
    options=unique_trackers,
    default=list(unique_trackers)
)

# Display mode
display_mode = st.sidebar.radio(
    "Display Mode",
    ["Both", "Lines Only", "Points Only"]
)

# Filter data
df_filtered = df[
    (df['timestamp'] >= time_range[0]) &
    (df['timestamp'] <= time_range[1]) &
    (df['tracker_id'].isin(selected_trackers))
]

# Create a map centered on the filtered data or original
if not df_filtered.empty:
    center_lat = df_filtered['latitude'].mean()
    center_lon = df_filtered['longitude'].mean()
elif not df.empty:
    center_lat = df['latitude'].mean()
    center_lon = df['longitude'].mean()
else:
    center_lat = 0.0
    center_lon = 0.0

m = folium.Map(location=[center_lat, center_lon], zoom_start=2)

# Add tracks (lines) if enabled
if display_mode in ["Both", "Lines Only"]:
    for tracker in selected_trackers:
        tracker_data = df_filtered[df_filtered['tracker_id'] == tracker].sort_values('timestamp')
        coordinates = tracker_data[['latitude', 'longitude']].values.tolist()
        if len(coordinates) > 1:
            folium.PolyLine(
                locations=coordinates,
                color=tracker_colors[tracker],
                weight=3,
                opacity=0.7
            ).add_to(m)

# Add circles if enabled
if display_mode in ["Both", "Points Only"]:
    for idx, row in df_filtered.iterrows():
        popup_text = f"Tracker: {row['tracker_id']}<br>Timestamp: {row['timestamp']}"
        folium.CircleMarker(
            location=[row['latitude'], row['longitude']],
            radius=5,
            color=tracker_colors[row['tracker_id']],
            fill=True,
            fill_color=tracker_colors[row['tracker_id']],
            fill_opacity=0.8,
            popup=popup_text,
            tooltip=row['tracker_id']
        ).add_to(m)

# Display the map in Streamlit
st.title("Tracker Map")
st.write(f"Showing {len(df_filtered)} data points")

st_folium(m, width=None, height=800)