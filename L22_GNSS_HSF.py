import streamlit as st
import pandas as pd
import re
from pyproj import Transformer
from streamlit_folium import st_folium
import folium

# Configurazione Pagina
st.set_page_config(page_title="L22 Height Scale Factor Tool", layout="wide")

# --- DATABASE HSF ITALIA ---
HSF_DATABASE = {
    "RDN2008 / UTM zone 32N": {"epsg": "7791", "hsf": 1.0004, "vrs": "ITG2009"},
    "RDN2008 / UTM zone 33N": {"epsg": "7792", "hsf": 1.0004, "vrs": "ITG2009"},
    # Aggiungere qui altri sistemi se necessario
}

# --- FUNZIONI DI SUPPORTO ---
def parse_filename(filename):
    # Cerca il pattern 0000_NomeFile
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
    
    # 1. ESTRAZIONE INFO DA CSV E FILENAME
    job_n, proj_name = parse_filename(uploaded_file.name)
    cs_full_name = df_raw['CS name'].iloc[0] if 'CS name' in df_raw.columns else "Non rilevato"
    
    # Matching del sistema di riferimento
    matched_system = next((v for k, v in HSF_DATABASE.items() if k in cs_full_name), None)
    default_epsg = matched_system['epsg'] if matched_system else "7791"
    default_hsf = matched_system['hsf'] if matched_system else 1.0004
    default_vrs = matched_system['vrs'] if matched_system else "ITG2009"

    # --- SIDEBAR OPZIONI (Tab Digits e Description) ---
    st.sidebar.header("Impostazioni Avanzate")
    digits = st.sidebar.number_input("Cifre decimali (X,Y,Z)", min_value=0, max_value=6, value=2)
    show_desc = st.sidebar.checkbox("Includi colonna 'Description'", value=True)

    # --- SEZIONE CONFIGURAZIONE ---
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("⚙️ Configurazione Sistema")
        job_id = st.text_input("Job Number", value=job_n)
        project_id = st.text_input("Project Name", value=proj_name)
        epsg_id = st.text_input("EPSG Code", value=default_epsg)
        vrs_id = st.text_input("Vertical Ref (VRS)", value=default_vrs)
        
    with col2:
        st.subheader("📏 Scale Parameter")
        st.info(f"**CS Rilevato:** {cs_full_name}")
        hsf_val = st.number_input("Fattore di Scala (HSF)", value=default_hsf, format="%.4f")
        base_pt = st.selectbox("Seleziona Punto Base (Local Origin)", df_raw['Name'].unique())

    # --- CALCOLO ---
    base_coords = df_raw[df_raw['Name'] == base_pt].iloc[0]
    E0, N0 = base_coords['Easting'], base_coords['Northing']
    
    df_final = df_raw.copy()
    df_final['Easting'] = (E0 + (df_raw['Easting'] - E0) * hsf_val).round(digits)
    df_final['Northing'] = (N0 + (df_raw['Northing'] - N0) * hsf_val).round(digits)
    df_final['Elevation'] = df_raw['Elevation'].round(digits)

# --- ANTEPRIMA MAPPA (OPENSTREETMAP) ---
    st.subheader("🗺️ Mappa di Anteprima (OSM)")
    
    # Trasformazione per la mappa (WGS84)
    # Rileviamo se usare fuso 32 o 33 per la trasformazione
    zone = 32 if "zone 32N" in cs_name_raw else 33
    transformer = Transformer.from_crs(f"EPSG:{32600+zone}", "EPSG:4326")
    
    df_raw['lat'], df_raw['lon'] = transformer.transform(df_raw['Easting'].values, df_raw['Northing'].values)
    
    # Creazione mappa Folium
    m = folium.Map(location=[df_raw['lat'].mean(), df_raw['lon'].mean()], zoom_start=17, control_scale=True)
    folium.TileLayer('OpenStreetMap').add_to(m)
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Satellite (Esri)',
        overlay=False,
        control=True
    ).add_to(m)
    folium.LayerControl().add_to(m)

    for _, row in df_raw.iterrows():
        folium.CircleMarker(
            location=[row['lat'], row['lon']],
            radius=5,
            popup=f"{row['Name']} ({row['Description']})",
            color="red",
            fill=True,
        ).add_to(m)

    st_folium(m, width=1200, height=500)

    # --- EXPORT ---
    st.subheader("💾 Export Data")
    
    # Costruzione Nome File
    export_filename = f"{job_id}_{project_id.replace(' ', '_')}_GNSS_EPSG{epsg_id}_{vrs_id}_LOCAL{base_pt}.txt"
    
    # Selezione colonne finali
    cols = ['Name', 'Easting', 'Northing', 'Elevation']
    if show_desc: cols.append('Description')
    
    output_csv = df_final[cols].to_csv(index=False, header=False).encode('utf-8')
    
    st.download_button(
        label=f"📥 Scarica {export_filename}",
        data=output_csv,
        file_name=export_filename,
        mime="text/plain",
    )
    
    st.dataframe(df_final[cols].head())

