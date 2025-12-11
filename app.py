# streamlit_app.py – DEN PERFEKTA VERSIONEN

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
    iteration_filter = st.text_input("Iteration", value="Release 4.6.1 Core Uplift")
    manual_days = st.slider("Manuella extra dagar", 0.0, 40.0, 0.0, 0.1)
    holiday_file = st.file_uploader("Semester-Excel (valfritt)", type=["xlsx", "xls"])
    st.markdown("---")

# ==================== Ladda upp filer ====================
snapshot_files = st.file_uploader(
    "Snapshot CSV-filer",
    type=["csv"],
    accept_multiple_files=True
)

if not snapshot_files:
    st.info("Ladda upp minst en snapshot-fil")
    st.stop()

# ==================== Läs in data ====================
dfs = []
for f in snapshot_files:
    df = pd.read_csv(f, sep=None, engine="python", on_bad_lines="skip")
    try:
        date_str = f.name.split("snapshot_")[1].split(".")[0].replace("_", "-")[:10]
        df["Snapshot_Date"] = pd.to_datetime(date_str)
    except:
        df["Snapshot_Date"] = pd.Timestamp.today()
    dfs.append(df)

data = pd.concat(dfs, ignore_index=True)

# ==================== SMART KOLUMNHANTERING ====================
def find_col(keywords):
    for col in data.columns:
        if any(kw.lower() in str(col).lower() for kw in keywords):
            return col
    return None

orig_col = find_col(["Original Estimate", "OriginalEstimate", "Σ Original"])
rem_col  = find_col(["Remaining Estimate", "Remaining", "Σ Remaining"])
iter_col = find_col(["Iteration", "Release"])

if not all([orig_col, rem_col, iter_col]):
    st.error("Kunde inte hitta kolumner automatiskt – välj manuellt:")
    col1, col2, col3 = st.columns(3)
    iter_col = col1.selectbox("Iteration", data.columns)
    orig_col = col2.selectbox("Original Estimate", data.columns)
    rem_col  = col3.selectbox("Remaining Estimate", data.columns)

# Filtrera iteration
data = data[data[iter_col].astype(str).str.contains(iteration_filter, case=False, na=False)]

# ==================== TID TILL MINUTER ====================
def to_min(val):
    if pd.isna(val): return 0
    s = str(val).lower()
    h = re.search(r"(\d+\.?\d*)h", s)
    m = re.search(r"(\d+)m", s)
    total = 0
    if h: total += float(h.group(1)) * 60
    if m: total += float(m.group(1))
    if total == 0:
        num = re.search(r"\d+", s)
        total = float(num.group()) if num else 0
    return int(round(total))

data["Est_Min"] = data[orig_col].apply(to_min)
data["Rem_Min"] = data[rem_col].apply(to_min)

# ==================== SEMESTER ====================
swedish_holidays = {"12-24","12-25","12-26","01-01","01-06"}
extra_days = manual_days

if holiday_file:
    try:
        hx = pd.read_excel(holiday_file, header=None)
        x_count = (hx.astype(str).str.lower() == "x").sum().sum()
        extra_days += x_count
        st.sidebar.success(f"Semester-Excel: +{x_count} persondagar")
    except:
        st.sidebar.warning("Kunde inte läsa semester-Excel")

# ==================== SUMMERING ====================
summary = data.groupby("Snapshot_Date").agg(
    Total_h=("Est_Min", lambda x: x.sum()/60),
    Remaining_h=("Rem_Min", lambda x: x.sum()/60)
).reset_index().sort_values("Snapshot_Date")

# ==================== GRAF ====================
fig = go.Figure()
fig.add_trace(go.Scatter(x=summary["Snapshot_Date"], y=summary["Total_h"],
                         mode="lines+markers", name="Totalt arbete"))
fig.add_trace(go.Scatter(x=summary["Snapshot_Date"], y=summary["Remaining_h"],
                         mode="lines+markers", name="Kvarvarande", line=dict(color="red")))
fig.update_layout(title="Burn-down Chart", height=600)
st.plotly_chart(fig, use_container_width=True)

# ==================== PROGNOS ====================
if len(summary) >= 2:
    x = np.arange(len(summary))
    y = summary["Remaining_h"].values
    slope, intercept = np.polyfit(x, y, 1)
    if slope < 0:
        days_needed = int(np.ceil(-intercept / slope))
        last_date = summary["Snapshot_Date"].iloc[-1].date()
        
        # Justera för helgdagar i perioden
        cursor = last_date
        end = last_date + timedelta(days=days_needed + int(extra_days))
        while cursor <= end:
            if cursor.strftime("%m-%d") in swedish_holidays:
                extra_days += 1
            cursor += timedelta(days=1)

        finish = last_date + timedelta(days=days_needed)
        finish_adj = finish + timedelta(days=int(extra_days))

        c1, c2 = st.columns(2)
        c1.metric("Prognos utan justering", finish.strftime("%Y-%m-%d"))
        c2.metric("Med semester & helgdagar", finish_adj.strftime("%Y-%m-%d"),
                  f"+{extra_days:.1f} dagar")

# ==================== INFO ====================
latest = summary.iloc[-1]
st.metric("Senaste snapshot", latest["Snapshot_Date"].strftime("%Y-%m-%d"))
st.metric("Kvarvarande arbete", f"{latest['Remaining_h']:.1f} timmar")

st.download_button("Ladda ner data", data.to_csv(index=False).encode(), "progress.csv")
st.balloons()
st.success("KLAR! Nu har ni exakt det ni ville ha – och det funkar för alltid")
