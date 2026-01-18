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

# --- CONFIGURACIÓN DE RUTAS ---
# En la nube usamos /tmp (carpeta temporal de Linux), en Windows la carpeta Downloads
DOWNLOAD_PATH = "/tmp" if not os.name == 'nt' else os.path.join(os.path.expanduser("~"), "Downloads")

def ejecutar_scraping():
    chrome_options = Options()
    # Opciones críticas para que Selenium no falle en servidores sin pantalla (Streamlit Cloud)
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--remote-debugging-port=9222")

    # Búsqueda automática del ejecutable de Chrome en Linux
    posibles_rutas = ["/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome"]
    for ruta in posibles_rutas:
        if os.path.exists(ruta):
            chrome_options.binary_location = ruta
            break

    prefs = {
        "download.default_directory": DOWNLOAD_PATH,
        "download.prompt_for_download": False,
        "directory_upgrade": True,
        "safebrowsing.enabled": False
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    # Instalación automática del driver
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    try:
        driver.get("https://smartcommerce.lat/sign-in")
        wait = WebDriverWait(driver, 35)

        # LOGIN
        wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/app-root/layout/empty-layout/div/div/auth-sign-in/div/div[1]/div[2]/form/div[1]/input"))).send_keys("rv309962@gmail.com")
        driver.find_element(By.XPATH, "/html/body/app-root/layout/empty-layout/div/div/auth-sign-in/div/div[1]/div[2]/form/div[2]/div/input").send_keys("Rodrigo052002")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()

        # NAVEGACIÓN A PEDIDOS
        # Usamos XPATH genérico para mayor estabilidad
        wait.until(EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Pedidos')]"))).click()

        # DESCARGA EXCEL
        wait.until(EC.element_to_be_clickable((By.XPATH, "//app-excel-export-button/button"))).click()
        
        # Espera generosa para asegurar que el archivo se guarde en disco
        time.sleep(20) 
        return True
    except Exception as e:
        st.error(f"Error en el scraping: {e}")
        return False
    finally:
        driver.quit()

def obtener_ultimo_excel(ruta):
    archivos = glob.glob(os.path.join(ruta, "*.xlsx"))
    archivos_validos = [f for f in archivos if not os.path.basename(f).startswith("~$")]
    if not archivos_validos: return None
    return max(archivos_validos, key=os.path.getctime)

# --- INTERFAZ DE USUARIO (DASHBOARD) ---
st.set_page_config(page_title="Dashboard BI Dropshipping", layout="wide")
st.title("📊 Business Intelligence: SmartCommerce")

# SIDEBAR: Control de datos
st.sidebar.header("⚙️ Gestión de Datos")
if st.sidebar.button("🚀 Actualizar y Descargar"):
    with st.spinner("Conectando con SmartCommerce..."):
        if ejecutar_scraping():
            st.sidebar.success("¡Datos actualizados!")
            st.rerun()

ultimo_archivo = obtener_ultimo_excel(DOWNLOAD_PATH)

if ultimo_archivo:
    try:
        # Carga de datos
        df = pd.read_excel(ultimo_archivo, skiprows=9, usecols="A:R").dropna(how='all')

        # Limpieza de precios (Eliminar 'L' de Lempiras y comas)
        if 'Total' in df.columns:
            df['Total'] = df['Total'].astype(str).str.replace('L', '', regex=False).str.replace(',', '', regex=False).str.strip()
            df['Total'] = pd.to_numeric(df['Total'], errors='coerce').fillna(0)

        # Procesar Fechas dinámicamente
        col_fecha = next((c for c in df.columns if 'fecha' in c.lower()), None)
        if col_fecha:
            df[col_fecha] = pd.to_datetime(df[col_fecha], errors='coerce')
            df = df.dropna(subset=[col_fecha])
            df['Fecha_Filtro'] = df[col_fecha].dt.date

        # Identificar columnas para filtros
        col_estado = next((c for c in df.columns if 'estado' in c.lower() and 'envío' not in c.lower()), 'Estado')
        col_envio = next((c for c in df.columns if 'envío' in c.lower()), 'Estado Envío')
        col_tienda = next((c for c in df.columns if 'tienda' in c.lower() or 'comercio' in c.lower()), 'Tienda')

        # Rellenar nulos para evitar fallos en multiselect
        for c in [col_estado, col_envio, col_tienda]:
            if c in df.columns: df[c] = df[c].fillna('Sin Info').astype(str)

        # --- PANEL DE FILTROS ---
        st.sidebar.divider()
        st.sidebar.subheader("🔍 Filtros de Tablero")
        
        # Filtro de Fecha (Slider interactivo)
        min_f, max_f = df['Fecha_Filtro'].min(), df['Fecha_Filtro'].max()
        fecha_rango = st.sidebar.slider("Rango de Fechas", min_value=min_f, max_value=max_f, value=(min_f, max_f))
        
        # Multiselectores que inician vacíos
        f_tienda = st.sidebar.multiselect("Tienda", options=sorted(df[col_tienda].unique()))
        f_estado = st.sidebar.multiselect("Estado del Pedido", options=sorted(df[col_estado].unique()))
        f_envio = st.sidebar.multiselect("Estado del Envío", options=sorted(df[col_envio].unique()))

        # LÓGICA: Si el usuario no selecciona nada, mostramos el TOTAL (todos los valores)
        q_tienda = f_tienda if f_tienda else df[col_tienda].unique()
        q_estado = f_estado if f_estado else df[col_estado].unique()
        q_envio = f_envio if f_envio else df[col_envio].unique()

        df_filtrado = df[
            (df[col_tienda].isin(q_tienda)) &
            (df[col_estado].isin(q_estado)) &
            (df[col_envio].isin(q_envio)) &
            (df['Fecha_Filtro'] >= fecha_rango[0]) &
            (df['Fecha_Filtro'] <= fecha_rango[1])
        ]

        # --- VISUALIZACIÓN ---
        # KPIs Principales
        k1, k2, k3 = st.columns(3)
        k1.metric("📦 Total Pedidos", len(df_filtrado))
        k2.metric("💰 Ingresos", f"L {df_filtrado['Total'].sum():,.2f}")
        k3.metric("🎫 Promedio Venta", f"L {df_filtrado['Total'].mean():,.2f}" if len(df_filtrado)>0 else "L 0.00")

        st.divider()

        # Gráficos
        row1_col1, row1_col2 = st.columns(2)
        with row1_col1:
            st.write("### 📈 Tendencia de Ingresos")
            area_data = df_filtrado.groupby('Fecha_Filtro')['Total'].sum().reset_index()
            st.plotly_chart(px.area(area_data, x='Fecha_Filtro', y='Total', template="plotly_white", color_discrete_sequence=['#2E86C1']), use_container_width=True)

        with row1_col2:
            st.write("### 🚚 Estado de Entregas")
            st.plotly_chart(px.pie(df_filtrado, names=col_envio, hole=0.4, color_discrete_sequence=px.colors.qualitative.Safe), use_container_width=True)

        row2_col1, row2_col2 = st.columns(2)
        with row2_col1:
            st.write("### 🏪 Rendimiento por Tienda")
            tienda_data = df_filtrado.groupby(col_tienda)['Total'].sum().reset_index().sort_values('Total', ascending=True)
            st.plotly_chart(px.bar(tienda_data, y=col_tienda, x='Total', orientation='h', color='Total', color_continuous_scale='Blues'), use_container_width=True)

        with row2_col2:
            st.write("### 🚩 Alerta de Pendientes")
            pendientes = df_filtrado[df_filtrado[col_estado].str.contains('Pendiente|Confirmar', case=False, na=False)]
            if not pendientes.empty:
                pend_data = pendientes.groupby('Fecha_Filtro').size().reset_index(name='Cantidad')
                st.plotly_chart(px.bar(pend_data, x='Fecha_Filtro', y='Cantidad', color_discrete_sequence=['#E74C3C']), use_container_width=True)
            else:
                st.info("No hay pedidos pendientes en el rango seleccionado.")

    except Exception as e:
        st.error(f"Error al procesar el archivo: {e}")
else:
    st.warning("👋 ¡Bienvenido! Pulsa el botón 'Actualizar' para descargar los datos desde SmartCommerce.")
