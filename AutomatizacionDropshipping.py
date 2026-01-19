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

# --- CONFIGURACIÓN ---
DOWNLOAD_PATH = "/tmp" if not os.name == 'nt' else os.path.join(os.path.expanduser("~"), "Downloads")

CUENTAS = [
    {"id": "HN", "nombre": "Honduras", "user": "rv309962@gmail.com", "pass": "Rodrigo052002"},
    {"id": "SV", "nombre": "El Salvador", "user": "overcloudselsalvador@gmail.com", "pass": "Rodrigo052002"}
]

def ejecutar_extraccion_segura(c):
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--incognito") # Sesión privada para evitar rastros de la otra cuenta
    
    prefs = {"download.default_directory": DOWNLOAD_PATH, "download.prompt_for_download": False}
    opts.add_experimental_option("prefs", prefs)
    
    driver = None
    status = st.empty() # Para mostrar el progreso en pantalla
    
    try:
        service = Service(ChromeDriverManager().install()) if os.name == 'nt' else None
        driver = webdriver.Chrome(service=service, options=opts)
        wait = WebDriverWait(driver, 40)

        # 1. Login
        status.text(f"⏳ [{c['nombre']}] Accediendo al portal...")
        driver.get("https://smartcommerce.lat/sign-in")
        
        email_field = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='email']")))
        email_field.clear()
        email_field.send_keys(c['user'])
        
        pass_field = driver.find_element(By.XPATH, "//input[@type='password']")
        pass_field.clear()
        pass_field.send_keys(c['pass'])
        
        driver.execute_script("arguments[0].click();", driver.find_element(By.CSS_SELECTOR, "button[type='submit']"))

        # 2. Salto a Pedidos
        time.sleep(12)
        status.text(f"⏳ [{c['nombre']}] Saltando a Pedidos...")
        driver.get("https://smartcommerce.lat/orders")
        
        # 3. Descarga de Excel
        time.sleep(8)
        status.text(f"⏳ [{c['nombre']}] Generando Excel...")
        
        # Intentamos localizar el botón por XPATH dinámico
        btn_excel = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Excel')] | //app-excel-export-button//button")))
        driver.execute_script("arguments[0].click();", btn_excel)
        
        # 4. Monitoreo de archivo
        status.text(f"⏳ [{c['nombre']}] Esperando descarga...")
        timeout = 60
        start = time.time()
        while time.time() - start < timeout:
            archivos = [f for f in os.listdir(DOWNLOAD_PATH) if f.endswith(".xlsx") and not f.startswith("DATO_")]
            if archivos:
                descargado = max([os.path.join(DOWNLOAD_PATH, f) for f in archivos], key=os.path.getctime)
                destino = os.path.join(DOWNLOAD_PATH, f"DATO_{c['id']}.xlsx")
                time.sleep(4) # Espera técnica para finalizar escritura
                if os.path.exists(destino): os.remove(destino)
                os.rename(descargado, destino)
                status.success(f"✅ [{c['nombre']}] Descargado con éxito.")
                return True
            time.sleep(2)
        
        status.error(f"❌ [{c['nombre']}] Tiempo de espera de descarga agotado.")
        return False

    except Exception as e:
        status.error(f"❌ Error en {c['nombre']}: {str(e)[:100]}")
        return False
    finally:
        if driver:
            driver.quit()

# --- INTERFAZ STREAMLIT ---
st.set_page_config(page_title="BI Consolidado", layout="wide")
st.title("📊 BI Unificado: Honduras & El Salvador")

if st.sidebar.button("🚀 Sincronizar Ambas Cuentas"):
    # Limpieza previa de archivos temporales
    for f in glob.glob(os.path.join(DOWNLOAD_PATH, "DATO_*.xlsx")):
        try: os.remove(f)
        except: pass
    
    # Ejecutamos una cuenta tras otra de forma aislada
    for cuenta in CUENTAS:
        ejecutar_extraccion_segura(cuenta)
    
    st.success("Proceso de sincronización finalizado.")
    st.rerun()

# --- CARGA Y UNIFICACIÓN ---
archivos_recuperados = glob.glob(os.path.join(DOWNLOAD_PATH, "DATO_*.xlsx"))

if archivos_recuperados:
    lista_dfs = []
    for arc in archivos_recuperados:
        try:
            df_temp = pd.read_excel(arc, skiprows=9).dropna(how='all')
            if not df_temp.empty:
                df_temp['Pais_BI'] = "Honduras" if "DATO_HN" in arc else "El Salvador"
                lista_dfs.append(df_temp)
        except Exception as e:
            st.warning(f"Error procesando {arc}: {e}")

    if lista_dfs:
        df_final = pd.concat(lista_dfs, ignore_index=True, sort=False)
        
        # Limpieza de Moneda
        col_total = next((c for c in df_final.columns if 'total' in c.lower()), 'Total')
        df_final[col_total] = pd.to_numeric(df_final[col_total].astype(str).str.replace('L', '').str.replace('$', '').str.replace(',', '').str.strip(), errors='coerce').fillna(0)

        # Dashboard Visual
        k1, k2, k3 = st.columns(3)
        k1.metric("📦 Pedidos Globales", len(df_final))
        k2.metric("🇭🇳 Venta HN", f"L {df_final[df_final['Pais_BI']=='Honduras'][col_total].sum():,.2f}")
        k3.metric("🇸🇻 Venta SV", f"L {df_final[df_final['Pais_BI']=='El Salvador'][col_total].sum():,.2f}")

        st.divider()
        st.write("### 📄 Tabla Maestra Consolidada")
        st.dataframe(df_final, use_container_width=True)
else:
    st.info("👋 No hay datos disponibles. Haz clic en 'Sincronizar Ambas Cuentas'.")
