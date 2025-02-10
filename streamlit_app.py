import streamlit as st
import pandas as pd
import numpy as np
import requests
import os
from streamlit_folium import st_folium
import folium
import base64
import math


st.set_page_config(page_title="MENA-VALIDATION-DASH", page_icon="💧", layout="wide")

# ------------------------------------------------------------------------------
#                          GitHub Commit Helper Function
# ------------------------------------------------------------------------------
def commit_file_to_github(content_bytes,
                          repo="Kanishka-Hewageegana-IWMI/Google-MENA-AI",
                          path="mena_validation_results_dataset.csv",
                          branch="main",
                          commit_message="Update CSV from Streamlit"):
    """
    Commits a file to a GitHub repo using the GitHub REST API.
    """
    token = st.secrets["GITHUB_TOKEN"]  # Ensure your token is in Streamlit secrets
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {"Authorization": f"Bearer {token}"}

    # 1) Get the current file's SHA if it exists
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        sha = response.json().get("sha")
    else:
        sha = None

    # 2) Encode CSV content to base64
    content_encoded = base64.b64encode(content_bytes).decode("utf-8")

    # 3) Prepare the JSON payload
    data = {
        "message": commit_message,
        "branch": branch,
        "content": content_encoded,
    }
    if sha:
        data["sha"] = sha

    # 4) Commit (PUT) the file
    put_response = requests.put(url, headers=headers, json=data)
    if put_response.status_code in [200, 201]:
        st.success("File committed to GitHub successfully!")
    else:
        st.error(f"Failed to commit file to GitHub: {put_response.text}")


# ------------------------------------------------------------------------------
#                               Helper Functions
# ------------------------------------------------------------------------------
def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Returns the distance in kilometers between two latitude/longitude points
    using the Haversine formula.
    """
    R = 6371.0  # Earth radius in km
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lat2 - lon1)
    a = (math.sin(d_lat / 2)**2
         + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2))
         * math.sin(d_lon / 2)**2)
    c = 2 * math.asin(math.sqrt(a))
    return R * c

def download_and_load_data():
    """
    Downloads the CSV from Google Drive if it doesn't exist locally,
    then loads it into a DataFrame. Ensures numeric columns are cast properly.
    """
    # csv_url = "https://docs.google.com/spreadsheets/d/1f9fH4NTOaWnff9RIT-CPcwSsVPKkMKgO5cVhznUhKsE/export?format=csv" #Production
    csv_url  = "https://docs.google.com/spreadsheets/d/1Sh4X-rSKoHd4oFqLotyCAhdxN9a3yGOW-cv4Nf6StKk/export?format=csv"  #Validation
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
    numeric_cols = [
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

    # --------------------------------------------------------------------------
    #                        Commit changes to GitHub
    # --------------------------------------------------------------------------
    csv_content = df.to_csv(index=False).encode('utf-8')
    commit_file_to_github(csv_content)

def apply_filters(df, selected_countries, selected_orbis):
    return df[df["country"].isin(selected_countries) & df["is_wwtp"].isin(selected_orbis)]

def display_custom_location_map(custom_lat=30.189538, custom_lon=31.417016):

    st.markdown("<br><hr><br>", unsafe_allow_html=True)
    st.subheader("Custom Location Tracker")

    col1, col2 = st.columns(2)
    with col1:
        custom_lat = st.number_input("Latitude", value=custom_lat, format="%.6f")
    with col2:
        custom_lon = st.number_input("Longitude", value=custom_lon, format="%.6f")

    # map layer
    if -90 <= custom_lat <= 90 and -180 <= custom_lon <= 180:
        m_custom = folium.Map(
            location=[custom_lat, custom_lon],
            zoom_start=15,
            tiles="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
            attr="OpenStreetMap",
        )

        # satellite layer
        folium.TileLayer(
            "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
            attr="Google Satellite",
            name="Google Satellite",
            overlay=False,
        ).add_to(m_custom)

        # Marker for custom location
        folium.Marker(
            [custom_lat, custom_lon],
            tooltip="Custom Location"
        ).add_to(m_custom)
        folium.LayerControl().add_to(m_custom)
        st_folium(m_custom, width="100%", height=500, key="steady_custom_map")
    else:
        st.error("Invalid latitude/longitude range. Please enter valid coordinates.")

# ------------------------------------------------------------------------------
#          Main Row-by-Row Validation (with 5km circle + user click)
# ------------------------------------------------------------------------------
def display_row_validation(filtered_data_val):
    """
    For each row in the filtered data slice:
      - Show a map centered on that row's lat/lon
      - Draw a dynamic km range circle
      - Mark the row itself differently
      - Show neighbors within the dynamic circle
      - ALLOW THE USER TO CLICK on the map to pick a new lat/lng
      - Provide an editable form
      - Provide Accept/Reject buttons
    """
    for idx, row in filtered_data_val.iterrows():
        st.markdown("---")
        st.write(f"**Row Index** - {idx}")
        st.write(f"**Source Name** - {row['source_name']}")

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

        if lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180:
            m = folium.Map(
                location=[lat, lon],
                zoom_start=80,
                tiles="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
                attr="OpenStreetMap",
            )

            # satellite layer
            folium.TileLayer(
                "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
                attr="Google Satellite",
                name="Google Satellite",
                overlay=False,
            ).add_to(m)

            # dynamic km circle
            folium.Circle(
                radius=5000,  # 5 km
                location=[lat, lon],
                color="blue",
                fill=True,
                fill_opacity=0.10
            ).add_to(m)

            # Main red marker
            main_tooltip = f"Index: {idx}, Source: {row['source_name']} (Main)"
            folium.Marker(
                location=[lat, lon],
                tooltip=main_tooltip,
                icon=folium.Icon(color="red", icon="")
            ).add_to(m)
            folium.LatLngPopup().add_to(m)  # Add LatLngPopup ----> Let user click to see lat & lng

            # Marking neighbors within 5km
            df_all = st.session_state.df.dropna(subset=["latitude","longitude"])
            for i2, row2 in df_all.iterrows():
                lat2 = row2["latitude"]
                lon2 = row2["longitude"]
                if pd.notnull(lat2) and pd.notnull(lon2):
                    dist = haversine_distance(lat, lon, lat2, lon2)
                    if dist <= 5.0 and i2 != idx:
                        tooltip_text = f"Index: {i2}, Source: {row2['source_name']}"
                        folium.Marker(
                            location=[lat2, lon2],
                            tooltip=tooltip_text,
                            icon=folium.Icon(color="blue" , icon=""),
                        ).add_to(m)

            # Layer control
            folium.LayerControl().add_to(m)
            map_data = st_folium(m, width="100%", height=600, key=f"map_{idx}")
        else:
            st.write("Invalid or missing lat/lon for mapping.")

        # ------------------------------------------------------------------------------
        #                         Expandable editor for each row
        # ------------------------------------------------------------------------------
        with st.expander("Editable Row Details"):
            with st.form(f"edit_form_{idx}"):
                updated_values = {}
                for col_name in row.index:
                    current_val = str(row[col_name])
                    updated_values[col_name] = st.text_input(col_name, current_val)

                if st.form_submit_button("Save Row Changes"):
                    for col_name, val in updated_values.items():
                        st.session_state.df.loc[idx, col_name] = val

                    numeric_cols = [
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
                    st.success(f"Source {row['source_name']} updated successfully!")

        # ------------------------------------------------------------------------------
        #                           Acceptance / Rejection Buttons
        # ------------------------------------------------------------------------------
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Rejected", key=f"reject_{idx}"):
                st.session_state.df.loc[idx, "Validation_Status"] = "Rejected"
                save_dataframe(st.session_state.df)
                st.success(f"Source {row['source_name']} Rejected")

        with col2:
            if st.button("Accepted", key=f"accept_{idx}"):
                st.session_state.df.loc[idx, "Validation_Status"] = "Accepted"
                save_dataframe(st.session_state.df)
                st.success(f"Source {row['source_name']} Accepted")

# ------------------------------------------------------------------------------
#                                General Insights
# ------------------------------------------------------------------------------
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
    Displays the locations of the current validation rows on a simple map using st.map().
    (Note: st.map() doesn't provide color-coding or advanced styling like Folium)
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
    display_custom_location_map()

    st.sidebar.header("Filters")

    # Country filter
    all_countries = sorted(df["country"].dropna().unique().tolist())
    selected_countries = st.sidebar.multiselect("Select Country",
                                                options=all_countries,
                                                default=all_countries)

    # Filter by classification
    all_orbis = sorted(df["is_wwtp"].dropna().unique().tolist())
    selected_orbis = st.sidebar.multiselect("Filter WWTP",
                                            options=all_orbis,
                                            default=all_orbis)

    filtered_data = apply_filters(df, selected_countries, selected_orbis)

    max_index = len(filtered_data)
    st.sidebar.write(f"Data has {max_index} rows after filtering.")
    start_idx = st.sidebar.number_input("Start Row Index", min_value=0,
                                        max_value=max_index, value=0, step=1)
    end_idx = st.sidebar.number_input("End Row Index", min_value=0,
                                      max_value=max_index, value=min(10, max_index), step=1)

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
