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

def ejecutar_scraping():
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    
    # Mantenemos bloqueo de imágenes para velocidad
    chrome_options.add_argument("--blink-settings=imagesEnabled=false")
    
    if os.name != 'nt':
        chrome_options.binary_location = "/usr/bin/chromium"

    prefs = {
        "download.default_directory": DOWNLOAD_PATH,
        "download.prompt_for_download": False,
        "directory_upgrade": True,
        "safebrowsing.enabled": False
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    try:
        service = Service(ChromeDriverManager().install()) if os.name == 'nt' else None
        driver = webdriver.Chrome(service=service, options=chrome_options)
        wait = WebDriverWait(driver, 40) # Espera generosa para evitar el Stacktrace

        driver.get("https://smartcommerce.lat/sign-in")

        # 1. Login - Usamos una espera más robusta
        email_f = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@type='email']")))
        email_f.clear()
        email_f.send_keys("rv309962@gmail.com")
        
        pass_f = driver.find_element(By.XPATH, "//input[@type='password']")
        pass_f.clear()
        pass_f.send_keys("Rodrigo052002")

        # Clic forzado por JavaScript para evitar errores de intercepción
        login_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        driver.execute_script("arguments[0].click();", login_btn)

        # 2. Transición a Pedidos
        # Esperamos un poco a que la sesión se asiente antes de saltar
        time.sleep(10) 
        driver.get("https://smartcommerce.lat/orders")

        # 3. Descarga Excel
        # Buscamos el botón de Excel con un selector más flexible
        btn_excel = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Excel')] | //app-excel-export-button//button")))
        time.sleep(3) # Pausa de seguridad para que el botón se active realmente
        driver.execute_script("arguments[0].click();", btn_excel)
        
        # 4. Monitoreo de archivo
        timeout = 50
        start = time.time()
        while time.time() - start < timeout:
            if any(f.endswith(".xlsx") for f in os.listdir(DOWNLOAD_PATH)):
                time.sleep(2) # Tiempo para que termine de escribir el archivo
                return True
            time.sleep(2)
        return False
    except Exception as e:
        st.error(f"Error en la descarga: {str(e)[:150]}") # Recortamos el error para leerlo mejor
        return False
    finally:
        if driver:
            driver.quit()

def obtener_ultimo_excel(ruta):
    archivos = glob.glob(os.path.join(ruta, "*.xlsx"))
    archivos_validos = [f for f in archivos if not os.path.basename(f).startswith("~$")]
    if not archivos_validos: return None
    return max(archivos_validos, key=os.path.getctime)

# --- INTERFAZ STREAMLIT ---
st.set_page_config(page_title="BI Dashboard Pro", layout="wide")
st.title("📊 Business Intelligence: SmartCommerce")

st.sidebar.header("⚙️ Configuración")
if st.sidebar.button("🚀 Actualizar Datos"):
    for f in glob.glob(os.path.join(DOWNLOAD_PATH, "*.xlsx")):
        try: os.remove(f)
        except: pass
    
    with st.spinner("Sincronizando con el portal..."):
        if ejecutar_scraping():
            st.sidebar.success("¡Datos actualizados!")
            st.rerun()

ultimo_archivo = obtener_ultimo_excel(DOWNLOAD_PATH)

if ultimo_archivo:
    try:
        df = pd.read_excel(ultimo_archivo, skiprows=9).dropna(how='all')

        col_total = 'Total'
        col_estado = 'Estado'
        col_envio = 'Estado Envío'
        col_productos = 'Productos'
        col_tienda = next((c for c in df.columns if 'tienda' in c.lower() or 'comercio' in c.lower()), 'Tienda')
        col_cliente = next((c for c in df.columns if 'cliente' in c.lower() or 'nombre' in c.lower()), 'Cliente')
        col_telefono = next((c for c in df.columns if 'teléfono' in c.lower() or 'telefono' in c.lower() or 'celular' in c.lower()), 'Teléfono')
        
        if col_total in df.columns:
            df[col_total] = pd.to_numeric(df[col_total].astype(str).str.replace('L', '', regex=False).str.replace(',', '', regex=False).str.strip(), errors='coerce').fillna(0)
        
        # Aplicación de descuento
        if col_envio in df.columns:
            df.loc[df[col_envio].astype(str).str.contains('Devuelto', case=False, na=False), col_total] = -125.2
        
        col_fecha = next((c for c in df.columns if 'fecha' in c.lower()), None)
        if col_fecha:
            df[col_fecha] = pd.to_datetime(df[col_fecha], errors='coerce').dt.tz_localize(None)
            df = df.dropna(subset=[col_fecha])
            df['Fecha_Filtro'] = df[col_fecha].dt.date

        for c in [col_estado, col_envio, col_productos, col_tienda, col_cliente, col_telefono]:
            if c not in df.columns: df[c] = "N/A"
            df[c] = df[c].fillna('Sin información').astype(str)

        # Filtros
        st.sidebar.divider()
        st.sidebar.subheader("🔍 Filtros")
        if col_fecha:
            min_f, max_f = df['Fecha_Filtro'].min(), df['Fecha_Filtro'].max()
            fecha_rango = st.sidebar.slider("Rango de Fechas", min_value=min_f, max_value=max_f, value=(min_f, max_f))
        
        f_tienda = st.sidebar.multiselect("Tienda", options=sorted(df[col_tienda].unique()))
        f_estado = st.sidebar.multiselect("Estado", options=sorted(df[col_estado].unique()))
        f_envio = st.sidebar.multiselect("Estado Envío", options=sorted(df[col_envio].unique()))
        f_prod = st.sidebar.multiselect("Productos", options=sorted(df[col_productos].unique()))

        df_filtrado = df[
            (df[col_tienda].isin(f_tienda if f_tienda else df[col_tienda].unique())) &
            (df[col_estado].isin(f_estado if f_estado else df[col_estado].unique())) &
            (df[col_envio].isin(f_envio if f_envio else df[col_envio].unique())) &
            (df[col_productos].isin(f_prod if f_prod else df[col_productos].unique())) &
            (df['Fecha_Filtro'] >= fecha_rango[0]) &
            (df['Fecha_Filtro'] <= fecha_rango[1])
        ]

        # Dashboard Visual
        k1, k2, k3 = st.columns(3)
        k1.metric("📦 Pedidos", f"{len(df_filtrado)}")
        k2.metric("💰 Venta Total", f"L {df_filtrado[col_total].sum():,.2f}")
        k3.metric("🎫 Ticket Promedio", f"L {df_filtrado[col_total].mean():,.2f}" if not df_filtrado.empty else "L 0.00")

        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            ventas_f = df_filtrado.groupby('Fecha_Filtro')[col_total].sum().reset_index()
            st.plotly_chart(px.area(ventas_f, x='Fecha_Filtro', y=col_total, title="Ingresos", template="plotly_white"), use_container_width=True)
        with c2:
            st.plotly_chart(px.pie(df_filtrado, names=col_envio, title="Logística", hole=0.5), use_container_width=True)

        with st.expander("📄 Ver Tabla de Datos"):
            st.dataframe(df_filtrado, use_container_width=True)

    except Exception as e:
        st.error(f"Error procesando información: {e}")
else:
    st.info("👋 Pulsa 'Actualizar Datos' para descargar el reporte.")
