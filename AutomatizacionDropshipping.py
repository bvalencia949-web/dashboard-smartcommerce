import numpy as np
import time
import os
import glob
import pandas as pd
import streamlit as st
import plotly.express as px
from datetime import datetime, timedelta
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
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    
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
        wait = WebDriverWait(driver, 45)

        # 1. Login
        email_f = wait.until(EC.presence_of_element_located((By.XPATH, "/html/body/app-root/layout/empty-layout/div/div/auth-sign-in/div/div[1]/div[2]/form/div[1]/input")))
        email_f.send_keys("rv309962@gmail.com")
        
        pass_f = driver.find_element(By.XPATH, "/html/body/app-root/layout/empty-layout/div/div/auth-sign-in/div/div[1]/div[2]/form/div[2]/div/input")
        pass_f.send_keys("Rodrigo052002")

        login_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        driver.execute_script("arguments[0].click();", login_btn)

        # 2. Navegación a Pedidos
        time.sleep(8)
        btn_pedidos = wait.until(EC.presence_of_element_located((By.XPATH, "/html/body/app-root/layout/dense-layout/fuse-vertical-navigation/div/div[2]/fuse-vertical-navigation-group-item[3]/fuse-vertical-navigation-basic-item[1]/div/a/div/div/span")))
        driver.execute_script("arguments[0].click();", btn_pedidos)

        # 3. Descarga Excel
        time.sleep(6)
        btn_excel = wait.until(EC.presence_of_element_located((By.XPATH, "/html/body/app-root/layout/dense-layout/div/div[2]/app-orders/div/mat-drawer-container/mat-drawer-content/app-orders-header/div/div[3]/app-excel-export-button/button")))
        driver.execute_script("arguments[0].click();", btn_excel)
        
        timeout = 50
        start = time.time()
        while time.time() - start < timeout:
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

st.sidebar.header("⚙️ Configuración")
if st.sidebar.button("🚀 Actualizar Datos"):
    for f in glob.glob(os.path.join(DOWNLOAD_PATH, "*.xlsx")):
        try: os.remove(f)
        except: pass
    
    with st.spinner("Descargando reporte..."):
        if ejecutar_scraping():
            st.sidebar.success("¡Datos actualizados!")
            st.rerun()

ultimo_archivo = obtener_ultimo_excel(DOWNLOAD_PATH)

if ultimo_archivo:
    try:
        df = pd.read_excel(ultimo_archivo, skiprows=9).dropna(how='all')

        # Nombres de columnas
        col_total = 'Total'
        col_estado = 'Estado'
        col_envio = 'Estado de envío'
        col_productos = 'Productos'
        col_tienda = next((c for c in df.columns if 'tienda' in c.lower() or 'comercio' in c.lower()), 'Tienda')
        col_cliente = next((c for c in df.columns if 'cliente' in c.lower() or 'nombre' in c.lower()), 'Cliente')
        col_telefono = next((c for c in df.columns if 'teléfono' in c.lower() or 'telefono' in c.lower() or 'celular' in c.lower()), 'Teléfono')
        
        if col_total in df.columns:
            df[col_total] = pd.to_numeric(df[col_total].astype(str).str.replace('L', '', regex=False).str.replace(',', '', regex=False).str.strip(), errors='coerce').fillna(0)
        
        # --- AJUSTE DE FECHA LOCAL ---
        col_fecha = next((c for c in df.columns if 'fecha' in c.lower()), None)
        if col_fecha:
            # Restamos 6 horas para ajustar de UTC a hora local de Honduras
            df[col_fecha] = pd.to_datetime(df[col_fecha], errors='coerce') - timedelta(hours=6)
            df[col_fecha] = df[col_fecha].dt.tz_localize(None)
            df = df.dropna(subset=[col_fecha])
            df['Fecha_Filtro'] = df[col_fecha].dt.date

        for c in [col_estado, col_envio, col_productos, col_tienda, col_cliente, col_telefono]:
            if c not in df.columns: df[c] = "N/A"
            df[c] = df[c].fillna('Sin información').astype(str)

        st.sidebar.divider()
        st.sidebar.subheader("🔍 Filtros Dinámicos")

        if col_fecha:
            min_f, max_f = df['Fecha_Filtro'].min(), df['Fecha_Filtro'].max()
            fecha_rango = st.sidebar.slider("Rango de Fechas", min_value=min_f, max_value=max_f, value=(min_f, max_f))
        
        f_tienda = st.sidebar.multiselect("Tienda", options=sorted(df[col_tienda].unique()))
        f_estado = st.sidebar.multiselect("Estado", options=sorted(df[col_estado].unique()))
        f_envio = st.sidebar.multiselect("Estado de envío", options=sorted(df[col_envio].unique()))
        f_prod = st.sidebar.multiselect("Productos", options=sorted(df[col_productos].unique()))

        q_tienda = f_tienda if f_tienda else df[col_tienda].unique()
        q_estado = f_estado if f_estado else df[col_estado].unique()
        q_envio = f_envio if f_envio else df[col_envio].unique()
        q_prod = f_prod if f_prod else df[col_productos].unique()

        df_filtrado = df[
            (df[col_tienda].isin(q_tienda)) &
            (df[col_estado].isin(q_estado)) &
            (df[col_envio].isin(q_envio)) &
            (df[col_productos].isin(q_prod)) &
            (df['Fecha_Filtro'] >= fecha_rango[0]) &
            (df['Fecha_Filtro'] <= fecha_rango[1])
        ]

        # KPIs
        k1, k2, k3 = st.columns(3)
        k1.metric("📦 Pedidos", f"{len(df_filtrado)}")
        k2.metric("💰 Venta Total", f"L {df_filtrado[col_total].sum():,.2f}")
        k3.metric("🎫 Ticket Promedio", f"L {df_filtrado[col_total].mean():,.2f}" if not df_filtrado.empty else "L 0.00")

        st.divider()

        # Gráficos
        c1, c2 = st.columns(2)
        with c1:
            st.write("### 💰 Ingresos por Fecha")
            ventas_f = df_filtrado.groupby('Fecha_Filtro')[col_total].sum().reset_index()
            st.plotly_chart(px.area(ventas_f, x='Fecha_Filtro', y=col_total, template="plotly_white", color_discrete_sequence=['#00CC96']), use_container_width=True)

        with c2:
            st.write("### ⏳ Pedidos Pendientes")
            pend = df_filtrado[df_filtrado[col_estado].str.contains('Pendiente|Confirmar', case=False, na=False)]
            if not pend.empty:
                df_pend = pend.groupby('Fecha_Filtro').size().reset_index(name='Cant')
                st.plotly_chart(px.bar(df_pend, x='Fecha_Filtro', y='Cant', color_discrete_sequence=['#FF4B4B']), use_container_width=True)

        c3, c4 = st.columns(2)
        with c3:
            st.write("### 🚚 Logística de Envío")
            st.plotly_chart(px.pie(df_filtrado, names=col_envio, hole=0.5, color_discrete_sequence=px.colors.qualitative.Pastel), use_container_width=True)

        with c4:
            st.write("### 🏪 Ventas por Tienda")
            ventas_t = df_filtrado.groupby(col_tienda)[col_total].sum().reset_index()
            st.plotly_chart(px.bar(ventas_t, x=col_tienda, y=col_total, color=col_total, color_continuous_scale='GnBu'), use_container_width=True)

        with st.expander("📄 Ver Tabla de Datos"):
            cols_tab = ['Fecha_Filtro', col_cliente, col_telefono, col_tienda, col_productos, col_estado, col_envio, col_total]
            columnas_validas = [c for c in cols_tab if c in df_filtrado.columns]
            tabla_final = df_filtrado[columnas_validas].copy().rename(columns={'Fecha_Filtro': 'Fecha', col_total: 'Monto (L)'})
            st.dataframe(tabla_final.sort_values('Fecha', ascending=False), use_container_width=True)

    except Exception as e:
        st.error(f"Error procesando información: {e}")
else:
    st.info("👋 Pulsa 'Actualizar Datos' para descargar el reporte.")
