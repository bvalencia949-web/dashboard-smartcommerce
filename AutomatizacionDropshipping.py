import numpy as np
import time
import os
import glob
import pandas as pd
import streamlit as st
import plotly.express as px
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# --- PARCHE DE COMPATIBILIDAD ---
try:
    if not hasattr(np, "float"): np.float = float
    if not hasattr(np, "int"): np.int = int
except Exception: pass

# --- CONFIGURACIÓN DE RUTAS ---
DOWNLOAD_PATH = "/tmp" if not os.name == 'nt' else os.path.join(os.path.expanduser("~"), "Downloads")

def ejecutar_scraping():
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    
    # FORZAR RUTA EN LINUX (Streamlit Cloud)
    if os.name != 'nt':
        chrome_options.binary_location = "/usr/bin/chromium"

    prefs = {
        "download.default_directory": DOWNLOAD_PATH,
        "download.prompt_for_download": False,
        "directory_upgrade": True,
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    try:
        # Intentar inicializar de forma simplificada para evitar SessionNotCreated
        if os.name == 'nt': # Windows local
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
        else: # Linux / Streamlit Cloud
            # En Linux usamos el driver que viene con el paquete chromium-driver
            driver = webdriver.Chrome(options=chrome_options)
        
        driver.get("https://smartcommerce.lat/sign-in")
        wait = WebDriverWait(driver, 35)

        # LOGIN
        wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@type='email'] | //input[contains(@formcontrolname, 'email')]"))).send_keys("rv309962@gmail.com")
        driver.find_element(By.XPATH, "//input[@type='password'] | //input[contains(@formcontrolname, 'password')]").send_keys("Rodrigo052002")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()

        # NAVEGACIÓN A PEDIDOS
        wait.until(EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Pedidos')]"))).click()

        # DESCARGA EXCEL
        wait.until(EC.element_to_be_clickable((By.XPATH, "//app-excel-export-button/button"))).click()
        
        time.sleep(20) 
        return True
    except Exception as e:
        st.error(f"Error detallado: {e}")
        return False
    finally:
        try: driver.quit()
        except: pass

def obtener_ultimo_excel(ruta):
    archivos = glob.glob(os.path.join(ruta, "*.xlsx"))
    archivos_validos = [f for f in archivos if not os.path.basename(f).startswith("~$")]
    if not archivos_validos: return None
    return max(archivos_validos, key=os.path.getctime)

# --- INTERFAZ STREAMLIT ---
st.set_page_config(page_title="Dashboard BI", layout="wide")
st.title("📊 BI SmartCommerce")

if st.sidebar.button("🚀 Actualizar Datos"):
    with st.spinner("Descargando..."):
        if ejecutar_scraping():
            st.sidebar.success("¡Listo!")
            st.rerun()

ultimo_archivo = obtener_ultimo_excel(DOWNLOAD_PATH)

if ultimo_archivo:
    try:
        df = pd.read_excel(ultimo_archivo, skiprows=9, usecols="A:R").dropna(how='all')
        
        # Limpieza rápida
        if 'Total' in df.columns:
            df['Total'] = pd.to_numeric(df['Total'].astype(str).str.replace('L','').str.replace(',','').str.strip(), errors='coerce').fillna(0)
        
        col_fecha = next((c for c in df.columns if 'fecha' in c.lower()), None)
        if col_fecha:
            df[col_fecha] = pd.to_datetime(df[col_fecha], errors='coerce')
            df['Fecha_Filtro'] = df[col_fecha].dt.date

        # Filtros (Lógica: Vacío = Todo)
        st.sidebar.subheader("Filtros")
        f_tienda = st.sidebar.multiselect("Tienda", options=sorted(df['Tienda'].unique() if 'Tienda' in df.columns else []))
        
        q_tienda = f_tienda if f_tienda else df['Tienda'].unique() if 'Tienda' in df.columns else []
        df_filtrado = df[df['Tienda'].isin(q_tienda)] if f_tienda else df

        # Dashboard Básico para probar
        k1, k2 = st.columns(2)
        k1.metric("Pedidos", len(df_filtrado))
        k2.metric("Total", f"L {df_filtrado['Total'].sum():,.2f}")
        
        st.plotly_chart(px.area(df_filtrado.groupby('Fecha_Filtro')['Total'].sum().reset_index(), x='Fecha_Filtro', y='Total'))

    except Exception as e:
        st.error(f"Error en datos: {e}")
else:
    st.info("Presiona 'Actualizar Datos' para comenzar.")
