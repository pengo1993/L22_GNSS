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
}

def parse_filename(filename):
    # Estrae Job Number (prime 4 cifre) e resto del nome
    match = re.match(r"(\d{4})_(.*)\.", filename)
    if match:
        return match.group(1), match.group(2)
    return "0000", "Project"

# --- LOGO E TITOLO ---
# Assicurati di avere un file 'logo_l22.png' nella stessa cartella
try:
    st.image("logo_l22.png", width=150)
except:
    st.info("Logo L22 non trovato. Carica 'logo_l22.png' nella repository.")

st.title("L22 Height Scale Factor Tool")
st.markdown("*Apply a Coordinate Reference System-dependent Height Scale Factor to X and Y (Z remains unchanged) for surveying, photogrammetry, and laser scanning applications.*")

uploaded_file = st.file_uploader("Carica il file CSV di Emlid", type=["csv"])

if uploaded_file:
    df_raw = pd.read_csv(uploaded_file)
    
    # 1. ANALISI DEI DATI E DEL NOME FILE
    job_n, proj_name = parse_filename(uploaded_file.name)
    cs_name_raw = df_raw['CS name'].iloc[0] if 'CS name' in df_raw.columns else "Unknown"
    
    # Matching automatico HSF e EPSG
    matched = next((v for k, v in HSF_DATABASE.items() if k in cs_name_raw), None)
    def_epsg = matched['epsg'] if matched else "7791"
    def_hsf = matched['hsf'] if matched else 1.0004
    def_vrs = matched['vrs'] if matched else "ITG2009"

    # --- SIDEBAR OPZIONI ---
    st.sidebar.header("⚙️ Settings")
    digits = st.sidebar.number_input("Cifre decimali (X,Y,Z)", 0, 6, 2)
    show_desc = st.sidebar.checkbox("Esporta colonna 'Description'", value=True)

    # --- SCHERMATA CONFIGURAZIONE ---
    st.divider()
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.subheader("📍 Riferimento e Scala")
        # Layout richiesto: Horizontal Reference | HSF
        c1, c2 = st.columns([3, 1])
        horz_ref = c1.text_input("Horizontal Reference System", value=cs_name_raw)
        hsf_val = c2.number_input("HSF", value=def_hsf, format="%.4f")
        
        vert_ref = st.text_input("Vertical Reference System", value=def_vrs)
        base_pt = st.selectbox("Seleziona Punto Base (Local Origin)", df_raw['Name'].unique())

    with col_b:
        st.subheader("📂 Naming per Export")
        job_id = st.text_input("Job Number", value=job_n)
        project_id = st.text_input("Project Name", value=proj_name.replace(" ", "_"))
        epsg_id = st.text_input("EPSG Code", value=def_epsg)
        # Il nome file si aggiorna in tempo reale
        final_filename = f"{job_id}_{project_id}_GNSS_EPSG{epsg_id}_{vert_ref}_LOCAL{base_pt}.txt"
        st.code(f"Output: {final_filename}")

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
    st.divider()
    cols_to_export = ['Name', 'Easting', 'Northing', 'Elevation']
    if show_desc:
        cols_to_export.append('Description')
    
    txt_data = df_final[cols_to_export].to_csv(index=False, header=False, sep=',').encode('utf-8')
    
    st.download_button(
        label=f"📥 Scarica {final_filename}",
        data=txt_data,
        file_name=final_filename,
        mime="text/plain",
    )
    st.dataframe(df_final[cols_to_export], use_container_width=True)
