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
    chrome_options.add_argument("--window-size=1920,1080")
    
    if os.name != 'nt':
        chrome_options.binary_location = "/usr/bin/chromium"

    prefs = {
        "download.default_directory": DOWNLOAD_PATH,
        "download.prompt_for_download": False,
        "directory_upgrade": True,
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    try:
        if os.name == 'nt':
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
        else:
            driver = webdriver.Chrome(options=chrome_options)
        
        driver.get("https://smartcommerce.lat/sign-in")
        wait = WebDriverWait(driver, 40)

        # 1. LOGIN
        user_input = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='email'] | //input[contains(@formcontrolname, 'email')]")))
        user_input.send_keys("rv309962@gmail.com")
        
        pass_input = driver.find_element(By.XPATH, "//input[@type='password'] | //input[contains(@formcontrolname, 'password')]")
        pass_input.send_keys("Rodrigo052002")

        # Clic en login usando JavaScript para evitar intercepciones
        login_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        driver.execute_script("arguments[0].click();", login_btn)

        # 2. ESPERAR A QUE CARGUE EL DASHBOARD
        time.sleep(5)

        # 3. IR A PEDIDOS (Clic forzado con JS)
        btn_pedidos = wait.until(EC.presence_of_element_located((By.XPATH, "//span[contains(text(), 'Pedidos')]")))
        driver.execute_script("arguments[0].click();", btn_pedidos)
        
        # 4. BOTÓN EXCEL (Clic forzado con JS)
        btn_excel = wait.until(EC.presence_of_element_located((By.XPATH, "//app-excel-export-button/button")))
        driver.execute_script("arguments[0].click();", btn_excel)
        
        # Espera de seguridad para la descarga
        time.sleep(20) 
        return True
    except Exception as e:
        st.error(f"Error detallado en la navegación: {e}")
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
st.set_page_config(page_title="BI SmartCommerce", layout="wide")
st.title("📊 Business Intelligence: SmartCommerce")

st.sidebar.header("⚙️ Configuración")
if st.sidebar.button("🚀 Actualizar Datos"):
    with st.spinner("Descargando reporte desde SmartCommerce..."):
        if ejecutar_scraping():
            st.sidebar.success("¡Datos descargados con éxito!")
            st.rerun()

ultimo_archivo = obtener_ultimo_excel(DOWNLOAD_PATH)

if ultimo_archivo:
    try:
        df = pd.read_excel(ultimo_archivo, skiprows=9, usecols="A:R").dropna(how='all')
        
        # Limpieza de Total
        if 'Total' in df.columns:
            df['Total'] = pd.to_numeric(df['Total'].astype(str).str.replace('L','').str.replace(',','').str.strip(), errors='coerce').fillna(0)
        
        # Procesar Fechas
        col_fecha = next((c for c in df.columns if 'fecha' in c.lower()), None)
        if col_fecha:
            df[col_fecha] = pd.to_datetime(df[col_fecha], errors='coerce')
            df['Fecha_Filtro'] = df[col_fecha].dt.date

        # Columnas automáticas
        col_tienda = next((c for c in df.columns if 'tienda' in c.lower() or 'comercio' in c.lower()), 'Tienda')
        col_envio = next((c for c in df.columns if 'envío' in c.lower()), 'Estado Envío')
        col_estado = next((c for c in df.columns if 'estado' in c.lower() and 'envío' not in c.lower()), 'Estado')

        # Filtros (Vaciados por defecto = Muestran todo)
        st.sidebar.divider()
        f_tienda = st.sidebar.multiselect("Tienda", options=sorted(df[col_tienda].unique() if col_tienda in df.columns else []))
        f_estado = st.sidebar.multiselect("Estado Pedido", options=sorted(df[col_estado].unique() if col_estado in df.columns else []))
        
        # Aplicación de filtros inteligentes
        df_filtrado = df.copy()
        if f_tienda: df_filtrado = df_filtrado[df_filtrado[col_tienda].isin(f_tienda)]
        if f_estado: df_filtrado = df_filtrado[df_filtrado[col_estado].isin(f_estado)]

        # Dashboard
        m1, m2 = st.columns(2)
        m1.metric("📦 Pedidos", len(df_filtrado))
        m2.metric("💰 Venta Total", f"L {df_filtrado['Total'].sum():,.2f}")

        st.plotly_chart(px.area(df_filtrado.groupby('Fecha_Filtro')['Total'].sum().reset_index(), x='Fecha_Filtro', y='Total', title="Tendencia de Ventas"), use_container_width=True)

    except Exception as e:
        st.error(f"Error al procesar los datos: {e}")
else:
    st.info("👋 Pulsa 'Actualizar Datos' para descargar el reporte.")
