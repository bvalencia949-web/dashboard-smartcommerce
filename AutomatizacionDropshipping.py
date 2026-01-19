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

# --- CONFIGURACIÓN INICIAL ---
try:
    if not hasattr(np, "float"): np.float = float
    if not hasattr(np, "int"): np.int = int
except Exception: pass

DOWNLOAD_PATH = "/tmp" if not os.name == 'nt' else os.path.join(os.path.expanduser("~"), "Downloads")

CUENTAS = [
    {"id": "HN", "nombre": "Honduras", "user": "rv309962@gmail.com", "pass": "Rodrigo052002"},
    {"id": "SV", "nombre": "El Salvador", "user": "overcloudselsalvador@gmail.com", "pass": "Rodrigo052002"}
]

def proceso_scraping_completo():
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    
    prefs = {"download.default_directory": DOWNLOAD_PATH, "download.prompt_for_download": False}
    opts.add_experimental_option("prefs", prefs)
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()) if os.name == 'nt' else None, options=opts)
    wait = WebDriverWait(driver, 45)
    
    try:
        for c in CUENTAS:
            st.write(f"🔐 Accediendo a cuenta: {c['nombre']}...")
            driver.get("https://smartcommerce.lat/sign-in")
            
            # Login
            wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='email']"))).send_keys(c['user'])
            driver.find_element(By.XPATH, "//input[@type='password']").send_keys(c['pass'])
            driver.execute_script("arguments[0].click();", driver.find_element(By.CSS_SELECTOR, "button[type='submit']"))
            
            # Ir a Pedidos y Descargar
            time.sleep(10)
            driver.get("https://smartcommerce.lat/orders")
            time.sleep(5)
            
            btn_excel = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Excel')]")))
            driver.execute_script("arguments[0].click();", btn_excel)
            
            # Esperar descarga y renombrar
            start_descarga = time.time()
            descargado_ok = False
            while time.time() - start_descarga < 60:
                files = [f for f in os.listdir(DOWNLOAD_PATH) if f.endswith(".xlsx") and not f.startswith("DATA_")]
                if files:
                    original = max([os.path.join(DOWNLOAD_PATH, f) for f in files], key=os.path.getctime)
                    final = os.path.join(DOWNLOAD_PATH, f"DATA_{c['id']}.xlsx")
                    time.sleep(3)
                    if os.path.exists(final): os.remove(final)
                    os.rename(original, final)
                    descargado_ok = True
                    break
                time.sleep(2)
            
            if descargado_ok:
                st.write(f"✅ Datos de {c['nombre']} obtenidos.")
                
                # --- PASOS DE CIERRE DE SESIÓN SOLICITADOS ---
                st.write(f"Logout de {c['nombre']}...")
                try:
                    # 1. Clic en el menú de usuario (SVG)
                    menu_user = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/app-root/layout/dense-layout/div/div[1]/div[2]/user/div/button[2]")))
                    driver.execute_script("arguments[0].click();", menu_user)
                    time.sleep(2)
                    
                    # 2. Clic en el botón de cerrar sesión (botón 5 del menú)
                    btn_logout = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[2]/div[2]/div/div/div/button[5]")))
                    driver.execute_script("arguments[0].click();", btn_logout)
                    
                    # 3. Esperar 5 segundos para que regrese al login limpio
                    time.sleep(5)
                except Exception as e_log:
                    st.warning(f"No se pudo cerrar sesión visualmente, forzando limpieza de cookies...")
                    driver.delete_all_cookies() # Plan B: Limpieza técnica
            else:
                st.error(f"❌ No se pudo descargar el archivo de {c['nombre']}.")

        return True
    except Exception as e:
        st.error(f"Error general: {e}")
        return False
    finally:
        driver.quit()

# --- INTERFAZ ---
st.set_page_config(page_title="BI Consolidado", layout="wide")
st.title("📊 BI Unificado: Honduras & El Salvador")

if st.sidebar.button("🚀 Sincronizar Todo"):
    # Limpiar archivos previos
    for f in glob.glob(os.path.join(DOWNLOAD_PATH, "DATA_*.xlsx")):
        try: os.remove(f)
        except: pass
        
    with st.spinner("Ejecutando proceso de login y logout secuencial..."):
        if proceso_scraping_completo():
            st.rerun()

# --- MOSTRAR RESULTADOS ---
archivos = glob.glob(os.path.join(DOWNLOAD_PATH, "DATA_*.xlsx"))

if archivos:
    dfs = []
    for a in archivos:
        try:
            tmp = pd.read_excel(a, skiprows=9).dropna(how='all')
            if not tmp.empty:
                tmp['Pais_BI'] = "Honduras" if "DATA_HN" in a else "El Salvador"
                dfs.append(tmp)
        except: continue
    
    if dfs:
        df = pd.concat(dfs, ignore_index=True, sort=False)
        col_t = next((c for c in df.columns if 'total' in c.lower()), 'Total')
        df[col_t] = pd.to_numeric(df[col_t].astype(str).str.replace('L', '').str.replace('$', '').str.replace(',', '').str.strip(), errors='coerce').fillna(0)

        # Dashboard
        c1, c2, c3 = st.columns(3)
        c1.metric("📦 Pedidos Globales", len(df))
        c2.metric("🇭🇳 Honduras", f"L {df[df['Pais_BI']=='Honduras'][col_t].sum():,.2f}")
        c3.metric("🇸🇻 El Salvador", f"L {df[df['Pais_BI']=='El Salvador'][col_t].sum():,.2f}")

        st.divider()
        st.dataframe(df, use_container_width=True)
else:
    st.info("Presiona 'Sincronizar Todo' para cargar los datos de ambas cuentas.")
