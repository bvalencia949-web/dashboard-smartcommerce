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

# Definición de las dos cuentas para la misma web
CUENTAS = [
    {"id": "HN", "nombre": "Honduras", "user": "rv309962@gmail.com", "pass": "Rodrigo052002"},
    {"id": "SV", "nombre": "El Salvador", "user": "overcloudselsalvador@gmail.com", "pass": "Rodrigo052002"}
]

def ejecutar_scraping_consolidado():
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
        wait = WebDriverWait(driver, 45)

        for c in CUENTAS:
            st.write(f"🔄 Procesando cuenta: {c['nombre']}...")
            
            # 1. Ingreso a la web
            driver.get("https://smartcommerce.lat/sign-in")
            
            # 2. Login
            email_f = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@type='email']")))
            email_f.clear()
            email_f.send_keys(c['user'])
            
            pass_f = driver.find_element(By.XPATH, "//input[@type='password']")
            pass_f.clear()
            pass_f.send_keys(c['pass'])
            
            login_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            driver.execute_script("arguments[0].click();", login_btn)

            # 3. Navegación a Pedidos y Descarga
            time.sleep(10)
            driver.get("https://smartcommerce.lat/orders")
            time.sleep(5)
            
            btn_excel = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Excel')] | //app-excel-export-button//button")))
            driver.execute_script("arguments[0].click();", btn_excel)
            
            # 4. Espera del archivo y renombrado inmediato
            start = time.time()
            descargado = False
            while time.time() - start < 60:
                # Buscamos archivos que no empiecen con 'DATO_'
                archivos = [f for f in os.listdir(DOWNLOAD_PATH) if f.endswith(".xlsx") and not f.startswith("DATO_")]
                if archivos:
                    archivo_orig = max([os.path.join(DOWNLOAD_PATH, f) for f in archivos], key=os.path.getctime)
                    destino = os.path.join(DOWNLOAD_PATH, f"DATO_{c['id']}.xlsx")
                    time.sleep(3) # Seguridad
                    if os.path.exists(destino): os.remove(destino)
                    os.rename(archivo_orig, destino)
                    descargado = True
                    break
                time.sleep(2)
            
            if descargado:
                st.write(f"✅ Descarga de {c['nombre']} completada.")
                
                # 5. CIERRE DE SESIÓN (Logout)
                try:
                    # Clic en menú usuario
                    btn_menu = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/app-root/layout/dense-layout/div/div[1]/div[2]/user/div/button[2]")))
                    driver.execute_script("arguments[0].click();", btn_menu)
                    time.sleep(2)
                    
                    # Clic en botón de salir (botón 5)
                    btn_exit = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[2]/div[2]/div/div/div/button[5]")))
                    driver.execute_script("arguments[0].click();", btn_exit)
                    
                    st.write("⏳ Esperando 7 segundos para la siguiente cuenta...")
                    time.sleep(7)
                except:
                    st.warning(f"No se pudo hacer logout visual en {c['nombre']}, limpiando cookies.")
                    driver.delete_all_cookies()
                    time.sleep(7)
                    
        return True
    except Exception as e:
        st.error(f"Error en el proceso: {e}")
        return False
    finally:
        if driver: driver.quit()

# --- INTERFAZ STREAMLIT ---
st.set_page_config(page_title="BI Dashboard Consolidado", layout="wide")
st.title("📊 Consolidado Global: HN & SV")

if st.sidebar.button("🚀 Sincronizar Ambas Cuentas"):
    # Limpiar archivos previos de nuestra app
    for f in glob.glob(os.path.join(DOWNLOAD_PATH, "DATO_*.xlsx")):
        try: os.remove(f)
        except: pass
        
    with st.spinner("Ejecutando proceso secuencial..."):
        if ejecutar_scraping_consolidado():
            st.rerun()

# --- PROCESAMIENTO DE ARCHIVOS ---
archivos_finales = glob.glob(os.path.join(DOWNLOAD_PATH, "DATO_*.xlsx"))

if archivos_finales:
    lista_dfs = []
    for f in archivos_finales:
        try:
            df_temp = pd.read_excel(f, skiprows=9).dropna(how='all')
            if not df_temp.empty:
                df_temp['Pais_ID'] = "Honduras" if "DATO_HN" in f else "El Salvador"
                lista_dfs.append(df_temp)
        except: continue

    if lista_dfs:
        df = pd.concat(lista_dfs, ignore_index=True)
        
        # Identificación y Limpieza
        col_total = 'Total'
        if col_total in df.columns:
            df[col_total] = pd.to_numeric(df[col_total].astype(str).str.replace('L', '').str.replace('$', '').str.replace(',', '').str.strip(), errors='coerce').fillna(0)
        
        # KPIs por País
        k1, k2, k3 = st.columns(3)
        k1.metric("📦 Total Pedidos", len(df))
        
        v_hn = df[df['Pais_ID']=='Honduras'][col_total].sum() if 'Honduras' in df['Pais_ID'].values else 0
        v_sv = df[df['Pais_ID']=='El Salvador'][col_total].sum() if 'El Salvador' in df['Pais_ID'].values else 0
        
        k2.metric("🇭🇳 Venta Honduras", f"L {v_hn:,.2f}")
        k3.metric("🇸🇻 Venta El Salvador", f"L {v_sv:,.2f}")

        st.divider()
        st.write("### 📋 Detalle de Pedidos Unificados")
        st.dataframe(df, use_container_width=True)
else:
    st.info("👋 Haz clic en el botón lateral para obtener los datos actualizados de ambos países.")
