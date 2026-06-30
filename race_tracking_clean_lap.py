import pandas as pd
import numpy as np
import plotly as pl
import requests as requests
import scipy as scp
import plotly.express as px
import plotly.graph_objects as go

from datetime import datetime, timedelta
from urllib.request import urlopen
import json

#Session: Belgium 2023 Race 
session_response = requests.get(
    "https://api.openf1.org/v1/sessions",
    params={
        "country_name": "Belgium",
        "session_name": "Race",
        "year": 2023,
    },
)

session_response.raise_for_status()
sessions = session_response.json()

print(sessions)

#Session Key 
session_key = sessions[0]["session_key"]

#Start, End time
start_time = sessions[0]["date_start"]
end_time = sessions[0]["date_end"]

#Drivers in race
driver_response = requests.get(
    "https://api.openf1.org/v1/drivers",
    params={"session_key": session_key},
)
driver_response.raise_for_status()
drivers = driver_response.json()

for d in drivers:
    print(f"  {d['driver_number']:>3} - {d['full_name']} ({d['team_name']})")

#Get lap endpoints
laps_response = requests.get(
    "https://api.openf1.org/v1/laps",
    params={
        "session_key": session_key,
        "driver_number": drivers[0]["driver_number"],
    },
)

laps_response.raise_for_status()
laps = laps_response.json()

#Filtering missing data laps and pits
clean_lap = [
    lap for lap in laps
    if lap.get("date_start") and lap.get("lap_duration") and not lap.get("is_pit_out_lap")
]

#Sampling one lap
chosen_lap = clean_lap[1]

lap_start_dt = datetime.fromisoformat(chosen_lap["date_start"])
lap_end_dt = lap_start_dt + timedelta(seconds=chosen_lap["lap_duration"])

slice_start_str = lap_start_dt.strftime("%Y-%m-%dT%H:%M:%S.%f")
slice_end_str = lap_end_dt.strftime("%Y-%m-%dT%H:%M:%S.%f")

print(f"Querying location data from {slice_start_str} to {slice_end_str}")

#Take data form one driver for now
DRIVER_NUM = drivers[0]["driver_number"]
 
location_response = requests.get(
    "https://api.openf1.org/v1/location",
    params={
        "session_key": session_key,
        "driver_number": DRIVER_NUM,
        "date>": slice_start_str,
        "date<": slice_end_str,
    },
)
location_response.raise_for_status()
location_data = location_response.json()

#Find min, max for x,y coords
df = pd.DataFrame(location_data)

min_x, max_x = df["x"].min(), df["x"].max()
min_y, max_y = df["y"].min(), df["y"].max()
 
print(min_x, max_x, min_y, max_y)

# coords need to rotate 90 ccw
df["x_rot_ccw"] = -df["y"]
df["y_rot_ccw"] = df["x"]
 
fig_ccw = px.line(
    df,
    x="x_rot_ccw",
    y="y_rot_ccw",
    title="Rotated 90 degrees counterclockwise",
)
fig_ccw.update_yaxes(scaleanchor="x", scaleratio=1)
fig_ccw.show()

#animation