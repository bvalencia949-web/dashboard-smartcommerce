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

# Cuentas a procesar
CUENTAS = [
    {"id": "HN", "nombre": "Honduras", "user": "rv309962@gmail.com", "pass": "Rodrigo052002"},
    {"id": "SV", "nombre": "El Salvador", "user": "overcloudselsalvador@gmail.com", "pass": "Rodrigo052002"}
]

def descargar_datos_cuenta(c):
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    # Esto asegura que cada vez que inicie, el navegador sea "nuevo"
    opts.add_argument("--incognito")
    
    prefs = {"download.default_directory": DOWNLOAD_PATH, "download.prompt_for_download": False}
    opts.add_experimental_option("prefs", prefs)
    
    driver = None
    try:
        service = Service(ChromeDriverManager().install()) if os.name == 'nt' else None
        driver = webdriver.Chrome(service=service, options=opts)
        wait = WebDriverWait(driver, 35)

        # 1. Login con XPATHs robustos
        driver.get("https://smartcommerce.lat/sign-in")
        wait.until(EC.visibility_of_element_located((By.NAME, "email"))).send_keys(c['user'])
        driver.find_element(By.NAME, "password").send_keys(c['pass'])
        
        btn_login = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        driver.execute_script("arguments[0].click();", btn_login)

        # 2. Espera y Salto a Pedidos
        time.sleep(12)
        driver.get("https://smartcommerce.lat/orders")
        time.sleep(6)

        # 3. Descarga de Excel
        # Buscamos cualquier botón que contenga la palabra "Excel"
        btn_excel = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Excel')]")))
        driver.execute_script("arguments[0].click();", btn_excel)
        
        # 4. Esperar el archivo y renombrarlo para que no se pierda
        timeout = 60
        start_time = time.time()
        while time.time() - start_time < timeout:
            archivos = [f for f in os.listdir(DOWNLOAD_PATH) if f.endswith(".xlsx") and not f.startswith("DATO_")]
            if archivos:
                archivo_descargado = max([os.path.join(DOWNLOAD_PATH, f) for f in archivos], key=os.path.getctime)
                destino = os.path.join(DOWNLOAD_PATH, f"DATO_{c['id']}.xlsx")
                time.sleep(3) # Tiempo de seguridad para terminar de escribir
                if os.path.exists(destino): os.remove(destino)
                os.rename(archivo_descargado, destino)
                return True
            time.sleep(2)
        return False
    except Exception as e:
        st.warning(f"⚠️ No se pudo obtener datos de {c['nombre']}. Reintentando en la próxima sincronización.")
        return False
    finally:
        if driver:
            driver.quit() # Cierre TOTAL del navegador para limpiar sesión

# --- INTERFAZ ---
st.set_page_config(page_title="BI Consolidado Pro", layout="wide")
st.title("📊 BI Unificado: Honduras & El Salvador")

if st.sidebar.button("🚀 Sincronizar Ambas Cuentas"):
    # Limpiamos solo los archivos que genera nuestra App
    for f in glob.glob(os.path.join(DOWNLOAD_PATH, "DATO_*.xlsx")):
        try: os.remove(f)
        except: pass
        
    with st.spinner("Iniciando procesos independientes por país..."):
        for cuenta in CUENTAS:
            st.write(f"Conectando a {cuenta['nombre']}...")
            descargar_datos_cuenta(cuenta)
    st.rerun()

# --- UNIFICACIÓN Y VISUALIZACIÓN ---
archivos_recuperados = glob.glob(os.path.join(DOWNLOAD_PATH, "DATO_*.xlsx"))

if archivos_recuperados:
    lista_dfs = []
    for arc in archivos_recuperados:
        try:
            # Tu configuración A11:R11
            df_temp = pd.read_excel(arc, skiprows=9).dropna(how='all')
            if not df_temp.empty:
                df_temp['Pais_Origen'] = "Honduras" if "DATO_HN" in arc else "El Salvador"
                lista_dfs.append(df_temp)
        except: continue
    
    if lista_dfs:
        df_final = pd.concat(lista_dfs, ignore_index=True, sort=False)
        
        # Limpieza de Moneda
        col_total = next((c for c in df_final.columns if 'total' in c.lower()), 'Total')
        df_final[col_total] = pd.to_numeric(df_final[col_total].astype(str).str.replace('L', '').str.replace('$', '').str.replace(',', '').str.strip(), errors='coerce').fillna(0)

        # Dashboard
        m1, m2, m3 = st.columns(3)
        m1.metric("📦 Pedidos Globales", len(df_final))
        m2.metric("🇭🇳 Venta Honduras", f"L {df_final[df_final['Pais_Origen']=='Honduras'][col_total].sum():,.2f}")
        m3.metric("🇸🇻 Venta El Salvador", f"L {df_final[df_final['Pais_Origen']=='El Salvador'][col_total].sum():,.2f}")

        st.divider()
        st.dataframe(df_final, use_container_width=True)
else:
    st.info("👋 Selecciona 'Sincronizar Ambas Cuentas' para cargar la información.")
