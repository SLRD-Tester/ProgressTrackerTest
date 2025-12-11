# streamlit_app.py – kopiera ALLT detta till en NY fil i ditt repo (Add file → streamlit_app.py)

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import re
import numpy as np

st.set_page_config(page_title="Test Progress Dashboard", layout="wide")
st.title("Test Execution Progress Dashboard")
st.markdown("**Med semesterjusterad prognos · Svensk kalender · Burn-down · Prognos**")

# ==================== SIDEBAR ====================
with st.sidebar:
    st.header("Inställningar")
    iteration_filter = st.text_input("Iteration att filtrera", "Release 4.6.1 Core Uplift")
    hours_per_day = st.number_input("Effektiva testtimmar per person/dag", value=6.0, step=0.5)
    manual_extra_days = st.slider("Manuella extra semesterdagar", 0.0, 40.0, 0.0, 0.1)

    st.markdown("---")
    holiday_file = st.file_uploader("Semester-matrix Excel (valfritt – ger exakt justering)", type=["xlsx", "xls"])
    snapshot_files = st.file_uploader(
        "Snapshot CSV-filer (snapshot_YYYY_MM_DD.csv)",
        type=["csv"],
        accept_multiple_files=True
    )

if not snapshot_files:
    st.info("Ladda upp minst en snapshot-fil för att fortsätta")
    st.stop()

# ==================== LÄS IN DATA ====================
@st.cache_data
def load_snapshots(files):
    dfs = []
    for f in files:
        df = None
        for sep in [",", ";"]:
            try:
                df = pd.read_csv(f, sep=sep, engine="python", on_bad_lines="skip")
                if len(df.columns) > 5:
                    break
            except:
                continue
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
    return pd.concat(dfs, ignore_index=True) if dfs else None

data = load_snapshots(snapshot_files)
data = data[data["Iteration"].astype(str).str.contains(iteration_filter, case=False, na=False)]

# ==================== KONVERTERA ESTIMATE ====================
def estimate_to_minutes(estimate):
    if pd.isna(estimate): return 0
    s = str(estimate).lower()
    if not s or s in ["", "null", "-"]: return 0
    hrs = re.search(r"(\d+(?:\.\d+)?)h", s)
    mins = re.search(r"(\d+)m", s)
    total = 0
    if hrs: total += float(hrs.group(1)) * 60
    if mins: total += float(mins.group(1))
    if total == 0:
        num = re.search(r"\d+", s)
        total = float(num.group()) if num else 0
    return int(round(total))

data["Est_Min"] = data["Original Estimate"].apply(estimate_to_minutes)
data["Rem_Min"] = data["Remaining Estimate"].apply(estimate_to_minutes)

# ==================== SEMESTER-JUSTERING ====================
swedish_holidays = {"12-24", "12-25", "12-26", "01-01", "01-06"}
extra_days = manual_extra_days

if holiday_file:
    try:
        hx = pd.read_excel(holiday_file, header=None)
        x_count = (hx.astype(str).str.lower() == "x").sum().sum()
        extra_days += x_count
        st.sidebar.success(f"Semester-Excel: +{x_count} persondagar")
    except:
        st.sidebar.warning("Kunde inte läsa semester-Excel")

# ==================== SUMMERING PER SNAPSHOT ====================
summary = data.groupby("Snapshot_Date").agg(
    Total_Min=("Est_Min", "sum"),
    Remaining_Min=("Rem_Min", "sum")
).reset_index()
summary["Total_h"] = summary["Total_Min"] / 60
summary["Remaining_h"] = summary["Remaining_Min"] / 60
summary = summary.sort_values("Snapshot_Date")

# ==================== BURN-DOWN CHART ====================
fig = go.Figure()
fig.add_trace(go.Scatter(x=summary["Snapshot_Date"], y=summary["Total_h"],
                         mode="lines+markers", name="Totalt arbete", line=dict(color="#1f77b4")))
fig.add_trace(go.Scatter(x=summary["Snapshot_Date"], y=summary["Remaining_h"],
                         mode="lines+markers", name="Kvarvarande", line=dict(color="#d62728")))
fig.update_layout(title="Burn-down Chart", height=550, hovermode="x unified")
st.plotly_chart(fig, use_container_width=True)

# ==================== PROGNOS ====================
if len(summary) >= 2:
    x = np.arange(len(summary))
    y = summary["Remaining_h"].values
    slope, intercept = np.polyfit(x, y, 1)

    if slope < 0:
        days_needed = int(np.ceil(-intercept / slope))
        last_date = summary["Snapshot_Date"].iloc[-1].date()

        # Justera för svenska helgdagar i prognosperioden
        cursor = last_date + timedelta(days=1)
        end = last_date + timedelta(days=days_needed + int(extra_days))
        while cursor <= end:
            if cursor.strftime("%m-%d") in swedish_holidays:
                extra_days += 1
            cursor += timedelta(days=1)

        original_finish = last_date + timedelta(days=days_needed)
        adjusted_finish = original_finish + timedelta(days=int(extra_days))

        col1, col2 = st.columns(2)
        col1.metric("Prognos utan justering", original_finish.strftime("%Y-%m-%d"))
        col2.metric("Med semester & helgdagar", adjusted_finish.strftime("%Y-%m-%d"),
                    f"+{extra_days:.1f} dagar")

# ==================== SENASTE SNAPSHOT ====================
latest = summary.iloc[-1]
c1, c2, c3 = st.columns(3)
c1.metric("Senaste snapshot", latest["Snapshot_Date"].strftime("%Y-%m-%d"))
c2.metric("Totalt arbete", f"{latest['Total_h']:.1f} h")
c3.metric("Kvarvarande", f"{latest['Remaining_h']:.1f} h")

# ==================== NERLADDNING ====================
st.download_button(
    "Ladda ner sammanställd data",
    data.to_csv(index=False).encode(),
    f"progress_{datetime.now().strftime('%Y%m%d')}.csv",
    "text/csv"
)

st.balloons()
st.success("KLAR! Nu har ni exakt samma dashboard som innan – fast som en modern webbapp som alla kan använda")
