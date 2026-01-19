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
DOWNLOAD_PATH = "/tmp" if not os.name == 'nt' else os.path.join(os.path.expanduser("~"), "Downloads")

def ejecutar_scraping():
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    
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

        # 1. Login (XPaths Originales)
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

        # Definición de Columnas
        col_total = 'Total'
        col_estado = 'Estado'
        col_envio = 'Estado de envío'
        col_productos = 'Productos'
        col_tienda = next((c for c in df.columns if 'tienda' in c.lower()), 'Tienda')
        col_cliente = next((c for c in df.columns if 'cliente' in c.lower() or 'nombre' in c.lower()), 'Cliente')
        col_telefono = next((c for c in df.columns if 'tel' in c.lower()), 'Teléfono')
        col_fecha = next((c for c in df.columns if 'fecha' in c.lower()), None)
        
        # Limpieza de Total
        df[col_total] = pd.to_numeric(df[col_total].astype(str).str.replace('L', '').str.replace(',', '').str.strip(), errors='coerce').fillna(0)
        
        # Normalizar textos para filtros
        for c in [col_estado, col_envio, col_productos, col_tienda]:
            df[c] = df[c].fillna('Sin información').astype(str)

        # --- FILTROS EN SIDEBAR ---
        st.sidebar.subheader("🔍 Filtros Avanzados")
        
        f_tienda = st.sidebar.multiselect("Tienda", sorted(df[col_tienda].unique()))
        f_estado = st.sidebar.multiselect("Estado de Pedido", sorted(df[col_estado].unique()))
        f_envio = st.sidebar.multiselect("Estado de Envío", sorted(df[col_envio].unique()))
        f_prod = st.sidebar.multiselect("Producto", sorted(df[col_productos].unique()))

        # Lógica de Filtrado
        df_f = df.copy()
        if f_tienda: df_f = df_f[df_f[col_tienda].isin(f_tienda)]
        if f_estado: df_f = df_f[df_f[col_estado].isin(f_estado)]
        if f_envio:  df_f = df_f[df_f[col_envio].isin(f_envio)]
        if f_prod:   df_f = df_f[df_f[col_productos].isin(f_prod)]

        # --- KPIs ---
        k1, k2, k3 = st.columns(3)
        k1.metric("📦 Pedidos", len(df_f))
        k2.metric("💰 Venta Total", f"L {df_f[col_total].sum():,.2f}")
        k3.metric("🎫 Ticket Promedio", f"L {df_f[col_total].mean():,.2f}" if not df_f.empty else "L 0.00")

        st.divider()

        # --- GRÁFICOS ---
        c1, c2 = st.columns(2)
        with c1:
            st.write("### 💰 Ingresos")
            if col_fecha:
                df_f[col_fecha] = pd.to_datetime(df_f[col_fecha], errors='coerce')
                ventas_f = df_f.groupby(df_f[col_fecha].dt.date)[col_total].sum().reset_index()
                st.plotly_chart(px.area(ventas_f, x=col_fecha, y=col_total, color_discrete_sequence=['#00CC96']), use_container_width=True)

        with c2:
            st.write("### 🚚 Logística")
            st.plotly_chart(px.pie(df_f, names=col_envio, hole=0.4), use_container_width=True)

        # --- TABLA DE DATOS ---
        with st.expander("📄 Ver Detalle de Pedidos"):
            cols_final = [c for c in [col_fecha, col_cliente, col_telefono, col_tienda, col_productos, col_estado, col_envio, col_total] if c in df_f.columns]
            st.dataframe(df_f[cols_final].sort_values(by=col_fecha, ascending=False) if col_fecha in df_f.columns else df_f, use_container_width=True)

    except Exception as e:
        st.error(f"Error procesando los datos: {e}")
else:
    st.info("👋 Pulsa **'Actualizar Datos'** para comenzar.")
