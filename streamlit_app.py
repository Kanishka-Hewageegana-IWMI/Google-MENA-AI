import streamlit as st
import pandas as pd
import numpy as np
import rasterio
import requests
from io import BytesIO
from PIL import Image
import gdown
import os

# -----------------------------------------------------------
# 1) Download CSV if not present, then load into a DataFrame
# -----------------------------------------------------------
def download_and_load_data():
    csv_url = "https://drive.google.com/uc?id=1oFOR1yQWQz0xiQiGhmWLydaHpVU7ZZmS"
    csv_file = "validation_dataset.csv"

    # Download CSV once if it doesn't exist
    if not os.path.exists(csv_file):
        gdown.download(csv_url, csv_file, quiet=False)

    # Read the CSV
    df_temp = pd.read_csv(csv_file, encoding="latin1")

    # Convert to numeric where appropriate
    numeric_cols = [
        "Circular_Tank_Count",
        "Rectangular_Tank_Count",
        "Desgin_Capacity",
        "Latitude",
        "Longitude",
    ]
    for col in numeric_cols:
        if col in df_temp.columns:
            df_temp[col] = pd.to_numeric(df_temp[col], errors="coerce")

    # Ensure a "Validation_Status" column exists
    if "Validation_Status" not in df_temp.columns:
        df_temp["Validation_Status"] = ""
    return df_temp


# -----------------------------------------------------------
# 2) Helper to save the DataFrame to CSV
# -----------------------------------------------------------
def save_dataframe(df: pd.DataFrame):
    df.to_csv("validation_dataset.csv", index=False)
    st.success("CSV updated successfully!")


# -----------------------------------------------------------
# 3) Load TIFF images from URLs
# -----------------------------------------------------------
def load_tiff_image(url_link: str) -> Image.Image:
    resp = requests.get(url_link, timeout=15)
    resp.raise_for_status()
    with rasterio.open(BytesIO(resp.content)) as src:
        arr = src.read()
        # Switch from (channels, height, width) => (height, width, channels)
        arr = np.transpose(arr, (1, 2, 0))
    return Image.fromarray(arr)


# -----------------------------------------------------------
# 4) Initialize or Retrieve DataFrame from session_state
# -----------------------------------------------------------
if "df" not in st.session_state:
    st.session_state.df = download_and_load_data()

df = st.session_state.df  # Work with an alias for convenience

st.title("WWTP Validation Dashboard")

# -----------------------------------------------------------
# 5) Sidebar Filters
# -----------------------------------------------------------
st.sidebar.header("Filters")

# Country filter
all_countries = sorted(df["Country"].dropna().unique().tolist())
selected_countries = st.sidebar.multiselect(
    "Select Country",
    options=all_countries,
    default=all_countries
)

# Filter the DataFrame by selected countries
filtered_data = df[df["Country"].isin(selected_countries)]

max_index = len(filtered_data)
st.sidebar.write(f"Data has {max_index} rows after filtering.")

# Let the user pick a start and end index
start_idx = st.sidebar.number_input(
    "Start Row Index (inclusive)",
    min_value=0,
    max_value=max_index,
    value=0,
    step=1
)
end_idx = st.sidebar.number_input(
    "End Row Index (exclusive)",
    min_value=0,
    max_value=max_index,
    value=min(10, max_index),
    step=1
)

# Ensure start < end
if start_idx >= end_idx:
    st.sidebar.error("Please set Start Row < End Row.")
    filtered_data_for_validation = pd.DataFrame()  # empty
else:
    # Slice the filtered data
    filtered_data_for_validation = filtered_data.iloc[start_idx:end_idx]

# -----------------------------------------------------------
# 6) Row-by-Row Validation & Editing
# -----------------------------------------------------------
st.subheader("Row-by-Row Validation")

for idx, row in filtered_data_for_validation.iterrows():
    st.markdown("---")
    st.write(f"**Row Index (Original DF):** {idx}")

    # --------------------------
    # A) IMAGE PREVIEW
    # --------------------------
    url_link = row.get("Url_Image", None)
    if url_link and isinstance(url_link, str) and url_link.startswith("http"):
        st.markdown(f"[Open Image in Browser]({url_link})")

        if url_link.lower().endswith((".tif", ".tiff")):
            try:
                img = load_tiff_image(url_link)
                st.image(img, caption="TIFF Image", use_container_width=True)
            except:
                pass
        else:
            st.image(url_link, caption="WWTP Image", use_container_width=True)
    else:
        st.write("No valid image URL found.")

    # --------------------------
    # B) MAP VIEW (Latitude/Longitude)
    # --------------------------
    lat, lon = row.get("Latitude"), row.get("Longitude")
    if pd.notnull(lat) and pd.notnull(lon):
        # Optionally check range
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            map_df = pd.DataFrame({"lat": [lat], "lon": [lon]})
            st.map(map_df, zoom=8)
        else:
            st.write("Invalid lat/lon range for mapping.")

    # --------------------------
    # C) EDITABLE ROW DETAILS
    # --------------------------
    with st.expander("Editable Row Details"):
        with st.form(f"edit_form_{idx}"):
            updated_values = {}
            for col_name in row.index:
                current_val = str(row[col_name])
                # Use text_input for all columns.
                # If you want numeric columns to remain numeric, you can
                # do st.number_input for those specific columns instead.
                new_val = st.text_input(f"{col_name}", current_val)
                updated_values[col_name] = new_val

            # When user clicks "Save Row Changes", write back to st.session_state.df
            if st.form_submit_button("Save Row Changes"):
                for col_name, val in updated_values.items():
                    st.session_state.df.loc[idx, col_name] = val
                # Save to disk
                save_dataframe(st.session_state.df)
                st.success(f"Row {idx} updated successfully!")

    # --------------------------
    # D) ACCEPT / REJECT BUTTONS
    # --------------------------
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Rejected", key=f"reject_{idx}"):
            st.session_state.df.loc[idx, "Validation_Status"] = "Rejected"
            save_dataframe(st.session_state.df)
            st.success(f"Row {idx} => Rejected")

    with col2:
        if st.button("Accepted", key=f"accept_{idx}"):
            st.session_state.df.loc[idx, "Validation_Status"] = "Accepted"
            save_dataframe(st.session_state.df)
            st.success(f"Row {idx} => Accepted")


# -----------------------------------------------------------
# 7) General Insights
# -----------------------------------------------------------
st.subheader("General Insights")

# Display data after filtering
st.dataframe(filtered_data)

# Basic numeric summary
st.write(filtered_data.describe(include=[np.number]))

if "Circular_Tank_Count" in filtered_data.columns:
    st.bar_chart(filtered_data["Circular_Tank_Count"].value_counts())
