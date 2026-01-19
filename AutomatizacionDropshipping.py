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

# Configuración de las dos cuentas
CUENTAS = [
    {"nombre": "Honduras", "user": "rv309962@gmail.com", "pass": "Rodrigo052002"},
    {"nombre": "El Salvador", "user": "overcloudselsalvador@gmail.com", "pass": "Rodrigo052002"}
]

def descargar_reporte(usuario, clave, nombre_archivo):
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
        wait.until(EC.presence_of_element_located((By.XPATH, "/html/body/app-root/layout/empty-layout/div/div/auth-sign-in/div/div[1]/div[2]/form/div[1]/input"))).send_keys(usuario)
        driver.find_element(By.XPATH, "/html/body/app-root/layout/empty-layout/div/div/auth-sign-in/div/div[1]/div[2]/form/div[2]/div/input").send_keys(clave)
        driver.execute_script("arguments[0].click();", driver.find_element(By.CSS_SELECTOR, "button[type='submit']"))

        # Navegación a Pedidos
        time.sleep(8)
        btn_pedidos = wait.until(EC.presence_of_element_located((By.XPATH, "/html/body/app-root/layout/dense-layout/fuse-vertical-navigation/div/div[2]/fuse-vertical-navigation-group-item[3]/fuse-vertical-navigation-basic-item[1]/div/a/div/div/span")))
        driver.execute_script("arguments[0].click();", btn_pedidos)

        # Descarga
        time.sleep(6)
        btn_excel = wait.until(EC.presence_of_element_located((By.XPATH, "/html/body/app-root/layout/dense-layout/div/div[2]/app-orders/div/mat-drawer-container/mat-drawer-content/app-orders-header/div/div[3]/app-excel-export-button/button")))
        driver.execute_script("arguments[0].click();", btn_excel)
        
        # Esperar y renombrar para que no se sobreescriban
        timeout = 50
        start = time.time()
        while time.time() - start < timeout:
            archivos = [f for f in os.listdir(DOWNLOAD_PATH) if f.endswith(".xlsx") and not f.startswith("reporte_")]
            if archivos:
                reciente = max([os.path.join(DOWNLOAD_PATH, f) for f in archivos], key=os.path.getctime)
                nuevo_nombre = os.path.join(DOWNLOAD_PATH, f"reporte_{nombre_archivo}.xlsx")
                if os.path.exists(nuevo_nombre): os.remove(nuevo_nombre)
                os.rename(reciente, nuevo_nombre)
                return True
            time.sleep(2)
        return False
    except Exception as e:
        st.error(f"Error en cuenta {nombre_archivo}: {e}")
        return False
    finally:
        if driver: driver.quit()

# --- INTERFAZ ---
st.set_page_config(page_title="BI Global SmartCommerce", layout="wide")
st.title("📊 BI Global: Honduras & El Salvador")

if st.sidebar.button("🚀 Sincronizar Ambas Cuentas"):
    # Limpiar excels viejos
    for f in glob.glob(os.path.join(DOWNLOAD_PATH, "reporte_*.xlsx")): os.remove(f)
    
    with st.spinner("Descargando datos de todos los logins..."):
        for cuenta in CUENTAS:
            st.write(f"⏳ Procesando {cuenta['nombre']}...")
            descargar_reporte(cuenta['user'], cuenta['pass'], cuenta['nombre'])
        st.rerun()

# Cargar y unir archivos
archivos_descargados = glob.glob(os.path.join(DOWNLOAD_PATH, "reporte_*.xlsx"))

if archivos_descargados:
    dfs = []
    for f in archivos_descargados:
        try:
            temp_df = pd.read_excel(f, skiprows=9).dropna(how='all')
            # Identificar de qué país viene la data
            pais = "Honduras" if "Honduras" in f else "El Salvador"
            temp_df['Pais_Origen'] = pais
            dfs.append(temp_df)
        except: pass
    
    if dfs:
        df = pd.concat(dfs, ignore_index=True)

        # Identificación de columnas
        col_total = 'Total'
        col_tienda = next((c for c in df.columns if 'tienda' in c.lower()), 'Tienda')
        col_fecha = next((c for c in df.columns if 'fecha' in c.lower()), 'Fecha')
        col_estado = 'Estado'
        
        # Limpieza
        df[col_total] = pd.to_numeric(df[col_total].astype(str).str.replace('L', '').str.replace(',', '').str.strip(), errors='coerce').fillna(0)
        
        # Filtros Sidebar
        st.sidebar.subheader("🔍 Filtros Globales")
        f_pais = st.sidebar.multiselect("País", df['Pais_Origen'].unique(), default=df['Pais_Origen'].unique())
        f_tienda = st.sidebar.multiselect("Tienda", sorted(df[col_tienda].unique()))
        
        df_f = df[df['Pais_Origen'].isin(f_pais)]
        if f_tienda: df_f = df_f[df_f[col_tienda].isin(f_tienda)]

        # Dashboard
        m1, m2, m3 = st.columns(3)
        m1.metric("📦 Pedidos Globales", len(df_f))
        m2.metric("💰 Venta Total", f"L {df_f[col_total].sum():,.2f}")
        m3.metric("🌎 Países", len(df_f['Pais_Origen'].unique()))

        st.divider()

        # Gráfico comparativo
        c1, c2 = st.columns(2)
        with c1:
            st.write("### 📈 Ventas por País")
            ventas_pais = df_f.groupby('Pais_Origen')[col_total].sum().reset_index()
            st.plotly_chart(px.bar(ventas_pais, x='Pais_Origen', y=col_total, color='Pais_Origen'), use_container_width=True)
        with c2:
            st.write("### 🚚 Logística Global")
            st.plotly_chart(px.pie(df_f, names='Estado de envío', hole=0.4), use_container_width=True)

        with st.expander("📄 Ver Tabla Consolidada"):
            st.dataframe(df_f, use_container_width=True)
else:
    st.info("👋 Pulsa 'Sincronizar Ambas Cuentas' para extraer la información de los dos logins.")
