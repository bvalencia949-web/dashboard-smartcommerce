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
        email_f = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='email']")))
        email_f.send_keys("rv309962@gmail.com")
        pass_f = driver.find_element(By.XPATH, "//input[@type='password']")
        pass_f.send_keys("Rodrigo052002")
        login_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        driver.execute_script("arguments[0].click();", login_btn)

        # 2. Navegación Directa a Pedidos
        time.sleep(8)
        driver.get("https://smartcommerce.lat/orders")

        # 3. Descarga Excel
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
        st.error(f"Error en el scraping: {e}")
        return False
    finally:
        try: driver.quit()
        except: pass

def obtener_ultimo_excel(ruta):
    archivos = [os.path.join(ruta, f) for f in os.listdir(ruta) if f.endswith(".xlsx") and not f.startswith("~$")]
    return max(archivos, key=os.path.getctime) if archivos else None

# --- INTERFAZ STREAMLIT ---
st.set_page_config(page_title="BI Dashboard Pro", layout="wide")
st.title("📊 Business Intelligence: SmartCommerce")

st.sidebar.header("⚙️ Configuración")
if st.sidebar.button("🚀 Actualizar Datos"):
    for f in glob.glob(os.path.join(DOWNLOAD_PATH, "*.xlsx")):
        try: os.remove(f)
        except: pass
    with st.spinner("Descargando reporte desde la web..."):
        if ejecutar_scraping():
            st.sidebar.success("¡Datos actualizados!")
            st.rerun()

ultimo_archivo = obtener_ultimo_excel(DOWNLOAD_PATH)

if ultimo_archivo:
    try:
        # --- CARGA SEGURA: LEER TODO COMO TEXTO ---
        df = pd.read_excel(ultimo_archivo, skiprows=9, dtype=str).dropna(how='all')

        # Detección de columnas
        col_total = 'Total'
        col_estado = 'Estado'
        col_envio = 'Estado de envío'
        col_productos = 'Productos'
        col_tienda = next((c for c in df.columns if 'tienda' in c.lower()), 'Tienda')
        col_cliente = next((c for c in df.columns if 'cliente' in c.lower() or 'nombre' in c.lower()), 'Cliente')
        col_telefono = next((c for c in df.columns if 'tel' in c.lower()), 'Teléfono')
        col_fecha_raw = next((c for c in df.columns if 'fecha' in c.lower()), None)
        
        # 1. Limpieza de Moneda (Convertir texto a número)
        df[col_total] = pd.to_numeric(df[col_total].str.replace('L', '', regex=False).str.replace(',', '', regex=False).str.strip(), errors='coerce').fillna(0)
        
        # 2. Procesamiento de Fecha Literal (Solución al error del día 19)
        if col_fecha_raw:
            # Tomamos exactamente los primeros 10 caracteres del texto original (YYYY-MM-DD)
            df['Fecha_Texto'] = df[col_fecha_raw].str[:10]
            # Creamos la versión de fecha para gráficos y filtros (sin ajustar zona horaria)
            df['Fecha_DT'] = pd.to_datetime(df['Fecha_Texto'], errors='coerce').dt.date
            df = df.dropna(subset=['Fecha_DT'])

        # Rellenar nulos en otras columnas
        for c in [col_estado, col_envio, col_productos, col_tienda, col_cliente, col_telefono]:
            if c not in df.columns: df[c] = "N/A"
            df[c] = df[c].fillna('N/A').astype(str)

        # --- FILTROS ---
        st.sidebar.divider()
        st.sidebar.subheader("🔍 Filtros Dinámicos")

        min_f, max_f = df['Fecha_DT'].min(), df['Fecha_DT'].max()
        f_rango = st.sidebar.slider("Periodo", min_f, max_f, (min_f, max_f))
        
        f_tienda = st.sidebar.multiselect("Tienda", sorted(df[col_tienda].unique()))
        f_estado = st.sidebar.multiselect("Estado", sorted(df[col_estado].unique()))
        f_envio = st.sidebar.multiselect("Envío", sorted(df[col_envio].unique()))
        f_prod = st.sidebar.multiselect("Productos", sorted(df[col_productos].unique()))

        # Lógica de filtrado
        mask = (
            (df['Fecha_DT'] >= f_rango[0]) & (df['Fecha_DT'] <= f_rango[1]) &
            (df[col_tienda].isin(f_tienda if f_tienda else df[col_tienda].unique())) &
            (df[col_estado].isin(f_estado if f_estado else df[col_estado].unique())) &
            (df[col_envio].isin(f_envio if f_envio else df[col_envio].unique())) &
            (df[col_productos].isin(f_prod if f_prod else df[col_productos].unique()))
        )
        df_f = df.loc[mask]

        # --- DASHBOARD ---
        k1, k2, k3 = st.columns(3)
        k1.metric("📦 Pedidos", len(df_f))
        k2.metric("💰 Total", f"L {df_f[col_total].sum():,.2f}")
        k3.metric("🎫 Ticket Prom.", f"L {df_f[col_total].mean():,.2f}" if not df_f.empty else "0")

        st.divider()

        # Gráficos
        c1, c2 = st.columns(2)
        with c1:
            st.write("### 💰 Ventas Diarias")
            v_diarias = df_f.groupby('Fecha_DT')[col_total].sum().reset_index()
            st.plotly_chart(px.area(v_diarias, x='Fecha_DT', y=col_total, template="plotly_white", color_discrete_sequence=['#00CC96']), use_container_width=True)

        with c2:
            st.write("### 🚚 Estado de Envíos")
            st.plotly_chart(px.pie(df_f, names=col_envio, hole=0.5), use_container_width=True)

        # --- TABLA DE DATOS FINAL ---
        with st.expander("📄 Ver Tabla de Datos Completa"):
            # Usamos Fecha_Texto para que no haya cambios de zona horaria al mostrar
            cols_final = ['Fecha_Texto', col_cliente, col_telefono, col_tienda, col_productos, col_estado, col_envio, col_total]
            v_cols = [c for c in cols_final if c in df_f.columns]
            
            res_tabla = df_f[v_cols].copy().sort_values('Fecha_Texto', ascending=False)
            res_tabla = res_tabla.rename(columns={'Fecha_Texto': 'Fecha', col_total: 'Monto (L)'})
            
            st.dataframe(res_tabla, use_container_width=True)

    except Exception as e:
        st.error(f"Error procesando los datos: {e}")
else:
    st.info("👋 Por favor, pulsa 'Actualizar Datos' para comenzar.")
