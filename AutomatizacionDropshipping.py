import numpy as np
import time
import os
import glob
import pandas as pd
import streamlit as st
import plotly.express as px
from datetime import datetime
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
    chrome_options.add_argument("--window-size=1920,1080")
    
    if os.name != 'nt':
        chrome_options.binary_location = "/usr/bin/chromium"

    prefs = {"download.default_directory": DOWNLOAD_PATH, "download.prompt_for_download": False}
    chrome_options.add_experimental_option("prefs", prefs)
    
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()) if os.name == 'nt' else None, options=chrome_options)
        driver.get("https://smartcommerce.lat/sign-in")
        wait = WebDriverWait(driver, 45)

        # Login
        wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='email']"))).send_keys("rv309962@gmail.com")
        driver.find_element(By.XPATH, "//input[@type='password']").send_keys("Rodrigo052002")
        driver.execute_script("arguments[0].click();", driver.find_element(By.CSS_SELECTOR, "button[type='submit']"))

        # Navegación y descarga
        time.sleep(8)
        driver.get("https://smartcommerce.lat/orders")
        time.sleep(6)
        btn_excel = wait.until(EC.presence_of_element_located((By.XPATH, "//app-excel-export-button//button")))
        driver.execute_script("arguments[0].click();", btn_excel)
        
        timeout = 50
        start = time.time()
        while time.time() - start < timeout:
            if any(f.endswith(".xlsx") for f in os.listdir(DOWNLOAD_PATH)): return True
            time.sleep(2)
        return False
    except Exception as e:
        st.error(f"Error en scraping: {e}")
        return False
    finally:
        try: driver.quit()
        except: pass

def obtener_ultimo_excel(ruta):
    archivos = [os.path.join(ruta, f) for f in os.listdir(ruta) if f.endswith(".xlsx") and not f.startswith("~$")]
    return max(archivos, key=os.path.getctime) if archivos else None

# --- INTERFAZ STREAMLIT ---
st.set_page_config(page_title="BI Dashboard Pro", layout="wide")
st.title("📊 BI SmartCommerce")

if st.sidebar.button("🚀 Actualizar Datos"):
    for f in glob.glob(os.path.join(DOWNLOAD_PATH, "*.xlsx")):
        try: os.remove(f)
        except: pass
    with st.spinner("Descargando..."):
        if ejecutar_scraping(): st.rerun()

ultimo_archivo = obtener_ultimo_excel(DOWNLOAD_PATH)

if ultimo_archivo:
    try:
        # Volvemos a la carga normal de datos
        df = pd.read_excel(ultimo_archivo, skiprows=9).dropna(how='all')

        # Detección de columnas
        col_total = 'Total'
        col_estado = 'Estado'
        col_envio = 'Estado de envío'
        col_productos = 'Productos'
        col_tienda = next((c for c in df.columns if 'tienda' in c.lower()), 'Tienda')
        col_cliente = next((c for c in df.columns if 'cliente' in c.lower() or 'nombre' in c.lower()), 'Cliente')
        col_telefono = next((c for c in df.columns if 'tel' in c.lower()), 'Teléfono')
        col_fecha_orig = next((c for c in df.columns if 'fecha' in c.lower()), None)
        
        # Limpieza de Moneda
        df[col_total] = pd.to_numeric(df[col_total].astype(str).str.replace('L', '').str.replace(',', '').str.strip(), errors='coerce').fillna(0)
        
        # --- PROCESAMIENTO DE FECHA COMO DATE (NO STRING) ---
        if col_fecha_orig:
            # Convertimos a datetime y extraemos el .date() inmediatamente
            # Esto elimina la hora y detiene la conversión a UTC de Streamlit
            df['Fecha_Limpia'] = pd.to_datetime(df[col_fecha_orig]).dt.date
            df = df.dropna(subset=['Fecha_Limpia'])

        # Sidebar Filtros
        st.sidebar.subheader("🔍 Filtros")
        min_d, max_d = df['Fecha_Limpia'].min(), df['Fecha_Limpia'].max()
        f_rango = st.sidebar.slider("Rango", min_d, max_d, (min_d, max_d))
        
        # Filtros Multiselect
        def aplicar_f(col, lista):
            return df[col].isin(lista) if lista else df[col].isin(df[col].unique())

        f_t = st.sidebar.multiselect("Tienda", sorted(df[col_tienda].unique()))
        f_e = st.sidebar.multiselect("Estado", sorted(df[col_estado].unique()))
        f_v = st.sidebar.multiselect("Envío", sorted(df[col_envio].unique()))
        f_p = st.sidebar.multiselect("Productos", sorted(df[col_productos].unique()))

        # Filtrado Final
        df_f = df[
            (df['Fecha_Limpia'] >= f_rango[0]) & 
            (df['Fecha_Limpia'] <= f_rango[1]) &
            aplicar_f(col_tienda, f_t) &
            aplicar_f(col_estado, f_e) &
            aplicar_f(col_envio, f_v) &
            aplicar_f(col_productos, f_p)
        ]

        # Dashboard
        k1, k2, k3 = st.columns(3)
        k1.metric("📦 Pedidos", len(df_f))
        k2.metric("💰 Total", f"L {df_f[col_total].sum():,.2f}")
        k3.metric("🎫 Ticket Prom.", f"L {df_f[col_total].mean():,.2f}" if not df_f.empty else "0")

        st.divider()

        # Gráficos
        c1, c2 = st.columns(2)
        with c1:
            ventas_dia = df_f.groupby('Fecha_Limpia')[col_total].sum().reset_index()
            st.plotly_chart(px.area(ventas_dia, x='Fecha_Limpia', y=col_total, title="Ingresos"), use_container_width=True)
        with c2:
            st.plotly_chart(px.pie(df_f, names=col_envio, title="Estados de Envío", hole=0.4), use_container_width=True)

        # TABLA FINAL (Con Cliente y Teléfono)
        with st.expander("📄 Ver Tabla de Datos"):
            cols_ver = ['Fecha_Limpia', col_cliente, col_telefono, col_tienda, col_productos, col_estado, col_envio, col_total]
            columnas_validas = [c for c in cols_ver if c in df_f.columns]
            
            # Ordenar y Renombrar
            res = df_f[columnas_validas].copy().sort_values('Fecha_Limpia', ascending=False)
            res = res.rename(columns={'Fecha_Limpia': 'Fecha', col_total: 'Monto (L)'})
            
            st.dataframe(res, use_container_width=True)

    except Exception as e:
        st.error(f"Error procesando datos: {e}")
else:
    st.info("👋 Pulsa 'Actualizar Datos' para cargar la información.")
