import streamlit as st
import pandas as pd
import plotly.express as px
import json
import pydeck as pdk

# load data
@st.cache_data
def load_file():
    df = pd.read_csv("data/malaria_indicators_btn.csv")
    return df

df = load_file()

st.title("Malaria Dashboard (Bhutan)")
st.write("This is a simple dashboard I made for learning purpose.")

# ---- FIX COLUMN NAMES HERE ----
# rename columns based on your actual CSV
df = df.rename(columns={
    "Indicator": "indicator_name",
    "Year": "year",
    "Value": "value_num"
})

# convert numeric column
df["value_num"] = pd.to_numeric(df["value_num"], errors="coerce")

# sidebar – pick indicator only
ind_list = df["indicator_name"].dropna().unique()

picked = st.sidebar.selectbox("Select Indicator", ind_list)

# filter
filt = df[df["indicator_name"] == picked]

st.subheader(picked)

# bar chart
st.write("### Bar Chart")
fig1 = px.bar(filt, x="year", y="value_num", title=picked)
st.plotly_chart(fig1, use_container_width=True)

# line chart
st.write("### Line Chart")
fig2 = px.line(filt, x="year", y="value_num", markers=True)
st.plotly_chart(fig2, use_container_width=True)

# table
st.write("### Data Table")
st.dataframe(filt)

# map
st.write("---")
st.header("Bhutan Map (Simple Version)")

with open("data/bhutan_districts.json", "r") as f:
    geo = json.load(f)

layer = pdk.Layer(
    "GeoJsonLayer",
    geo,
    stroked=True,
    filled=True,
    get_fill_color="[255, 0, 0, 100]"
)

view = pdk.ViewState(latitude=27.5, longitude=90.4, zoom=7)

st.pydeck_chart(
    pdk.Deck(
        layers=[layer],
        initial_view_state=view
    )
)
