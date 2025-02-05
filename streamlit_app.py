import streamlit as st
import pandas as pd
import numpy as np
import requests
import os
from streamlit_folium import st_folium
import folium

# Page configs..
st.set_page_config(page_title="MENA-VALIDATION-DASH", page_icon="💧", layout="wide")

def download_and_load_data():
    """
    Downloads the CSV from Google Drive if it doesn't exist locally,
    then loads it into a DataFrame. Ensures numeric columns are cast properly.
    """
    # csv_url = "https://docs.google.com/spreadsheets/d/1bi56lUGNNtF5X9n3rWCkhxoNKI84X_IB7ra7CTv2rjc/export?format=csv"     #Duplicates CSV
    csv_url = "https://docs.google.com/spreadsheets/d/126prGZYRsF3V7ruKPAcoV1I4hEK-jhOM8RGWGaC9wjY/export?format=csv"       #Final CSV file
    csv_file = "mena_validation_results_dataset.csv"

    if not os.path.exists(csv_file):
        response = requests.get(csv_url)
        if response.status_code == 200:
            with open(csv_file, 'wb') as f:
                f.write(response.content)
        else:
            st.error("Failed to download the CSV file")
            return pd.DataFrame()

    df_temp = pd.read_csv(csv_file, encoding="latin1")
    numeric_cols = [  # Pre-processing
        "circular_tank_count",
        "rectangular_tank_count",
        "desgin_capacity_m3_yr",
        "latitude",
        "longitude"
    ]
    for col in numeric_cols:
        if col in df_temp.columns:
            df_temp[col] = pd.to_numeric(df_temp[col], errors="coerce")

    if "Validation_Status" not in df_temp.columns:
        df_temp["Validation_Status"] = ""

    return df_temp

def save_dataframe(df):
    """
    Saves the given DataFrame to a local CSV file.
    Then the user can safely get the edited csv without damaging the original
    """
    df.to_csv("mena_validation_results_dataset.csv", index=False)
    st.success("CSV updated successfully!")

def apply_filters(df, selected_countries, selected_orbis):
    """
    Applies filters to the DataFrame based on selected countries and WWTP classification.
    """
    return df[df["country"].isin(selected_countries) & df["is_wwtp"].isin(selected_orbis)]

def display_row_validation(filtered_data_val):
    """
    Displays row-by-row validation with editable fields and accept/reject buttons.
    """
    for idx, row in filtered_data_val.iterrows():
        st.markdown("---")
        st.write(f"**Row Index** - {idx}")
        st.write(f"**Source Name** - {row['new_name']}")

        url_link = row.get("url_image", None)
        if url_link and isinstance(url_link, str) and url_link.startswith("http"):
            st.link_button("Open Image in Browser", url_link, type="primary")
        else:
            st.write("No valid image URL found.")

        lat_raw, lon_raw = row.get("latitude"), row.get("longitude")
        try:
            lat = float(lat_raw)
            lon = float(lon_raw)
        except (ValueError, TypeError):
            lat, lon = None, None

        if lat is not None and lon is not None:
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                m = folium.Map(
                    location=[lat, lon],
                    zoom_start=100,
                    tiles="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
                    attr="OpenStreetMap",
                )

                folium.TileLayer(
                    "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
                    attr="Google",
                    name="Google Satellite",
                    overlay=False,
                ).add_to(m)

                folium.Marker(
                    [lat, lon],
                    tooltip=f"{row['new_name']}"
                ).add_to(m)

                st_folium(m, width="100%", height=800, key=f"map_{idx}")
            else:
                st.write("Invalid lat/lon range for mapping.")
        else:
            st.write("Invalid or missing lat/lon for mapping.")

        with st.expander("Editable Row Details"):
            with st.form(f"edit_form_{idx}"):
                updated_values = {}
                for col_name in row.index:
                    current_val = str(row[col_name])
                    updated_values[col_name] = st.text_input(col_name, current_val)

                if st.form_submit_button("Save Row Changes"):
                    for col_name, val in updated_values.items():
                        st.session_state.df.loc[idx, col_name] = val

                    numeric_cols = [  # Double check
                        "circular_tank_count",
                        "rectangular_tank_count",
                        "desgin_capacity_m3_yr",
                        "latitude",
                        "longitude",
                    ]
                    for col in numeric_cols:
                        st.session_state.df[col] = pd.to_numeric(
                            st.session_state.df[col], errors="coerce"
                        )

                    save_dataframe(st.session_state.df)
                    st.success(f"Source {row['new_name']} updated successfully!")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Rejected", key=f"reject_{idx}"):
                st.session_state.df.loc[idx, "Validation_Status"] = "Rejected"
                save_dataframe(st.session_state.df)
                st.success(f"Source {row['new_name']} Rejected")

        with col2:
            if st.button("Accepted", key=f"accept_{idx}"):
                st.session_state.df.loc[idx, "Validation_Status"] = "Accepted"
                save_dataframe(st.session_state.df)
                st.success(f"Source {row['new_name']} Accepted")

def display_general_insights(filtered_data):
    """
    Displays general insights and statistics about the filtered data.
    """
    st.subheader("General Insights")
    st.dataframe(filtered_data)

    st.write("WWTP Statistics")
    st.write(filtered_data.describe(include=[np.number]))

    try:
        if "circular_tank_count" in filtered_data.columns and filtered_data["circular_tank_count"].notna().any():
            st.write("Circular Tank Count Distribution")
            st.bar_chart(filtered_data["circular_tank_count"].value_counts())

        if "rectangular_tank_count" in filtered_data.columns and filtered_data["rectangular_tank_count"].notna().any():
            st.write("Rectangular Tank Count Distribution")
            st.bar_chart(filtered_data["rectangular_tank_count"].value_counts())

    except Exception as e:
        st.error(f"Error creating plots: {e}")

def display_locations(filtered_data_val):
    """
    Displays the locations of the current validation on a map.
    """
    st.subheader("Locations of Current Validation")
    valid_coords_map = filtered_data_val.dropna(subset=["latitude", "longitude"])

    if not valid_coords_map.empty:
        map_data = valid_coords_map[['latitude', 'longitude']]
        st.map(map_data)
    else:
        st.write("No valid latitude/longitude found for the current validation.")

def main():
    if "df" not in st.session_state:
        st.session_state.df = download_and_load_data()

    df = st.session_state.df
    st.title("WWTP Validation Dashboard")
    st.sidebar.header("Filters")

    # Country filter
    all_countries = sorted(df["country"].dropna().unique().tolist())
    selected_countries = st.sidebar.multiselect("Select Country", options=all_countries, default=all_countries)

    # Filter by classification
    all_orbis = sorted(df["is_wwtp"].dropna().unique().tolist())
    selected_orbis = st.sidebar.multiselect("Filter WWTP", options=all_orbis, default=all_orbis)

    # Apply filters
    filtered_data = apply_filters(df, selected_countries, selected_orbis)

    max_index = len(filtered_data)
    st.sidebar.write(f"Data has {max_index} rows after filtering.")
    start_idx = st.sidebar.number_input("Start Row Index", min_value=0, max_value=max_index, value=0, step=1)
    end_idx = st.sidebar.number_input("End Row Index", min_value=0, max_value=max_index, value=min(10, max_index), step=1)

    if start_idx >= end_idx:
        st.sidebar.error("Please set Start Row Value < End Row Value.")
        filtered_data_val = pd.DataFrame()
    else:
        filtered_data_val = filtered_data.iloc[start_idx:end_idx]

    display_row_validation(filtered_data_val)
    display_general_insights(filtered_data)
    display_locations(filtered_data_val)

if __name__ == "__main__":
    main()