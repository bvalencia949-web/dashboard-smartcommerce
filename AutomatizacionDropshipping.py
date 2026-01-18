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
# Si está en la nube usa /tmp, si es Windows usa Downloads
DOWNLOAD_PATH = "/tmp" if not os.name == 'nt' else os.path.join(os.path.expanduser("~"), "Downloads")

def ejecutar_scraping():
    chrome_options = Options()
    # Opciones obligatorias para que funcione en el servidor de Streamlit
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    
    # Intentar detectar la ubicación del binario en la nube
    if os.path.exists("/usr/bin/chromium"):
        chrome_options.binary_location = "/usr/bin/chromium"
    elif os.path.exists("/usr/bin/chromium-browser"):
        chrome_options.binary_location = "/usr/bin/chromium-browser"

    prefs = {
        "download.default_directory": DOWNLOAD_PATH,
        "download.prompt_for_download": False,
        "directory_upgrade": True,
        "safebrowsing.enabled": False
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    # Instalación automática del driver compatible
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    try:
        driver.get("https://smartcommerce.lat/sign-in")
        wait = WebDriverWait(driver, 30)

        # LOGIN
        email_field = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/app-root/layout/empty-layout/div/div/auth-sign-in/div/div[1]/div[2]/form/div[1]/input")))
        email_field.send_keys("rv309962@gmail.com")

        pass_field = driver.find_element(By.XPATH, "/html/body/app-root/layout/empty-layout/div/div/auth-sign-in/div/div[1]/div[2]/form/div[2]/div/input")
        pass_field.send_keys("Rodrigo052002")

        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()

        # NAVEGACIÓN A PEDIDOS
        btn_pedidos = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Pedidos')] | /html/body/app-root/layout/dense-layout/fuse-vertical-navigation/div/div[2]/fuse-vertical-navigation-group-item[3]/fuse-vertical-navigation-basic-item[1]/div/a/div/div/span")))
        btn_pedidos.click()

        # DESCARGA EXCEL
        btn_excel = wait.until(EC.element_to_be_clickable((By.XPATH, "//app-excel-export-button/button")))
        btn_excel.click()
        
        # Tiempo de espera para que se complete la descarga
        time.sleep(15) 
        return True
    except Exception as e:
        st.error(f"Error en el proceso de descarga: {e}")
        return False
    finally:
        driver.quit()

def obtener_ultimo_excel(ruta):
    archivos = glob.glob(os.path.join(ruta, "*.xlsx"))
    archivos_validos = [f for f in archivos if not os.path.basename(f).startswith("~$")]
    if not archivos_validos: return None
    return max(archivos_validos, key=os.path.getctime)

# --- INTERFAZ STREAMLIT ---
st.set_page_config(page_title="Dashboard BI Dropshipping", layout="wide")
st.title("📊 Business Intelligence: SmartCommerce")

st.sidebar.header("⚙️ Configuración")
if st.sidebar.button("🚀 Actualizar y Descargar Datos"):
    with st.spinner("Ejecutando scraping en segundo plano..."):
        if ejecutar_scraping():
            st.sidebar.success("¡Datos descargados con éxito!")
            st.rerun()

ultimo_archivo = obtener_ultimo_excel(DOWNLOAD_PATH)

if ultimo_archivo:
    try:
        # Cargar datos (saltando encabezados innecesarios)
        df = pd.read_excel(ultimo_archivo, skiprows=9, usecols="A:R").dropna(how='all')

        # Limpieza de columna Total
        if 'Total' in df.columns:
            df['Total'] = df['Total'].astype(str).str.replace('L', '', regex=False).str.replace(',', '', regex=False).str.strip()
            df['Total'] = pd.to_numeric(df['Total'], errors='coerce').fillna(0)

        # Procesar Fechas
        col_fecha = next((c for c in df.columns if 'fecha' in c.lower()), None)
        if col_fecha:
            df[col_fecha] = pd.to_datetime(df[col_fecha], errors='coerce')
            df = df.dropna(subset=[col_fecha])
            df['Fecha_Filtro'] = df[col_fecha].dt.date

        # Columnas para filtros
        col_estado = next((c for c in df.columns if 'estado' in c.lower() and 'envío' not in c.lower()), 'Estado')
        col_envio = next((c for c in df.columns if 'envío' in c.lower()), 'Estado Envío')
        col_tienda = next((c for c in df.columns if 'tienda' in c.lower() or 'comercio' in c.lower()), 'Tienda')

        for c in [col_estado, col_envio, col_tienda]:
            if c in df.columns: df[c] = df[c].fillna('none').astype(str)

        # --- SIDEBAR FILTROS ---
        st.sidebar.divider()
        st.sidebar.subheader("🔍 Filtros de Visualización")
        
        min_f, max_f = df['Fecha_Filtro'].min(), df['Fecha_Filtro'].max()
        fecha_rango = st.sidebar.slider("Seleccionar Rango de Fecha", min_value=min_f, max_value=max_f, value=(min_f, max_f))
        
        f_tienda = st.sidebar.multiselect("Filtrar por Tienda", options=sorted(df[col_tienda].unique()))
        f_estado = st.sidebar.multiselect("Filtrar por Estado Pedido", options=sorted(df[col_estado].unique()))
        f_envio = st.sidebar.multiselect("Filtrar por Estado Envío", options=sorted(df[col_envio].unique()))

        # Lógica: Si no hay selección, mostrar todos (total general)
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

        # --- DASHBOARD ---
        m1, m2, m3 = st.columns(3)
        m1.metric("📦 Pedidos", len(df_filtrado))
        m2.metric("💰 Venta Total", f"L {df_filtrado['Total'].sum():,.2f}")
        m3.metric("🎫 Ticket Promedio", f"L {df_filtrado['Total'].mean():,.2f}" if not df_filtrado.empty else "L 0.00")

        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            st.write("### 📈 Ingresos Totales por Fecha")
            fig_ingresos = px.area(df_filtrado.groupby('Fecha_Filtro')['Total'].sum().reset_index(), x='Fecha_Filtro', y='Total', template="plotly_white", color_discrete_sequence=['#00CC96'])
            st.plotly_chart(fig_ingresos, use_container_width=True)
        with col2:
            st.write("### ⏳ Pendientes de Confirmación")
            pend = df_filtrado[df_filtrado[col_estado].str.contains('Pendiente|Confirmar', case=False, na=False)]
            if not pend.empty:
                df_pend = pend.groupby('Fecha_Filtro').size().reset_index(name='Cant')
                st.plotly_chart(px.bar(df_pend, x='Fecha_Filtro', y='Cant', color_discrete_sequence=['#FF4B4B']), use_container_width=True)
            else:
                st.info("No hay pedidos pendientes.")

        col3, col4 = st.columns(2)
        with col3:
            st.write("### 🚚 Logística de Envío")
            st.plotly_chart(px.pie(df_filtrado, names=col_envio, hole=0.5, color_discrete_sequence=px.colors.qualitative.Pastel), use_container_width=True)
        with col4:
            st.write("### 🏪 Ventas por Tienda")
            ventas_t = df_filtrado.groupby(col_tienda)['Total'].sum().reset_index()
            st.plotly_chart(px.bar(ventas_t, x=col_tienda, y='Total', color='Total', color_continuous_scale='GnBu'), use_container_width=True)

    except Exception as e:
        st.error(f"Error al procesar los datos: {e}")
else:
    st.warning("⚠️ No se ha encontrado información. Haz clic en 'Actualizar y Descargar Datos' para iniciar.")
