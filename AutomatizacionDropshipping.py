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

DOWNLOAD_PATH = "/tmp" if not os.name == 'nt' else os.path.join(os.path.expanduser("~"), "Downloads")

# Definición de las dos fuentes de datos
CUENTAS = [
    {"id": "CUENTA_A", "nombre": "Honduras", "user": "rv309962@gmail.com", "pass": "Rodrigo052002"},
    {"id": "CUENTA_B", "nombre": "El Salvador", "user": "overcloudselsalvador@gmail.com", "pass": "Rodrigo052002"}
]

def ejecutar_scraping_limpio(usuario, clave, id_archivo):
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    
    prefs = {"download.default_directory": DOWNLOAD_PATH, "download.prompt_for_download": False}
    chrome_options.add_experimental_option("prefs", prefs)
    
    driver = None
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()) if os.name == 'nt' else None, options=chrome_options)
        driver.get("https://smartcommerce.lat/sign-in")
        wait = WebDriverWait(driver, 45)

        # Login
        wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='email']"))).send_keys(usuario)
        driver.find_element(By.XPATH, "//input[@type='password']").send_keys(clave)
        driver.execute_script("arguments[0].click();", driver.find_element(By.CSS_SELECTOR, "button[type='submit']"))

        # Ir a Pedidos
        time.sleep(8)
        driver.get("https://smartcommerce.lat/orders")

        # Clic en Excel
        btn_excel = wait.until(EC.presence_of_element_located((By.XPATH, "//app-excel-export-button//button")))
        driver.execute_script("arguments[0].click();", btn_excel)
        
        # Esperar la descarga y renombrar inmediatamente
        timeout = 50
        start = time.time()
        while time.time() - start < timeout:
            # Buscar cualquier Excel que NO sea uno de nuestros archivos finales
            archivos = [f for f in os.listdir(DOWNLOAD_PATH) if f.endswith(".xlsx") and not f.startswith("DATO_")]
            if archivos:
                descargado = max([os.path.join(DOWNLOAD_PATH, f) for f in archivos], key=os.path.getctime)
                destino = os.path.join(DOWNLOAD_PATH, f"DATO_{id_archivo}.xlsx")
                
                # Pausa para asegurar que el archivo no esté bloqueado por el sistema
                time.sleep(2)
                if os.path.exists(destino): os.remove(destino)
                os.rename(descargado, destino)
                return True
            time.sleep(2)
        return False
    except Exception as e:
        st.error(f"Error en {id_archivo}: {e}")
        return False
    finally:
        if driver: driver.quit()

# --- INTERFAZ ---
st.set_page_config(page_title="BI Consolidado Pro", layout="wide")
st.title("📊 BI Unificado: Honduras + El Salvador")

if st.sidebar.button("🚀 Actualizar Ambas Cuentas"):
    # PASO 1: LIMPIEZA TOTAL antes de descargar nada nuevo
    for f in glob.glob(os.path.join(DOWNLOAD_PATH, "DATO_*.xlsx")):
        try: os.remove(f)
        except: pass
    
    with st.spinner("Descargando nuevos reportes..."):
        for c in CUENTAS:
            ejecutar_scraping_limpio(c['user'], c['pass'], c['id'])
    st.rerun()

# --- PROCESAMIENTO DE LOS 2 ARCHIVOS ---
archivos_locales = glob.glob(os.path.join(DOWNLOAD_PATH, "DATO_*.xlsx"))

if len(archivos_locales) > 0:
    lista_dfs = []
    for f in archivos_locales:
        try:
            # Usando el rango A11:R11 (skiprows=9)
            df_temp = pd.read_excel(f, skiprows=9).dropna(how='all')
            if not df_temp.empty:
                # Asignar país según el ID del archivo
                df_temp['Pais'] = "Honduras" if "CUENTA_A" in f else "El Salvador"
                lista_dfs.append(df_temp)
        except: continue

    if lista_dfs:
        # Unión final de las dos tablas
        df_final = pd.concat(lista_dfs, ignore_index=True, sort=False)
        
        # Limpieza de Moneda (L y $)
        col_m = next((c for c in df_final.columns if 'total' in c.lower()), 'Total')
        df_final[col_m] = pd.to_numeric(df_final[col_m].astype(str).str.replace('L', '').str.replace('$', '').str.replace(',', '').str.strip(), errors='coerce').fillna(0)

        # Dashboard
        k1, k2, k3 = st.columns(3)
        k1.metric("📦 Pedidos Totales", len(df_final))
        k2.metric("💰 Venta Honduras", f"L {df_final[df_final['Pais']=='Honduras'][col_m].sum():,.2f}")
        k3.metric("💰 Venta El Salvador", f"L {df_final[df_final['Pais']=='El Salvador'][col_m].sum():,.2f}")

        st.divider()
        st.write("### 📋 Tabla Maestra Consolidada")
        st.dataframe(df_final, use_container_width=True)
else:
    st.info("Presiona 'Actualizar Ambas Cuentas' para obtener los datos más recientes.")
