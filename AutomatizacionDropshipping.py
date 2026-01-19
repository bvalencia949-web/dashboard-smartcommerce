import numpy as np
import time
import os
import glob
import pandas as pd
import streamlit as st
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# --- CONFIGURACIÓN DE RUTA ---
DOWNLOAD_PATH = "/tmp" if not os.name == 'nt' else os.path.join(os.path.expanduser("~"), "Downloads")

CUENTAS = [
    {"id": "HN", "nombre": "Honduras", "user": "rv309962@gmail.com", "pass": "Rodrigo052002"},
    {"id": "SV", "nombre": "El Salvador", "user": "overcloudselsalvador@gmail.com", "pass": "Rodrigo052002"}
]

def proceso_unificado_scraping():
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
            # 1. IR A LA PÁGINA (Vuelve a ingresar siempre a la misma URL)
            st.write(f"🌐 Ingresando a la web para: {c['nombre']}...")
            driver.get("https://smartcommerce.lat/sign-in")
            time.sleep(3)
            
            # 2. LOGIN
            wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='email']"))).send_keys(c['user'])
            driver.find_element(By.XPATH, "//input[@type='password']").send_keys(c['pass'])
            driver.execute_script("arguments[0].click();", driver.find_element(By.CSS_SELECTOR, "button[type='submit']"))
            
            # 3. NAVEGAR A PEDIDOS Y DESCARGAR
            time.sleep(12)
            driver.get("https://smartcommerce.lat/orders")
            time.sleep(6)
            
            btn_excel = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Excel')]")))
            driver.execute_script("arguments[0].click();", btn_excel)
            
            # 4. ESPERAR DESCARGA
            start_descarga = time.time()
            archivo_listo = False
            while time.time() - start_descarga < 60:
                files = [f for f in os.listdir(DOWNLOAD_PATH) if f.endswith(".xlsx") and not f.startswith("DATO_")]
                if files:
                    orig = max([os.path.join(DOWNLOAD_PATH, f) for f in files], key=os.path.getctime)
                    dest = os.path.join(DOWNLOAD_PATH, f"DATO_{c['id']}.xlsx")
                    time.sleep(4)
                    if os.path.exists(dest): os.remove(dest)
                    os.rename(orig, dest)
                    archivo_listo = True
                    break
                time.sleep(2)
            
            if archivo_listo:
                st.success(f"✅ Archivo de {c['nombre']} capturado.")
                
                # 5. SALIR (LOGOUT) - Pasos específicos del usuario
                st.write(f"🚪 Cerrando sesión de {c['nombre']}...")
                try:
                    # Paso 1: Clic en el menú usuario (SVG/Botón)
                    menu_user = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/app-root/layout/dense-layout/div/div[1]/div[2]/user/div/button[2]")))
                    driver.execute_script("arguments[0].click();", menu_user)
                    time.sleep(2)
                    
                    # Paso 2: Clic en el botón 5 (Cerrar Sesión)
                    btn_logout = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[2]/div[2]/div/div/div/button[5]")))
                    driver.execute_script("arguments[0].click();", btn_logout)
                    
                    # Paso 3: ESPERA DE 7 SEGUNDOS para limpiar servidor
                    st.warning("⏳ Esperando 7 segundos de enfriamiento...")
                    time.sleep(7)
                    
                except Exception as e_logout:
                    st.error("⚠️ Error al intentar salir visualmente. Limpiando sesión por URL...")
                    driver.get("https://smartcommerce.lat/sign-in") # Forzar regreso al inicio
                    time.sleep(7)
            
        return True
    except Exception as e:
        st.error(f"❌ Error crítico: {e}")
        return False
    finally:
        driver.quit()

# --- INTERFAZ ---
st.set_page_config(page_title="Dashboard BI Consolidado", layout="wide")
st.title("📊 BI Unificado: Honduras & El Salvador")

if st.sidebar.button("🚀 Iniciar Sincronización"):
    # Limpiar excels anteriores
    for f in glob.glob(os.path.join(DOWNLOAD_PATH, "DATO_*.xlsx")):
        try: os.remove(f)
        except: pass
        
    with st.spinner("Ejecutando ciclo: Login -> Descarga -> Logout -> Espera 7s -> Re-ingreso..."):
        if proceso_unificado_scraping():
            st.rerun()

# --- RESULTADOS ---
archivos = glob.glob(os.path.join(DOWNLOAD_PATH, "DATO_*.xlsx"))
if archivos:
    lista_dfs = []
    for a in archivos:
        try:
            df_t = pd.read_excel(a, skiprows=9).dropna(how='all')
            if not df_t.empty:
                df_t['País'] = "Honduras" if "DATO_HN" in a else "El Salvador"
                lista_dfs.append(df_t)
        except: continue
    
    if lista_dfs:
        df_final = pd.concat(lista_dfs, ignore_index=True)
        # Limpieza de Moneda
        col_t = next((c for c in df_final.columns if 'total' in c.lower()), 'Total')
        df_final[col_t] = pd.to_numeric(df_final[col_t].astype(str).str.replace('L', '').str.replace('$', '').str.replace(',', '').str.strip(), errors='coerce').fillna(0)

        # KPIs
        c1, c2, c3 = st.columns(3)
        c1.metric("📦 Pedidos Globales", len(df_final))
        c1.metric("🇭🇳 Honduras", f"L {df_final[df_final['País']=='Honduras'][col_t].sum():,.2f}")
        c1.metric("🇸🇻 El Salvador", f"L {df_final[df_final['País']=='El Salvador'][col_t].sum():,.2f}")
        
        st.divider()
        st.dataframe(df_final, use_container_width=True)
