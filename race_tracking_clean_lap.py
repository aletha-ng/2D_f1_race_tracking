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

#Take data from two driver for now
DRIVER_NUM = drivers[0]["driver_number"], drivers[15]["driver_number"]

location_data_per_driver = {}

for driver_num in DRIVER_NUM:
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
    location_data_per_driver[driver_num] = pd.DataFrame(response.json())
    print(f"Driver {driver_num}: {len(location_data_per_driver[driver_num])} rows")

#Find min, max for x,y coords
all_drivers_df = pd.concat(location_data_per_driver.values(), ignore_index=True)

# Apply the rotation to the combined df
all_drivers_df["x_rot_ccw"] = -all_drivers_df["y"]
all_drivers_df["y_rot_ccw"] = all_drivers_df["x"]
 
#min max from combined dataset
min_x = all_drivers_df["x_rot_ccw"].min()
max_x = all_drivers_df["x_rot_ccw"].max()
min_y = all_drivers_df["y_rot_ccw"].min()
max_y = all_drivers_df["y_rot_ccw"].max()

print(f"x range: {min_x} to {max_x}")
print(f"y range: {min_y} to {max_y}")

# coords need to rotate 90 ccw
for driver_num, df in location_data_per_driver.items():
    df["x_rot_ccw"] = -df["y"]
    df["y_rot_ccw"] = df["x"]

#interpolation <---- start from here to modify two drivers
fig_ccw = px.line(
    df,
    x="x_rot_ccw",
    y="y_rot_ccw",
    title="Rotated 90 degrees counterclockwise",
)
fig_ccw.update_yaxes(scaleanchor="x", scaleratio=1)
fig_ccw.show()

#animation
df["date"] = pd.to_datetime(df["date"])

anim_df = df.copy().reset_index(drop=True)
print(f"Rows in animation window: {len(anim_df)}")

track_trace = go.Scatter(
    x=df["x_rot_ccw"],
    y=df["y_rot_ccw"],
    mode="lines",
    line=dict(color="lightgray", width=2),
    name="Track",
)
 
car_trace = go.Scatter(
    x=[anim_df["x_rot_ccw"].iloc[0]],
    y=[anim_df["y_rot_ccw"].iloc[0]],
    mode="markers",
    marker=dict(size=14, color="red"),
    name=f"Driver {DRIVER_NUM}",
)

#updating frames
frames = [
    go.Frame(
        data=[
            go.Scatter(
                x=[row["x_rot_ccw"]],
                y=[row["y_rot_ccw"]],
            )
        ],
        traces=[1],  # tells Plotly this frame updates trace index 1 (the dot)
        name=str(i),
    )
    for i, row in anim_df.iterrows()
]

fig_anim = go.Figure(
    data=[track_trace, car_trace],
    frames=frames,
)

fig_anim.update_layout(
    title=f"Driver {DRIVER_NUM} - live position replay (lap {chosen_lap['lap_number']})",
    xaxis=dict(range=[df["x_rot_ccw"].min() - 500, df["x_rot_ccw"].max() + 500]),
    yaxis=dict(range=[df["y_rot_ccw"].min() - 500, df["y_rot_ccw"].max() + 500]),
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
fig_anim.show()
