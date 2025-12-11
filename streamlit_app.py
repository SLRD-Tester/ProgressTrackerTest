import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import re

st.title("Progress Tracker – funkar direkt")

files = st.file_uploader("Ladda upp snapshot_CSV", type="csv", accept_multiple_files=True)
if not files:
    st.stop()

dfs = []
for f in files:
    df = pd.read_csv(f, sep=None, engine="python", on_bad_lines="skip")
    try:
        d = f.name.split("snapshot_")[1].split(".")[0].replace("_", "-")
        df["Date"] = pd.to_datetime(d[:10])
    except:
        df["Date"] = pd.Timestamp.today()
    dfs.append(df)

data = pd.concat(dfs, ignore_index=True)

cols = list(data.columns)
orig = st.selectbox("Original Estimate", cols)
rem = st.selectbox("Remaining Estimate", cols)

def min(x):
    try:
        s = str(x).lower()
        h = re.search(r"(\d+\.?\d*)h", s)
        m = re.search(r"(\d+)m", s)
        t = 0
        if h: t += float(h.group(1))*60
        if m: t += float(m.group(1))
        if t == 0: t = float(re.search(r"\d+", s).group())
        return int(t)
    except:
        return 0

data["O"] = data[orig].apply(min)
data["R"] = data[rem].apply(min)

s = data.groupby("Date").sum()[["O","R"]]/60
s = s.reset_index().sort_values("Date")

fig = go.Figure()
fig.add_trace(go.Scatter(x=s["Date"], y=s["O"], name="Totalt"))
fig.add_trace(go.Scatter(x=s["Date"], y=s["R"], name="Kvar", line=dict(color="red")))
st.plotly_chart(fig, use_container_width=True)

extra = st.slider("Extra semesterdagar", 0, 50, 0)
if len(s) > 1 and s["R"].iloc[-1] < s["R"].iloc[0]:
    slope_per_day = (s["R"].iloc[-1] - s["R"].iloc[0]) / len(s)
    days_left = int(s["R"].iloc[-1] / -slope_per_day) + 1
    finish = s["Date"].iloc[-1] + timedelta(days=days_left)
    st.success(f"Utan semester: {finish.date()}")
    st.success(f"Med {extra} dagar: {(finish + timedelta(days=extra)).date()}")

st.balloons()
