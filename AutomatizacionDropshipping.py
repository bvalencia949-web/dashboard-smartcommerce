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

CUENTAS = [
    {"id": "CUENTA_A", "nombre": "Honduras", "user": "rv309962@gmail.com", "pass": "Rodrigo052002"},
    {"id": "CUENTA_B", "nombre": "El Salvador", "user": "overcloudselsalvador@gmail.com", "pass": "Rodrigo052002"}
]

def ejecutar_scraping_seguro(usuario, clave, id_archivo):
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    
    prefs = {"download.default_directory": DOWNLOAD_PATH, "download.prompt_for_download": False}
    chrome_options.add_experimental_option("prefs", prefs)
    
    driver = None
    try:
        service = Service(ChromeDriverManager().install()) if os.name == 'nt' else None
        driver = webdriver.Chrome(service=service, options=chrome_options)
        wait = WebDriverWait(driver, 30)

        # 1. Login
        driver.get("https://smartcommerce.lat/sign-in")
        email_el = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@type='email']")))
        email_el.send_keys(usuario)
        driver.find_element(By.XPATH, "//input[@type='password']").send_keys(clave)
        
        btn_login = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        driver.execute_script("arguments[0].click();", btn_login)

        # 2. Navegación directa a Pedidos para evitar menús laterales
        time.sleep(10) 
        driver.get("https://smartcommerce.lat/orders")

        # 3. Descarga de Excel (Usando JavaScript para evitar Stacktrace)
        time.sleep(5)
        btn_excel = wait.until(EC.presence_of_element_located((By.XPATH, "//app-excel-export-button//button")))
        driver.execute_script("arguments[0].click();", btn_excel)
        
        # 4. Monitoreo de descarga
        timeout = 60
        start = time.time()
        while time.time() - start < timeout:
            archivos = [f for f in os.listdir(DOWNLOAD_PATH) if f.endswith(".xlsx") and not f.startswith("DATO_")]
            if archivos:
                descargado = max([os.path.join(DOWNLOAD_PATH, f) for f in archivos], key=os.path.getctime)
                destino = os.path.join(DOWNLOAD_PATH, f"DATO_{id_archivo}.xlsx")
                time.sleep(3) # Espera a que se suelte el archivo
                if os.path.exists(destino): os.remove(destino)
                os.rename(descargado, destino)
                return True
            time.sleep(2)
        return False
    except Exception as e:
        st.error(f"⚠️ Error en {id_archivo}: {str(e)[:100]}") # Recortamos el error para que sea legible
        return False
    finally:
        if driver: driver.quit()

# --- INTERFAZ STREAMLIT ---
st.set_page_config(page_title="BI Consolidado Global", layout="wide")
st.title("📊 BI Unificado: Honduras + El Salvador")

if st.sidebar.button("🚀 Actualizar Ambas Cuentas"):
    # Limpieza total de excels previos
    for f in glob.glob(os.path.join(DOWNLOAD_PATH, "DATO_*.xlsx")):
        try: os.remove(f)
        except: pass
    
    with st.spinner("Sincronizando servidores..."):
        for c in CUENTAS:
            st.write(f"📥 Descargando {c['nombre']}...")
            ejecutar_scraping_seguro(c['user'], c['pass'], c['id'])
    st.rerun()

# --- CARGA DE DATOS ---
archivos = glob.glob(os.path.join(DOWNLOAD_PATH, "DATO_*.xlsx"))

if len(archivos) > 0:
    all_data = []
    for f in archivos:
        try:
            # Tu rango A11:R11 (skiprows=9)
            df_t = pd.read_excel(f, skiprows=9).dropna(how='all')
            if not df_t.empty:
                df_t['Origen_BI'] = "Honduras" if "CUENTA_A" in f else "El Salvador"
                all_data.append(df_t)
        except: continue

    if all_data:
        df = pd.concat(all_data, ignore_index=True, sort=False)
        
        # Limpieza de Moneda
        col_t = next((c for c in df.columns if 'total' in c.lower()), 'Total')
        df[col_t] = pd.to_numeric(df[col_t].astype(str).str.replace('L', '').str.replace('$', '').str.replace(',', '').str.strip(), errors='coerce').fillna(0)

        # Visualización
        k1, k2, k3 = st.columns(3)
        k1.metric("📦 Pedidos Globales", len(df))
        
        # Filtro de moneda por país
        venta_hn = df[df['Origen_BI'] == 'Honduras'][col_t].sum()
        venta_sv = df[df['Origen_BI'] == 'El Salvador'][col_t].sum()
        
        k2.metric("🇭🇳 Venta Honduras", f"L {venta_hn:,.2f}")
        k3.metric("🇸🇻 Venta El Salvador", f"L {venta_sv:,.2f}")

        st.divider()
        st.write("### 📋 Tabla Maestra Consolidada")
        st.dataframe(df, use_container_width=True)
else:
    st.info("Haz clic en 'Actualizar Ambas Cuentas' para ver la información.")
