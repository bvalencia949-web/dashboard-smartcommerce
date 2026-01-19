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
# 
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# --- CONFIGURACIÓN DE RUTAS ---
DOWNLOAD_PATH = "/tmp" if not os.name == 'nt' else os.path.join(os.path.expanduser("~"), "Downloads")

def ejecutar_scraping():
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    
    # Prefs de descarga
    prefs = {
        "download.default_directory": DOWNLOAD_PATH,
        "download.prompt_for_download": False,
        "directory_upgrade": True,
        "safebrowsing.enabled": False
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    try:
        # Inicialización compatible del Driver
        if os.name == 'nt': # Windows
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
        else: # Linux / Streamlit Cloud
            driver = webdriver.Chrome(options=chrome_options)
        
        driver.get("https://smartcommerce.lat/sign-in")
        wait = WebDriverWait(driver, 30)

        # Login
        email_f = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='email']")))
        email_f.send_keys("rv309962@gmail.com")
        
        pass_f = driver.find_element(By.XPATH, "//input[@type='password']")
        pass_f.send_keys("Rodrigo052002")

        login_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        driver.execute_script("arguments[0].click();", login_btn)

        # Ir a pedidos directamente para mayor velocidad
        time.sleep(5)
        driver.get("https://smartcommerce.lat/orders")

        # Descarga
        time.sleep(5)
        btn_excel = wait.until(EC.element_to_be_clickable((By.XPATH, "//app-excel-export-button//button")))
        driver.execute_script("arguments[0].click();", btn_excel)
        
        # Esperar archivo
        timeout = 40
        start = time.time()
        while time.time() - start < timeout:
            if any(f.endswith(".xlsx") for f in os.listdir(DOWNLOAD_PATH)):
                return True
            time.sleep(2)
        return False
    except Exception as e:
        st.error(f"Error específico: {e}")
        return False
    finally:
        try: driver.quit()
        except: pass

def obtener_ultimo_excel(ruta):
    archivos = glob.glob(os.path.join(ruta, "*.xlsx"))
    archivos_validos = [f for f in archivos if not os.path.basename(f).startswith("~$")]
    if not archivos_validos: return None
    return max(archivos_validos, key=os.path.getctime)

# --- INTERFAZ STREAMLIT ---
st.set_page_config(page_title="BI Dashboard Pro", layout="wide")
st.title("📊 Business Intelligence: SmartCommerce")

if st.sidebar.button("🚀 Actualizar Datos"):
    # Limpiar archivos viejos
    for f in glob.glob(os.path.join(DOWNLOAD_PATH, "*.xlsx")):
        try: os.remove(f)
        except: pass
    
    with st.spinner("Descargando reporte..."):
        if ejecutar_scraping():
            st.sidebar.success("¡Datos actualizados!")
            st.rerun()

archivo = obtener_ultimo_excel(DOWNLOAD_PATH)

if archivo:
    try:
        # Carga de datos normal
        df = pd.read_excel(archivo, skiprows=9).dropna(how='all')

        # Detección de columnas
        col_total = 'Total'
        col_estado = 'Estado'
        col_envio = 'Estado de envío'
        col_productos = 'Productos'
        col_tienda = next((c for c in df.columns if 'tienda' in c.lower()), 'Tienda')
        col_cliente = next((c for c in df.columns if 'cliente' in c.lower() or 'nombre' in c.lower()), 'Cliente')
        col_telefono = next((c for c in df.columns if 'tel' in c.lower()), 'Teléfono')
        col_fecha = next((c for c in df.columns if 'fecha' in c.lower()), None)

        # Limpiar Montos
        df[col_total] = pd.to_numeric(df[col_total].astype(str).str.replace('L', '').str.replace(',', '').str.strip(), errors='coerce').fillna(0)

        # --- CORRECCIÓN DE FECHA ---
        if col_fecha:
            # Convertimos a datetime, normalizamos (quita horas) y luego a date
            df['Fecha_Filtro'] = pd.to_datetime(df[col_fecha]).dt.normalize().dt.date
            df = df.dropna(subset=['Fecha_Filtro'])

        # Sidebar Filtros
        st.sidebar.subheader("🔍 Filtros")
        min_d, max_d = df['Fecha_Filtro'].min(), df['Fecha_Filtro'].max()
        f_rango = st.sidebar.slider("Fechas", min_d, max_d, (min_d, max_d))
        
        f_tienda = st.sidebar.multiselect("Tienda", sorted(df[col_tienda].unique()))
        f_estado = st.sidebar.multiselect("Estado", sorted(df[col_estado].unique()))
        
        # Aplicar filtros
        mask = (
            (df['Fecha_Filtro'] >= f_rango[0]) & 
            (df['Fecha_Filtro'] <= f_rango[1]) &
            (df[col_tienda].isin(f_tienda) if f_tienda else True) &
            (df[col_estado].isin(f_estado) if f_estado else True)
        )
        df_f = df.loc[mask]

        # Dashboard Visual
        k1, k2, k3 = st.columns(3)
        k1.metric("📦 Pedidos", len(df_f))
        k2.metric("💰 Total", f"L {df_f[col_total].sum():,.2f}")
        k3.metric("🎫 Promedio", f"L {df_f[col_total].mean():,.2f}" if len(df_f)>0 else "0")

        st.divider()
        
        c1, c2 = st.columns(2)
        with c1:
            # Gráfico de ventas
            v_dia = df_f.groupby('Fecha_Filtro')[col_total].sum().reset_index()
            st.plotly_chart(px.line(v_dia, x='Fecha_Filtro', y=col_total, title="Evolución de Ventas"), use_container_width=True)
        with c2:
            st.plotly_chart(px.pie(df_f, names=col_envio, title="Logística"), use_container_width=True)

        with st.expander("📄 Ver Tabla"):
            cols = ['Fecha_Filtro', col_cliente, col_telefono, col_tienda, col_productos, col_estado, col_total]
            res = df_f[[c for c in cols if c in df_f.columns]].copy()
            st.dataframe(res.sort_values('Fecha_Filtro', ascending=False), use_container_width=True)

    except Exception as e:
        st.error(f"Error procesando tabla: {e}")
else:
    st.info("👋 Haz clic en 'Actualizar Datos' para descargar el Excel.")
