import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import re

st.set_page_config(page_title="Progress Tracker", layout="wide")
st.title("Progress Tracker – funkar alltid")

snapshot_files = st.file_uploader("Ladda upp snapshot-filer", type=["csv"], accept_multiple_files=True)
if not snapshot_files:
    st.info("Ladda upp minst en fil")
    st.stop()

# Läs in alla filer
dfs = []
for file in snapshot_files:
    df = None
    for sep in [",", ";"]:
        try:
            df = pd.read_csv(file, sep=sep, on_bad_lines="skip", engine="python")
            if len(df.columns) > 3:
                break
        except:
            pass
    if df is None:
        st.error(f"Kunde inte läsa {file.name}")
        continue
    try:
        date_str = file.name.split("snapshot_")[-1].split(".")[0].replace("_", "-")[:10]
        snap_date = datetime.strptime(date_str, "%Y-%m-%d")
    except:
        snap_date = datetime.now()
    df["Snapshot_Date"] = snap_date
    dfs.append(df)

data = pd.concat(dfs, ignore_index=True)

st.write("Välj kolumner själv:")
cols = list(data.columns)
col1, col2, col3 = st.columns(3)
with col1:
    iteration_col = st.selectbox("Iteration", cols)
with col2:
    original_col = st.selectbox("Original Estimate", cols)
with col3:
    remaining_col = st.selectbox("Remaining Estimate", cols)

# Filtrera
filter_text = st.text_input("Filtrera iteration (valfritt)")
if filter_text:
    data = data[data[iteration_col].astype(str).str.contains(filter_text, case=False, na=False)]

# Konvertera till minuter
def to_min(x):
    if pd.isna(x): return 0
    s = str(x).lower()
    h = re.search(r"(\d+(?:\.\d+)?)h", s)
    m = re.search(r"(\d+)m", s)
    total = 0
    if h: total += float(h.group(1))*60
    if m: total += float(m.group(1))
    if total == 0:
        nums = re.findall(r"\d+", s)
        total = float(nums[0]) if nums else 0
    return int(total)

data["orig_min"] = data[original_col].apply(to_min)
data["rem_min"] = data[remaining_col].apply(to_min)

# Semester
extra_days = st.slider("Extra semesterdagar", 0.0, 50.0, 0.0, 0.5)

# Summera
summary = data.groupby("Snapshot_Date").agg({"orig_min":"sum", "rem_min":"sum"}).reset_index()
summary["Total_h"] = summary["orig_min"]/60
summary["Rem_h"] = summary["rem_min"]/60
summary = summary.sort_values("Snapshot_Date")

# Graf
fig = go.Figure()
fig.add_trace(go.Scatter(x=summary["Snapshot_Date"], y=summary["Total_h"], mode="lines+markers", name="Totalt"))
fig.add_trace(go.Scatter(x=summary["Snapshot_Date"], y=summary["Rem_h"], mode="lines+markers", name="Kvar", line=dict(color="red")))
st.plotly_chart(fig, use_container_width=True)

# Prognos
if len(summary) >= 2:
    days_needed = int(summary["Rem_h"].iloc[-1] / ((summary["Rem_h"].iloc[0] - summary["Rem_h"].iloc[-1]) / (len(summary)-1))) + 1
    finish = summary["Snapshot_Date"].iloc[-1] + timedelta(days=days_needed)
    finish_sem = finish + timedelta(days=int(extra_days))
    st.success(f"Utan semester: {finish.date()}")
    st.success(f"Med semester: {finish_sem.date()} (+{extra_days} dagar)")

st.balloons()
