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

# Definir ruta según el sistema (Streamlit Cloud o Local)
DOWNLOAD_PATH = "/tmp" if not os.name == 'nt' else os.path.join(os.path.expanduser("~"), "Downloads")

CUENTAS = [
    {"id": "HN", "nombre": "Honduras", "user": "rv309962@gmail.com", "pass": "Rodrigo052002"},
    {"id": "SV", "nombre": "El Salvador", "user": "overcloudselsalvador@gmail.com", "pass": "Rodrigo052002"}
]

def scraping_pro(c):
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    prefs = {"download.default_directory": DOWNLOAD_PATH, "download.prompt_for_download": False}
    opts.add_experimental_option("prefs", prefs)
    
    driver = None
    try:
        service = Service(ChromeDriverManager().install()) if os.name == 'nt' else None
        driver = webdriver.Chrome(service=service, options=opts)
        wait = WebDriverWait(driver, 45)

        # Login
        driver.get("https://smartcommerce.lat/sign-in")
        wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='email']"))).send_keys(c['user'])
        driver.find_element(By.XPATH, "//input[@type='password']").send_keys(c['pass'])
        driver.execute_script("arguments[0].click();", driver.find_element(By.CSS_SELECTOR, "button[type='submit']"))

        # SALTO DIRECTO (Evita clics en menús que fallan)
        time.sleep(12)
        driver.get("https://smartcommerce.lat/orders")
        
        # Descarga
        time.sleep(6)
        btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Excel')] | //app-excel-export-button//button")))
        driver.execute_script("arguments[0].click();", btn)
        
        # Captura de archivo
        start = time.time()
        while time.time() - start < 60:
            raw_files = [f for f in os.listdir(DOWNLOAD_PATH) if f.endswith(".xlsx") and not f.startswith("DATA_")]
            if raw_files:
                original = max([os.path.join(DOWNLOAD_PATH, f) for f in raw_files], key=os.path.getctime)
                final_name = os.path.join(DOWNLOAD_PATH, f"DATA_{c['id']}.xlsx")
                time.sleep(3) # Espera técnica de escritura
                if os.path.exists(final_name): os.remove(final_name)
                os.rename(original, final_name)
                return True
            time.sleep(2)
        return False
    except Exception as e:
        st.error(f"Error en {c['nombre']}: {str(e)[:100]}")
        return False
    finally:
        if driver: driver.quit()

# --- UI ---
st.set_page_config(page_title="Dashboard Global", layout="wide")
st.title("📊 BI Consolidado HN & SV")

if st.sidebar.button("🚀 Sincronizar Datos"):
    # Limpiar antes de empezar
    for f in glob.glob(os.path.join(DOWNLOAD_PATH, "DATA_*.xlsx")):
        try: os.remove(f)
        except: pass
    
    with st.spinner("Descargando reportes de ambas cuentas..."):
        for c in CUENTAS:
            st.write(f"Procesando {c['nombre']}...")
            scraping_pro(c)
    st.rerun()

# --- PROCESAMIENTO ---
archivos = glob.glob(os.path.join(DOWNLOAD_PATH, "DATA_*.xlsx"))

if archivos:
    dfs = []
    for a in archivos:
        try:
            # Usar skiprows=9 para el rango A11:R11
            tmp = pd.read_excel(a, skiprows=9).dropna(how='all')
            if not tmp.empty:
                tmp['País'] = "Honduras" if "DATA_HN" in a else "El Salvador"
                dfs.append(tmp)
        except: continue

    if dfs:
        df = pd.concat(dfs, ignore_index=True, sort=False)
        col_t = next((c for c in df.columns if 'total' in c.lower()), 'Total')
        df[col_t] = pd.to_numeric(df[col_t].astype(str).str.replace('L', '').str.replace('$', '').str.replace(',', '').str.strip(), errors='coerce').fillna(0)

        # KPIs
        c1, c2, c3 = st.columns(3)
        c1.metric("📦 Pedidos Totales", len(df))
        c2.metric("🇭🇳 Venta HN", f"L {df[df['País']=='Honduras'][col_t].sum():,.2f}")
        c3.metric("🇸🇻 Venta SV", f"L {df[df['País']=='El Salvador'][col_t].sum():,.2f}")

        st.divider()
        st.dataframe(df, use_container_width=True)
else:
    st.info("No hay datos cargados. Pulsa el botón para sincronizar.")
