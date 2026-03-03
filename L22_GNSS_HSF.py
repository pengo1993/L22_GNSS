import streamlit as st
import pandas as pd
import re
from pyproj import Transformer
from streamlit_folium import st_folium
import folium

# Configurazione Pagina
st.set_page_config(page_title="L22 Height Scale Factor Tool", layout="wide")

# --- DATABASE HSF ITALIA AGGIORNATO ---
HSF_DATABASE = {
    "UTM zone 32N": {"epsg": "7791", "hsf": 1.0004, "vrs": "ITG2009"},
    "UTM zone 33N": {"epsg": "7792", "hsf": 1.0004, "vrs": "ITG2009"},
    "Italy zone 12": {"epsg": "7795", "hsf": 1.0004, "vrs": "ITG2009"},
    "Italy zone 13": {"epsg": "7800", "hsf": 1.0004, "vrs": "ITG2009"},
}

def parse_filename(filename):
    # Estrae Job Number (prime 4 cifre) e nome progetto
    match = re.match(r"(\d{4})_(.*)\.", filename)
    if match:
        return match.group(1), match.group(2)
    return "0000", "Project"

# --- INTERFACCIA ---
st.title("🚀 L22 Height Scale Factor Tool")
st.markdown("""
*Apply a Coordinate Reference System-dependent Height Scale Factor to X and Y (Z remains unchanged) 
for surveying, photogrammetry, and laser scanning applications.*
""")

uploaded_file = st.file_uploader("Carica il file CSV di Emlid", type=["csv"])

if uploaded_file:
    df_raw = pd.read_csv(uploaded_file)
    
    # 1. ESTRAZIONE INFO
    job_n, proj_name = parse_filename(uploaded_file.name)
    cs_full_name = str(df_raw['CS name'].iloc[0]) if 'CS name' in df_raw.columns else "Unknown"
    
    # Matching del sistema di riferimento nel database
    matched = None
    for key, val in HSF_DATABASE.items():
        if key.lower() in cs_full_name.lower():
            matched = val
            break
            
    def_epsg = matched['epsg'] if matched else "7791"
    def_hsf = matched['hsf'] if matched else 1.0004
    def_vrs = matched['vrs'] if matched else "ITG2009"

    # --- SIDEBAR OPZIONI ---
    st.sidebar.header("⚙️ Settings")
    digits = st.sidebar.number_input("Cifre decimali (X,Y,Z)", min_value=0, max_value=6, value=2)
    show_desc = st.sidebar.checkbox("Esporta colonna 'Description'", value=True)

    # --- SEZIONE CONFIGURAZIONE ---
    st.divider()
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📍 Riferimento e Scala")
        c1, c2 = st.columns([3, 1])
        horz_ref = c1.text_input("Horizontal Reference System", value=cs_full_name)
        hsf_val = c2.number_input("HSF", value=def_hsf, format="%.4f", step=0.0001)
        
        vert_ref = st.text_input("Vertical Reference System", value=def_vrs)
        base_pt = st.selectbox("Seleziona Punto Base (Local Origin)", df_raw['Name'].unique())

    with col2:
        st.subheader("📂 Naming per Export")
        job_id = st.text_input("Job Number", value=job_n)
        project_id = st.text_input("Project Name", value=proj_name.replace(" ", "_"))
        epsg_id = st.text_input("EPSG Code", value=def_epsg)
        
        # Nome file dinamico
        final_filename = f"{job_id}_{project_id}_GNSS_EPSG{epsg_id}_{vert_ref}_LOCAL{base_pt}.txt"
        st.code(f"Output: {final_filename}")

    # --- CALCOLO ---
    base_row = df_raw[df_raw['Name'] == base_pt].iloc[0]
    E0, N0 = base_row['Easting'], base_row['Northing']
    
    df_final = df_raw.copy()
    df_final['Easting'] = (E0 + (df_raw['Easting'] - E0) * hsf_val).round(digits)
    df_final['Northing'] = (N0 + (df_raw['Northing'] - N0) * hsf_val).round(digits)
    df_final['Elevation'] = df_raw['Elevation'].round(digits)

    # --- ANTEPRIMA MAPPA (FOLIUM) ---
    st.subheader("🗺️ Anteprima Satellitare")
    
    # Determina zona per mappa (33 se "33" o "13" è nel nome, altrimenti 32)
    map_zone = 33 if ("33" in cs_full_name or "13" in cs_full_name) else 32
    transformer = Transformer.from_crs(f"EPSG:{32600 + map_zone}", "EPSG:4326")
    
    df_raw['lat'], df_raw['lon'] = transformer.transform(df_raw['Easting'].values, df_raw['Northing'].values)
    
    # Creazione mappa
    m = folium.Map(location=[df_raw['lat'].mean(), df_raw['lon'].mean()], zoom_start=18)
    
    # Layer Satellite
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri', name='Satellite (Esri)', overlay=False
    ).add_to(m)
    folium.TileLayer('OpenStreetMap', name='OpenStreetMap').add_to(m)
    folium.LayerControl().add_to(m)

    # Marker
    for _, row in df_raw.iterrows():
        is_base = row['Name'] == base_pt
        folium.CircleMarker(
            location=[row['lat'], row['lon']],
            radius=6 if is_base else 4,
            popup=f"ID: {row['Name']}",
            color="red" if is_base else "blue",
            fill=True,
            fill_opacity=0.7
        ).add_to(m)

    st_folium(m, width="100%", height=500, returned_objects=[])

    # --- EXPORT ---
    st.divider()
    cols_to_export = ['Name', 'Easting', 'Northing', 'Elevation']
    if show_desc:
        cols_to_export.append('Description')
    
    output_csv = df_final[cols_to_export].to_csv(index=False, header=False).encode('utf-8')
    
    st.download_button(
        label=f"📥 Scarica {final_filename}",
        data=output_csv,
        file_name=final_filename,
        mime="text/plain",
    )
    
    st.subheader("📄 Anteprima dati scalati")
    st.dataframe(df_final[cols_to_export], use_container_width=True)
