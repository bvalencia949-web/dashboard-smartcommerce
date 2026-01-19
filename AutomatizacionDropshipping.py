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

        # Definición de columnas
        col_total = 'Total'
        col_estado = 'Estado'
        col_envio = 'Estado de envío'
        col_productos = 'Productos'
        col_tienda = next((c for c in df.columns if 'tienda' in c.lower()), 'Tienda')
        col_cliente = next((c for c in df.columns if 'cliente' in c.lower() or 'nombre' in c.lower()), 'Cliente')
        col_telefono = next((c for c in df.columns if 'tel' in c.lower()), 'Teléfono')
        col_fecha = next((c for c in df.columns if 'fecha' in c.lower()), None)
        
        # Limpieza de Total
        if col_total in df.columns:
            df[col_total] = pd.to_numeric(df[col_total].astype(str).str.replace('L', '').str.replace(',', '').str.strip(), errors='coerce').fillna(0)
        
        # --- CORRECCIÓN DE FECHA (Sin transformación UTC) ---
        if col_fecha:
            # Convertimos a datetime y nos quedamos solo con el objeto DATE (sin horas)
            df[col_fecha] = pd.to_datetime(df[col_fecha]).dt.date
            df = df.dropna(subset=[col_fecha])

        # --- FILTROS ---
        st.sidebar.subheader("🔍 Filtros")
        min_f, max_f = df[col_fecha].min(), df[col_fecha].max()
        f_rango = st.sidebar.slider("Fecha", min_f, max_f, (min_f, max_f))
        
        df_filtrado = df[
            (df[col_fecha] >= f_rango[0]) & 
            (df[col_fecha] <= f_rango[1])
        ]

        # KPIs
        k1, k2, k3 = st.columns(3)
        k1.metric("📦 Pedidos", len(df_filtrado))
        k2.metric("💰 Total", f"L {df_filtrado[col_total].sum():,.2f}")
        k3.metric("🎫 Ticket Promedio", f"L {df_filtrado[col_total].mean():,.2f}" if not df_filtrado.empty else "0")

        st.divider()

        # Gráficos y Tabla
        st.plotly_chart(px.line(df_filtrado.groupby(col_fecha)[col_total].sum().reset_index(), x=col_fecha, y=col_total), use_container_width=True)

        with st.expander("📄 Ver Tabla"):
            st.dataframe(df_filtrado[[col_fecha, col_cliente, col_telefono, col_tienda, col_total]].sort_values(col_fecha, ascending=False), use_container_width=True)

    except Exception as e:
        st.error(f"Error procesando: {e}")
else:
    st.info("👋 Pulsa 'Actualizar Datos'.")
