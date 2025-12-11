import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import re
import numpy as np

st.set_page_config(page_title="Jobb-Progress Tracker", layout="wide")
st.title("Jobb-Progress Tracker")
st.markdown("Den snygga versionen – med semester-Excel, prognos och allt ni vill ha")

# -------------------- Sidomeny --------------------
with st.sidebar:
    st.header("Inställningar")
    iteration_filter = st.text_input("Filtrera iteration", "Release 4.6.1 Core Uplift")
    manual_days = st.slider("Extra semesterdagar (manuell)", 0.0, 50.0, 0.0, 0.5)
    holiday_file = st.file_uploader("Semester-matrix Excel (valfritt)", type=["xlsx", "xls"])

# -------------------- Ladda upp snapshots --------------------
snapshot_files = st.file_uploader(
    "Ladda upp snapshot_CSV-filer (en eller flera)",
    type=["csv"],
    accept_multiple_files=True
)
if not snapshot_files:
    st.info("Ladda upp minst en snapshot-fil för att starta")
    st.stop()

# -------------------- Läs in alla filer --------------------
dfs = []
for f in snapshot_files:
    df = None
    for sep in [",", ";"]:
        try:
            df = pd.read_csv(f, sep=sep, engine="python", on_bad_lines="skip")
            if len(df.columns) > 5:
                break
        except:
            pass
    if df is None:
        st.error(f"Kunde inte läsa {f.name}")
        continue

    # Datum från filnamn
    try:
        date_str = f.name.split("snapshot_")[1].split(".")[0].replace("_", "-")[:10]
        snap_date = datetime.strptime(date_str, "%Y-%m-%d")
    except:
        snap_date = datetime.now()
    df["Snapshot_Date"] = snap_date
    dfs.append(df)

data = pd.concat(dfs, ignore_index=True)

# -------------------- Välj kolumner (snyggt i kolumner) --------------------
st.subheader("Välj kolumner")
c1, c2, c3 = st.columns(3)
with c1:
    iteration_col = st.selectbox("Iteration / Release", data.columns)
with c2:
    original_col = st.selectbox("Original Estimate", data.columns)
with c3:
    remaining_col = st.selectbox("Remaining Estimate", data.columns)

# Filtrera iteration
data = data[data[iteration_col].astype(str).str.contains(iteration_filter, case=False, na=False)]

# -------------------- Konvertera till minuter --------------------
def to_minutes(val):
    if pd.isna(val): return 0
    s = str(val).lower()
    h = re.search(r"(\d+\.?\d*)h", s)
    m = re.search(r"(\d+)m", s)
    total = 0
    if h: total += float(h.group(1)) * 60
    if m: total += float(m.group(1))
    if total == 0:
        nums = re.findall(r"\d+", s)
        total = float(nums[0]) if nums else 0
    return int(total)

data["Orig_Min"] = data[original_col].apply(to_minutes)
data["Rem_Min"]  = data[remaining_col].apply(to_minutes)

# -------------------- Semester-Excel (valfritt) --------------------
extra_from_excel = 0
if holiday_file:
    try:
        hx = pd.read_excel(holiday_file, header=None)
        extra_from_excel = (hx.astype(str).str.lower() == "x").sum().sum()
        st.sidebar.success(f"Semester-Excel: +{extra_from_excel} dagar")
    except:
        st.sidebar.warning("Kunde inte läsa semester-Excel")

total_extra_days = manual_days + extra_from_excel

# -------------------- Summering & graf --------------------
summary = data.groupby("Snapshot_Date").agg({
    "Orig_Min": "sum",
    "Rem_Min": "sum"
}).reset_index()
summary["Total_h"] = summary["Orig_Min"] / 60
summary["Remaining_h"] = summary["Rem_Min"] / 60
summary = summary.sort_values("Snapshot_Date")

fig = go.Figure()
fig.add_trace(go.Scatter(x=summary["Snapshot_Date"], y=summary["Total_h"],
                         mode="lines+markers", name="Totalt jobb"))
fig.add_trace(go.Scatter(x=summary["Snapshot_Date"], y=summary["Remaining_h"],
                         mode="lines+markers", name="Kvarvarande", line=dict(color="red")))
fig.update_layout(title="Burn-down Chart", height=600)
st.plotly_chart(fig, use_container_width=True)

# -------------------- Prognos --------------------
if len(summary) >= 2 and summary["Remaining_h"].iloc[-1] < summary["Remaining_h"].iloc[0]:
    x = np.arange(len(summary))
    y = summary["Remaining_h"].values
    slope, intercept = np.polyfit(x, y, 1)
    days_left = int(np.ceil(-intercept / slope))
    last_date = summary["Snapshot_Date"].iloc[-1].date()
    finish = last_date + timedelta(days=days_left)
    finish_adj = finish + timedelta(days=int(total_extra_days))

    col1, col2 = st.columns(2)
    col1.metric("Prognos utan semester", finish.strftime("%Y-%m-%d"))
    col2.metric("Med semesterjustering", finish_adj.strftime("%Y-%m-%d"),
                f"+{total_extra_days:.1f} dagar")

st.download_button("Ladda ner all data", data.to_csv(index=False).encode(), "progress_all.csv")
st.balloons()
st.success("KLAR! Nu har ni den snygga versionen – och den kommer aldrig mer spöka")
