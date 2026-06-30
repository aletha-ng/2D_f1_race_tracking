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

# Session: Belgium 2023 Sprint Qualifying
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

# Session Key 
session_key = sessions[0]["session_key"]
print(session_key)

# Time start and end
start_time = sessions[0]["date_start"]
end_time = sessions[0]["date_end"]

# Drivers participated 
driver_response = requests.get(
    "https://api.openf1.org/v1/drivers",
    params={"session_key": session_key},
)
driver_response.raise_for_status()
drivers = driver_response.json()

for d in drivers:
    print(f"  {d['driver_number']:>3} - {d['full_name']} ({d['team_name']})")
    
#### Slicing start race time 
session_start_dt = datetime.fromisoformat(start_time)
session_end_dt = datetime.fromisoformat(end_time)
slice_start_dt = session_start_dt 
slice_end_dt = session_end_dt

slice_start_str = slice_start_dt.strftime("%Y-%m-%dT%H:%M:%S")
slice_end_str = slice_end_dt.strftime("%Y-%m-%dT%H:%M:%S")

print(f"Querying location data from {slice_start_str} to {slice_end_str}")

#Fetch location for one driver for now
DRIVER_NUM= drivers[0]["driver_number"]

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

print(len(location_data))

#Find min/max x, y coords from dataFrame
df = pd.DataFrame(location_data)

min_x, max_x = df["x"].min(), df["x"].max()
min_y, max_y = df["y"].min(), df["y"].max()

print(min_x, max_x, min_y, max_y)

# plot raw x,y coords 
figure = px.line(
    df,
    x="x",
    y="y",
    title=f"Raw x/y path - Driver {DRIVER_NUM} - Spa-Francorchamps 2023",
)

figure.update_yaxes(scaleanchor="x", scaleratio=1)

# plotting transformed track 
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
df["date"] = pd.to_datetime(df["date"])
window_start = df["date"].min()
window_end = window_start + pd.Timedelta(minutes=5)
 
anim_df = df[(df["date"] >= window_start) & (df["date"] <= window_end)].copy()
print(f"Rows in animation window: {len(anim_df)}")

anim_df = df[(df["date"] >= window_start) & (df["date"] <= window_end)].copy()
print(f"Rows in animation window: {len(anim_df)}")

anim_df = anim_df.reset_index(drop=True)
anim_df["frame"] = anim_df.index

fig_anim = px.scatter(
    anim_df,
    x="x_rot_ccw",
    y="y_rot_ccw",
    animation_frame="frame",
    range_x=[df["x_rot_ccw"].min() - 500, df["x_rot_ccw"].max() + 500],
    range_y=[df["y_rot_ccw"].min() - 500, df["y_rot_ccw"].max() + 500],
    title=f"Driver {DRIVER_NUM} - live position replay (first 30 seconds, no track overlay)",
)

#full outline as a static ref 
fig_anim.update_traces(marker=dict(size=14))
fig_anim.update_yaxes(scaleanchor="x", scaleratio=1)
fig_anim.layout.updatemenus[0].buttons[0].args[1]["frame"]["duration"] = 50  # 50 ms/frame = 20 FPS
fig_anim.layout.updatemenus[0].buttons[0].args[1]["transition"]["duration"] = 0
fig_anim.show()

#plotting static track 
track_trace = go.Scatter(
    x=df["x_rot_ccw"],
    y=df["y_rot_ccw"],
    mode="lines",
    line=dict(color="black", width=2),
    name="Track",
)

car_trace = go.Scatter(
    x=[anim_df["x_rot_ccw"].iloc[0]],
    y=[anim_df["y_rot_ccw"].iloc[0]],
    mode="markers",
    marker=dict(size=14, color="red"),
    name=f"Driver {DRIVER_NUM}",
)

#frames 
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
    title=f"Driver {DRIVER_NUM} - live position replay (first 5 minutes)",
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
 