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
        # Inicializar Driver
        if os.name == 'nt':
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
        else:
            driver = webdriver.Chrome(options=chrome_options)
        
        driver.get("https://smartcommerce.lat/sign-in")
        wait = WebDriverWait(driver, 30)

        # 1. Login con JavaScript para asegurar que nada lo bloquee
        user_field = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='email'] | //input[contains(@formcontrolname, 'email')]")))
        user_field.send_keys("rv309962@gmail.com")
        
        pass_field = driver.find_element(By.XPATH, "//input[@type='password'] | //input[contains(@formcontrolname, 'password')]")
        pass_field.send_keys("Rodrigo052002")

        login_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        driver.execute_script("arguments[0].click();", login_btn)

        # 2. Navegación a Pedidos
        time.sleep(7) # Espera a que cargue el menú
        btn_pedidos = wait.until(EC.presence_of_element_located((By.XPATH, "//span[contains(text(), 'Pedidos')]")))
        driver.execute_script("arguments[0].click();", btn_pedidos)

        # 3. Exportar Excel
        time.sleep(5)
        btn_excel = wait.until(EC.presence_of_element_located((By.XPATH, "//app-excel-export-button/button")))
        driver.execute_script("arguments[0].click();", btn_excel)
        
        # 4. ESPERA CRÍTICA: Esperar a que el archivo aparezca en la carpeta
        timeout = 40
        start_time = time.time()
        while time.time() - start_time < timeout:
            if any(f.endswith(".xlsx") for f in os.listdir(DOWNLOAD_PATH)):
                return True
            time.sleep(2)
            
        return False
    except Exception as e:
        st.error(f"Error en scraping: {e}")
        return False
    finally:
        try: driver.quit()
        except: pass

def obtener_ultimo_excel(ruta):
    archivos = glob.glob(os.path.join(ruta, "*.xlsx"))
    archivos_validos = [f for f in archivos if not os.path.basename(f).startswith("~$")]
    if not archivos_validos: return None
    return max(archivos_validos, key=os.path.getctime)

# --- INTERFAZ ---
st.set_page_config(page_title="BI Dashboard", layout="wide")
st.title("📊 Business Intelligence: SmartCommerce")

if st.sidebar.button("🚀 Actualizar Datos"):
    # Borrar archivos viejos para no leer datos antiguos
    for f in glob.glob(os.path.join(DOWNLOAD_PATH, "*.xlsx")):
        try: os.remove(f)
        except: pass
        
    with st.spinner("Descargando reporte... esto puede tardar 30 segundos."):
        if ejecutar_scraping():
            st.sidebar.success("¡Datos descargados!")
            st.rerun()
        else:
            st.sidebar.error("No se pudo descargar el archivo. Reintente.")

ultimo_archivo = obtener_ultimo_excel(DOWNLOAD_PATH)

if ultimo_archivo:
    try:
        df = pd.read_excel(ultimo_archivo, skiprows=9, usecols="A:R").dropna(how='all')
        
        # Limpieza de Total
        if 'Total' in df.columns:
            df['Total'] = pd.to_numeric(df['Total'].astype(str).str.replace('L','').str.replace(',','').str.strip(), errors='coerce').fillna(0)
        
        # Fecha
        col_fecha = next((c for c in df.columns if 'fecha' in c.lower()), None)
        if col_fecha:
            df[col_fecha] = pd.to_datetime(df[col_fecha], errors='coerce')
            df['Fecha_Filtro'] = df[col_fecha].dt.date

        # Dashboard con datos totales
        st.sidebar.divider()
        st.sidebar.subheader("Filtros")
        
        col_tienda = next((c for c in df.columns if 'tienda' in c.lower()), 'Tienda')
        f_tienda = st.sidebar.multiselect("Tienda", options=sorted(df[col_tienda].unique()))
        
        df_filtrado = df[df[col_tienda].isin(f_tienda)] if f_tienda else df

        k1, k2 = st.columns(2)
        k1.metric("📦 Pedidos", len(df_filtrado))
        k2.metric("💰 Total", f"L {df_filtrado['Total'].sum():,.2f}")
        
        st.plotly_chart(px.area(df_filtrado.groupby('Fecha_Filtro')['Total'].sum().reset_index(), x='Fecha_Filtro', y='Total'), use_container_width=True)
    except Exception as e:
        st.error(f"Error al procesar: {e}")
else:
    st.info("👋 Pulsa 'Actualizar Datos' para descargar el reporte.")
