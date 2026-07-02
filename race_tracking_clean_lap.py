import pandas as pd
import numpy as np
import plotly as pl
import requests as requests
import scipy as scp
import plotly.express as px
import plotly.graph_objects as go
import plotly.colors as pc

from datetime import datetime, timedelta
from urllib.request import urlopen
from scipy.interpolate import interp1d
import json
import time
import os

from f1_constants import TEAM_COLORS

CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

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

#Getting information abt race and track 
session = session_response.json()[0]
race_date = datetime.fromisoformat(session["date_start"]).strftime("%d %b %Y")
country = session["country_name"]
circuit = session["circuit_short_name"]

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

#Take data from two driver for now
DRIVER_NUM = tuple(d["driver_number"] for d in drivers)

location_data_per_driver = {}

#CACHE FOR DRIVER LAPS COORDS 
for driver_num in DRIVER_NUM:
    cache_file = f"{CACHE_DIR}/session_{session_key}_driver_{driver_num}_lap{chosen_lap['lap_number']}.json"
    
    if os.path.exists(cache_file):
        print(f"Loading cached data for driver {driver_num} from {cache_file}")
        with open(cache_file, "r") as f:
            data = json.load(f)
        print(f"Driver {driver_num}: {len(data)} rows loaded from cache")
    else:
        response = requests.get(
            "https://api.openf1.org/v1/location",
            params={
                "session_key": session_key,
                "driver_number": driver_num,
                "date>": slice_start_str,
                "date<": slice_end_str,
            },
        )
        response.raise_for_status()
        data = response.json()
        if not data:
            print(f"Driver {driver_num}: no data, skipping")
            continue
        with open(cache_file, "w") as f:
            json.dump(data, f)
        print(f"Driver {driver_num}: {len(data)} rows fetched and cached to {cache_file}")
        time.sleep(0.4)
    
    location_data_per_driver[driver_num] = pd.DataFrame(data)
    
# for driver_num in DRIVER_NUM:
#     response = requests.get(
#         "https://api.openf1.org/v1/location",
#         params={
#             "session_key": session_key,
#             "driver_number": driver_num,
#             "date>": slice_start_str,
#             "date<": slice_end_str,
#         },
#     )
#     response.raise_for_status()
#     data = response.json()
#     if not data:
#         print(f"Driver {driver_num}: no data, skipping")
#         continue
#     location_data_per_driver[driver_num] = pd.DataFrame(data)
#     print(f"Driver {driver_num}: {len(location_data_per_driver[driver_num])} rows")
#     time.sleep(0.4)

for driver_num, df in location_data_per_driver.items():
    df["x_rot_ccw"] = -df["y"]
    df["y_rot_ccw"] = df["x"]

#Find min, max for x,y coords
all_drivers_df = pd.concat(location_data_per_driver.values(), ignore_index=True)

#filtering out GPS outliers 
x_low, x_high = all_drivers_df["x_rot_ccw"].quantile([0.02, 0.98])
y_low, y_high = all_drivers_df["y_rot_ccw"].quantile([0.02, 0.98])

track_df = location_data_per_driver[1][  # driver 1 = Verstappen
    (location_data_per_driver[1]["x_rot_ccw"].between(x_low, x_high)) &
    (location_data_per_driver[1]["y_rot_ccw"].between(y_low, y_high))
].sort_values("date").reset_index(drop=True)
 
#min max from combined dataset
min_x = track_df["x_rot_ccw"].min()
max_x = track_df["x_rot_ccw"].max()
min_y = track_df["y_rot_ccw"].min()
max_y = track_df["y_rot_ccw"].max()

print(f"x range: {min_x} to {max_x}")
print(f"y range: {min_y} to {max_y}")

# coords need to rotate 90 ccw
for driver_num, df in location_data_per_driver.items():
    df["x_rot_ccw"] = -df["y"]
    df["y_rot_ccw"] = df["x"]
    
#interpolation 
#convert drivers date to seconds 
lap_start_ts = pd.Timestamp(slice_start_str, tz="UTC")

for driver_num, df in location_data_per_driver.items():
    df["date"] = pd.to_datetime(df["date"])
    df["t_sec"] = (df["date"] - lap_start_ts).dt.total_seconds()

#adjusting for cars to share same timeline
t_start = max(df["t_sec"].min() for df in location_data_per_driver.values())
t_end = min(df["t_sec"].max() for df in location_data_per_driver.values())
t_common = np.arange(t_start, t_end, 0.2)

print(f"Shared timeline: {len(t_common)} frames at 0.1s intervals")

interpolated={}

for driver_num, df in location_data_per_driver.items():
    interp_x = interp1d(df["t_sec"], df["x_rot_ccw"], kind="linear")
    interp_y = interp1d(df["t_sec"], df["y_rot_ccw"], kind="linear")
    
    interpolated[driver_num] = {
        "x": interp_x(t_common),
        "y": interp_y(t_common),
    }
    
    print(f"Driver {driver_num}: interpolated to {len(t_common)} frames")

#plotting figures (static)
fig_ccw = px.line(
    df,
    x="x_rot_ccw",
    y="y_rot_ccw",
    title="Rotated 90 degrees counterclockwise",
)
fig_ccw.update_yaxes(scaleanchor="x", scaleratio=1)

#animation, for multi-driver
df["date"] = pd.to_datetime(df["date"])

anim_df = df.copy().reset_index(drop=True)
print(f"Rows in animation window: {len(anim_df)}")

track_trace = go.Scatter(
    x=track_df["x_rot_ccw"],
    y=track_df["y_rot_ccw"],
    mode="lines",
    line=dict(color="lightgray", width=2),
    name="Track",
)
 
#driver team colors
driver_colors = {
    d["driver_number"]: TEAM_COLORS.get(d["team_name"], "white")
    for d in drivers
    if d["driver_number"] in location_data_per_driver
}

#setting driver name on labels
driver_names = {
    d["driver_number"]: d.get("name_acronym", str(d["driver_number"]))
    for d in drivers
}

car_trace = [
    go.Scatter(
        x=[interpolated[driver_num]["x"][0]],
        y=[interpolated[driver_num]["y"][0]],
        mode="markers",
        marker=dict(size=14, color=driver_colors.get(driver_num, "white")),
        name=driver_names.get(driver_num, str(driver_num)),
    )
    for driver_num in location_data_per_driver
]

#updating frames
car_trace_indices = list(range(1, len(DRIVER_NUM) + 1))

frames = [
    go.Frame(
        data=[
            go.Scatter(
                x=[interpolated[driver_num]["x"][i]],
                y=[interpolated[driver_num]["y"][i]],
            )
            for driver_num in DRIVER_NUM
        ],
        traces=car_trace_indices, 
        name=str(i),
    )
    for i in range(len(t_common))
]

fig_anim = go.Figure(
    data=[track_trace] + car_trace,
    frames=frames,
)

fig_anim.update_layout(
    title=f"{country} Grand Prix {race_date} - {circuit} | Lap {chosen_lap['lap_number']}",
    paper_bgcolor="black",
    plot_bgcolor="black",
    font=dict(color="red"),
    width=1260,
    height=600,
    margin=dict(l=0, r=0, t=50, b=0),
    xaxis=dict(
        range=[min_x - 500, max_x + 500],
        showgrid=False,
        zeroline=False,
        showticklabels=False,
    ),
    yaxis=dict(
         range=[min_y - 500, max_y + 500],
        showgrid=False,
        zeroline=False,
        showticklabels=False,
    ),
    updatemenus=[
        dict(
            type="buttons",
            buttons=[
                dict(
                    label="Play",
                    method="animate",
                    args=[
                        None,
                        {
                            "frame": {"duration": 50, "redraw": True},
                            "transition": {"duration": 0},
                            "fromcurrent": True,
                        },
                    ],
                ),
                dict(
                    label="Pause",
                    method="animate",
                    args=[
                        [None],
                        {
                            "frame": {"duration": 0, "redraw": False},
                            "mode": "immediate",
                        },
                    ],
                ),
            ],
        )
    ],
)
 
fig_anim.update_yaxes(scaleanchor="x", scaleratio=1)
fig_anim.show(config={"displayModeBar": False})
