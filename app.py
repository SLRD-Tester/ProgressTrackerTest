import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import re

st.set_page_config(page_title="Progress Tracker", layout="wide")
st.title("Progress Tracker – väljer kolumner själv")

# -------------------- UPLOAD --------------------
snapshot_files = st.file_uploader(
    "Ladda upp snapshot_CSV-filer (en eller flera)",
    type=["csv"],
    accept_multiple_files=True
)

if not snapshot_files:
    st.info("Ladda upp minst en fil för att fortsätta")
    st.stop()

# -------------------- LÄS IN ALLA --------------------
dfs = []
for file in snapshot_files:
    df = None
    for sep in [",", ";"]:
        try:
            df = pd.read_csv(file, sep=sep, on_bad_lines="skip", engine="python")
            if len(df.columns) > 3:
                break
        except:
            continue
    if df is None:
        st.error(f"Kunde inte läsa {file.name}")
        continue

    # Försök hitta datum från filnamnet
    try:
        date_str = file.name.split("snapshot_")[-1].split(".")[0].replace("_", "-")[:10]
        snap_date = datetime.strptime(date_str, "%Y-%m-%d")
    except:
        snap_date = datetime.now()

    df["Snapshot_Date"] = snap_date
    dfs.append(df)

if not dfs:
    st.stop()

data = pd.concat(dfs, ignore_index=True)

# -------------------- VÄLJ KOLUMNER SJÄLV --------------------
st.subheader("Välj vilka kolumner som innehåller vad")
cols = list(data.columns)

col1, col2, col3 = st.columns(3)
with col1:
    iteration_col = st.selectbox("Iteration / Release", cols)
with col2:
    original_est_col = st.selectbox("Original Estimate (total tid)", cols)
with col3:
    remaining_est_col = st.selectbox("Remaining Estimate (tid kvar)", cols)

# Filtrera iteration
iteration_filter = st.text_input("Filtrera på del av iteration (valfritt)", "")
if iteration_filter:
    data = data[data[iteration_col].astype(str).str.contains(iteration_filter, case=False, na=False)]

# -------------------- KONVERTERA TID --------------------
def to_minutes(val):
    if pd.isna(val): return 0
    s = str(val).lower()
    if not s or "null" in s or "nan" in s: return 0
    h = re.search(r"(\d+(?:\.\d+)?)\s*h", s)
    m = re.search(r"(\d+)\s*m", s)
    total = 0
    if h: total += float(h.group(1)) * 60
    if m: total += float(m.group(1))
    if total == 0:
        nums = re.findall(r"\d+", s)
        if nums: total = float(nums[0])
    return int(total)

data["Original_Min"] = data[original_est_col].apply(to_minutes)
data["Remaining_Min"] = data[remaining_est_col].apply(to_minutes)

# -------------------- SEMESTER (valfritt) --------------------
manual_days = st.slider("Extra semesterdagar", 0.0, 50.0, 0.0, 0.5)
holiday_file = st.file_uploader("Semester-Excel (valfritt)", type=["xlsx", "xls"])
extra_from_file = 0
if holiday_file:
    try:
        hx = pd.read_excel(holiday_file, header=None)
        extra_from_file = (hx.astype(str).str.lower() == "x").sum().sum()
        st.success(f"Hittade {extra_from_file} semesterdagar i Excel")
    except:
        st.warning("Kunde inte läsa semester-excel")

total_extra = manual_days + extra_from_file

# -------------------- PROGNOS --------------------
summary = data.groupby("Snapshot_Date").agg({
    "Original_Min": "sum",
    "Remaining_Min": "sum"
}).reset_index()
summary["Total_H"] = summary["Original_Min"] / 60
summary["Remaining_H"] = summary["Remaining_Min"] / 60
summary = summary.sort_values("Snapshot_Date")

fig = go.Figure()
fig.add_trace(go.Scatter(x=summary["Snapshot_Date"], y=summary["Total_H"],
                         mode="lines+markers", name="Totalt"))
fig.add_trace(go.Scatter(x=summary["Snapshot_Date"], y=summary["Remaining_H"],
                         mode="lines+markers", name="Kvar", line=dict(color="red")))
fig.update_layout(title="Burn-down", xaxis_title="Datum", yaxis_title="Timmar")
st.plotly_chart(fig, use_container_width=True)

# Prognos
prognos = None
if len(summary) >= 2:
    x = list(range(len(summary)))
    y = summary["Remaining_H"].values
    slope = (y[-1] - y[0]) / (x[-1] - x[0])
    if slope < 0:
        days_left = int(summary["Remaining_H"].iloc[-1] / -slope) + 1
        last_date = summary["Snapshot_Date"].iloc[-1].date()
        prognos = last_date + timedelta(days=days_left)
        prognos_semester = prognos + timedelta(days=int(total_extra))

st.metric("Senaste snapshot", summary["Snapshot_Date"].iloc[-1].strftime("%Y-%m-%d"))
st.metric("Totalt jobb", f"{summary['Total_H'].iloc[-1]:.0f} h")
st.metric("Kvarvarande", f"{summary['Remaining_H'].iloc[-1]:.0f} h")
if prognos:
    st.success(f"Prognos färdig: {prognos.strftime('%Y-%m-%d')}")
    st.success(f"Med semester: {(prognos + timedelta(days=int(total_extra))).strftime('%Y-%m-%d')} (+{total_extra:.1f} dagar)")

st.download_button("Ladda ner data", data.to_csv(index=False).encode(), "progress.csv")
st.balloons()
st.success("KLAR! Nu funkar det – du valde kolumnerna själv")
