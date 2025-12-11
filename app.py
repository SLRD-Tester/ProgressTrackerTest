import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import re

st.set_page_config(page_title="Progress Tracker", layout="wide")
st.title("Jobb-Progress Tracker – klicka själv vilka kolumner som är vad")

# -------------------- Ladda upp filer --------------------
snapshot_files = st.file_uploader(
    "Ladda upp era snapshot_CSV-filer (en eller flera)",
    type=["csv"],
    accept_multiple_files=True
)

holiday_file = st.file_uploader("Semester-Excel (valfritt – bara om ni vill)", type=["xlsx", "xls"])

if not snapshot_files:
    st.info("Ladda upp minst en snapshot-fil för att fortsätta")
    st.stop()

# -------------------- Läs in alla filer --------------------
dfs = []
for file in snapshot_files:
    for sep in [",", ";"]:
        try:
            df = pd.read_csv(file, sep=sep, on_bad_lines="skip", engine="python")
            if len(df.columns) > 3:
                # Försök hitta datum från filnamnet
                try:
                    date_part = file.name.split("snapshot_")[-1].split(".")[0].replace("_", "-")[:10]
                    snap_date = datetime.strptime(date_part, "%Y-%m-%d")
                except:
                    snap_date = datetime.now()
                df["Snapshot_Date"] = snap_date
                dfs.append(df)
                break
        except:
            continue

if not dfs:
    st.error("Kunde inte läsa någon fil")
    st.stop()

data = pd.concat(dfs, ignore_index=True)

# -------------------- Låt användaren välja kolumner själv --------------------
st.write("### Välj vilka kolumner som innehåller vad:")
cols = ["Välj kolumn..."] + list(data.columns)

iteration_col = st.selectbox("Iteration / Release-kolumn", cols, index=0)
est_col = st.selectbox("Original Estimate-kolumn (tid från början)", cols, index=0)
rem_col = st.selectbox("Remaining Estimate-kolumn (tid kvar)", cols, index=0)

if "Välj kolumn..." in [iteration_col, est_col, rem_col]:
    st.warning("Välj alla tre kolumner ovan för att fortsätta")
    st.stop()

# Filtrera på iteration
iteration_filter = st.text_input("Skriv del av iteration (t.ex. '4.6.1' eller 'Core')", "")
if iteration_filter:
    data = data[data[iteration_col].astype(str).str.contains(iteration_filter, case=False, na=False)]

# -------------------- Konvertera tid till minuter --------------------
def to_min(x):
    if pd.isna(x): return 0
    s = str(x)
    h = re.search(r"(\d+(?:\.\d+)?)h", s, re.I)
    m = re.search(r"(\d+)m", s, re.I)
    val = 0
    if h: val += float(h.group(1)) * 60
    if m: val += float(m.group(1))
    if val == 0:
        nums = re.findall(r"\d+", s)
        val = float(nums[0]) if nums else 0
    return int(val)

data["Est_Min"] = data[est_col].apply(to_min)
data["Rem_Min"] = data[rem_col].apply(to_min)

# -------------------- Semesterjustering --------------------
manual_days = st.slider("Extra semesterdagar (manuellt)", 0.0, 50.0, 0.0, 0.5)
extra_from_excel = 0
if holiday_file:
    try:
        hx = pd.read_excel(holiday_file, header=None)
        extra_from_excel = hx.astype(str).str.lower().applymap(lambda x: "x" in x).sum().sum()
        st.success(f"Hittade {extra_from_excel} 'x' i semester-excel → +{extra_from_excel} dagar")
    except:
        st.warning("Kunde inte läsa semester-excel")

total_extra_days = manual_days + extra_from_excel

# -------------------- Prognos --------------------
summary = data.groupby("Snapshot_Date").agg({
    "Est_Min": "sum",
    "Rem_Min": "sum"
}).reset_index()
summary["Total_H"] = summary["Est_Min"] / 60
summary["Remaining_H"] = summary["Rem_Min"] / 60
summary = summary.sort_values("Snapshot_Date")

# Burn-down chart
fig = go.Figure()
fig.add_trace(go.Scatter(x=summary["Snapshot_Date"], y=summary["Total_H"], mode="lines+markers", name="Totalt jobb"))
fig.add_trace(go.Scatter(x=summary["Snapshot_Date"], y=summary["Remaining_H"], mode="lines+markers", name="Kvarvarande", line=dict(color="red")))
fig.update_layout(title="Burn-down Chart", xaxis_title="Datum", yaxis_title="Timmar")

# Prognos
prognos = None
if len(summary) >= 2:
    x = list(range(len(summary)))
    y = summary["Remaining_H"].values
    slope, intercept = np.polyfit(x, y, 1)
    if slope < 0:
        days_left = int(-intercept / slope) + 1
        last_date = summary["Snapshot_Date"].iloc[-1].date()
        prognos = last_date + timedelta(days=days_left)
        prognos_med_semester = prognos + timedelta(days=int(total_extra_days))

# -------------------- Visa allt --------------------
c1, c2, c3, c4 = st.columns(4)
c1.metric("Senaste snapshot", summary["Snapshot_Date"].iloc[-1].strftime("%Y-%m-%d"))
c2.metric("Totalt jobb", f"{summary['Total_H'].iloc[-1]:.0f} h")
c3.metric("Kvarvarande", f"{summary['Remaining_H'].iloc[-1]:.0f} h")
if prognos:
    c4.metric("Prognos färdig", prognos.strftime("%Y-%m-%d"))

if prognos:
    st.success(f"Prognos utan semester: {prognos.strftime('%Y-%
