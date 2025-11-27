import streamlit as st
import pandas as pd
import plotly.express as px
import pydeck as pdk
import json

# -----------------------
# Load Data
# -----------------------
@st.cache_data
def load_file():
    df = pd.read_csv("data/malaria_indicators_btn.csv")
    return df

df = load_file()

st.title("Malaria Dashboard (Bhutan)")
st.write("This is a simple dashboard made for learning. It shows malaria indicators of Bhutan with basic charts and a map.")

# ------------------------------------------------
# AUTO-DETECT COLUMN NAMES (Prevents KeyError)
# ------------------------------------------------
cols = list(df.columns)

# find indicator column
indicator_col = None
for c in cols:
    if c.lower() in ["indicator", "gho (display)", "indicator_name", "name"]:
        indicator_col = c

# find year column
year_col = None
for c in cols:
    if c.lower() in ["year", "year (display)"]:
        year_col = c

# find numeric/value column
value_col = None
for c in cols:
    if c.lower() in ["value", "numeric", "number", "val"]:
        value_col = c

# rename to standard
df = df.rename(columns={
    indicator_col: "indicator_name",
    year_col: "year",
    value_col: "value_num"
})

# ensure numeric conversion
df["value_num"] = pd.to_numeric(df["value_num"], errors="coerce")

# -----------------------
# Indicator Selection
# -----------------------
ind_list = df["indicator_name"].dropna().unique()

picked = st.sidebar.selectbox("Select Indicator", ind_list)

filt = df[df["indicator_name"] == picked]

st.subheader(picked)

# -----------------------
# Charts
# -----------------------
st.write("### Bar Chart")
fig1 = px.bar(filt, x="year", y="value_num", title=picked)
st.plotly_chart(fig1, use_container_width=True)

st.write("### Line Chart")
fig2 = px.line(filt, x="year", y="value_num", markers=True)
st.plotly_chart(fig2, use_container_width=True)

# -----------------------
# Table
# -----------------------
st.write("### Data Table")
st.dataframe(filt)

# -----------------------
# Bhutan Map
# -----------------------
st.write("---")
st.header("Bhutan Map (Simple)")

with open("data/
