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
# En la nube usamos /tmp, en Windows local usamos Downloads
DOWNLOAD_PATH = "/tmp" if not os.name == 'nt' else os.path.join(os.path.expanduser("~"), "Downloads")

def ejecutar_scraping():
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    
    # Detección de binario para Streamlit Cloud (Linux)
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
        if os.name == 'nt':
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
        else:
            driver = webdriver.Chrome(options=chrome_options)
        
        driver.get("https://smartcommerce.lat/sign-in")
        wait = WebDriverWait(driver, 40)

        # 1. Login (Usando JavaScript para evitar intercepciones)
        email_f = wait.until(EC.presence_of_element_located((By.XPATH, "/html/body/app-root/layout/empty-layout/div/div/auth-sign-in/div/div[1]/div[2]/form/div[1]/input")))
        email_f.send_keys("rv309962@gmail.com")
        
        pass_f = driver.find_element(By.XPATH, "/html/body/app-root/layout/empty-layout/div/div/auth-sign-in/div/div[1]/div[2]/form/div[2]/div/input")
        pass_f.send_keys("Rodrigo052002")

        login_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        driver.execute_script("arguments[0].click();", login_btn)

        # 2. Navegación a Pedidos (Clic Forzado)
        time.sleep(7)
        btn_pedidos = wait.until(EC.presence_of_element_located((By.XPATH, "/html/body/app-root/layout/dense-layout/fuse-vertical-navigation/div/div[2]/fuse-vertical-navigation-group-item[3]/fuse-vertical-navigation-basic-item[1]/div/a/div/div/span")))
        driver.execute_script("arguments[0].click();", btn_pedidos)

        # 3. Descarga Excel (Clic Forzado)
        time.sleep(5)
        btn_excel = wait.until(EC.presence_of_element_located((By.XPATH, "/html/body/app-root/layout/dense-layout/div/div[2]/app-orders/div/mat-drawer-container/mat-drawer-content/app-orders-header/div/div[3]/app-excel-export-button/button")))
        driver.execute_script("arguments[0].click();", btn_excel)
        
        # Espera a que el archivo aparezca en disco
        timeout = 45
        inicio = time.time()
        while time.time() - inicio < timeout:
            if any(f.endswith(".xlsx") for f in os.listdir(DOWNLOAD_PATH)):
                return True
            time.sleep(2)
        return False
    except Exception as e:
        st.error(f"Error en la descarga: {e}")
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

# --- BARRA LATERAL ---
st.sidebar.header("⚙️ Configuración")
if st.sidebar.button("🚀 Actualizar Datos"):
    # Limpiar descargas previas
    for f in glob.glob(os.path.join(DOWNLOAD_PATH, "*.xlsx")):
        try: os.remove(f)
        except: pass
    
    with st.spinner("Descargando reporte..."):
        if ejecutar_scraping():
            st.sidebar.success("¡Datos actualizados!")
            st.rerun()
        else:
            st.sidebar.error("Error al obtener el archivo. Reintente.")

ultimo_archivo = obtener_ultimo_excel(DOWNLOAD_PATH)

if ultimo_archivo:
    try:
        # 1. CARGA INICIAL
        df = pd.read_excel(ultimo_archivo, skiprows=9, usecols="A:R").dropna(how='all')

        # 2. LIMPIEZA DE DATOS
        if 'Total' in df.columns:
            df['Total'] = df['Total'].astype(str).str.replace('L', '', regex=False).str.replace(',', '', regex=False).str.strip()
            df['Total'] = pd.to_numeric(df['Total'], errors='coerce').fillna(0)
        
        col_fecha = next((c for c in df.columns if 'fecha' in c.lower()), None)
        if col_fecha:
            df[col_fecha] = pd.to_datetime(df[col_fecha], errors='coerce')
            df = df.dropna(subset=[col_fecha])
            df['Fecha_Filtro'] = df[col_fecha].dt.date

        col_estado = next((c for c in df.columns if 'estado' in c.lower() and 'envío' not in c.lower()), 'Estado')
        col_envio = next((c for c in df.columns if 'envío' in c.lower()), 'Estado Envío')
        col_tienda = next((c for c in df.columns if 'tienda' in c.lower() or 'comercio' in c.lower()), 'Tienda')

        for c in [col_estado, col_envio, col_tienda]:
            if c in df.columns: df[c] = df[c].fillna('none').astype(str)

        # --- SECCIÓN DE FILTROS EN SIDEBAR ---
        st.sidebar.divider()
        st.sidebar.subheader("🔍 Filtros Dinámicos")

        if col_fecha:
            min_f, max_f = df['Fecha_Filtro'].min(), df['Fecha_Filtro'].max()
            fecha_rango = st.sidebar.slider("Rango de Fechas", min_value=min_f, max_value=max_f, value=(min_f, max_f))
        
        f_tienda = st.sidebar.multiselect("Filtrar por Tienda", options=sorted(df[col_tienda].unique()))
        f_estado = st.sidebar.multiselect("Filtrar por Estado Pedido", options=sorted(df[col_estado].unique()))
        f_envio = st.sidebar.multiselect("Filtrar por Estado Envío", options=sorted(df[col_envio].unique()))

        # Lógica: Si vacío = Todos
        query_tienda = f_tienda if f_tienda else df[col_tienda].unique()
        query_estado = f_estado if f_estado else df[col_estado].unique()
        query_envio = f_envio if f_envio else df[col_envio].unique()

        df_filtrado = df[
            (df[col_tienda].isin(query_tienda)) &
            (df[col_estado].isin(query_estado)) &
            (df[col_envio].isin(query_envio)) &
            (df['Fecha_Filtro'] >= fecha_rango[0]) &
            (df['Fecha_Filtro'] <= fecha_rango[1])
        ]

        # --- DASHBOARD ---
        k1, k2, k3 = st.columns(3)
        k1.metric("📦 Pedidos", f"{len(df_filtrado)}")
        k2.metric("💰 Venta Total", f"L {df_filtrado['Total'].sum():,.2f}")
        k3.metric("🎫 Ticket Promedio", f"L {df_filtrado['Total'].mean():,.2f}" if not df_filtrado.empty else "L 0.00")

        st.divider()

        # Fila 1: Gráficos principales
        c1, c2 = st.columns(2)
        with c1:
            st.write("### 💰 Ingresos por Fecha")
            ventas_f = df_filtrado.groupby('Fecha_Filtro')['Total'].sum().reset_index()
            st.plotly_chart(px.area(ventas_f, x='Fecha_Filtro', y='Total', template="plotly_white", color_discrete_sequence=['#00CC96']), use_container_width=True)

        with c2:
            st.write("### ⏳ Pedidos por Confirmar")
            pend = df_filtrado[df_filtrado[col_estado].str.contains('Pendiente|Confirmar', case=False, na=False)]
            if not pend.empty:
                df_pend = pend.groupby('Fecha_Filtro').size().reset_index(name='Cant')
                st.plotly_chart(px.bar(df_pend, x='Fecha_Filtro', y='Cant', color_discrete_sequence=['#FF4B4B']), use_container_width=True)
            else:
                st.info("No hay pedidos pendientes.")

        # Fila 2: Logística y Tiendas
        c3, c4 = st.columns(2)
        with c3:
            st.write("### 🚚 Logística de Envío")
            st.plotly_chart(px.pie(df_filtrado, names=col_envio, hole=0.5, color_discrete_sequence=px.colors.qualitative.Pastel), use_container_width=True)

        with c4:
            st.write("### 🏪 Ventas por Tienda")
            ventas_t = df_filtrado.groupby(col_tienda)['Total'].sum().reset_index()
            st.plotly_chart(px.bar(ventas_t, x=col_tienda, y='Total', color='Total', color_continuous_scale='GnBu'), use_container_width=True)

        with st.expander("📄 Ver Datos Detallados"):
            st.dataframe(df_filtrado, use_container_width=True)

    except Exception as e:
        st.error(f"Error al procesar la información: {e}")
else:
    st.warning("👋 ¡Bienvenido! Pulsa 'Actualizar Datos' para descargar el reporte de SmartCommerce.")
