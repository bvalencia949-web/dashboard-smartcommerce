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
            if any(f.endswith(".xlsx") for f in os.listdir(DOWNLOAD_PATH)): return True
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
        # LEER COMO TEXTO (Clave para evitar error de fecha)
        df = pd.read_excel(ultimo_archivo, skiprows=9, dtype=str).dropna(how='all')

        # Nombres de columnas inteligentes
        col_total = 'Total'
        col_estado = 'Estado'
        col_envio = 'Estado de envío'
        col_productos = 'Productos'
        col_tienda = next((c for c in df.columns if 'tienda' in c.lower()), 'Tienda')
        col_cliente = next((c for c in df.columns if 'cliente' in c.lower() or 'nombre' in c.lower()), 'Cliente')
        col_telefono = next((c for c in df.columns if 'tel' in c.lower()), 'Teléfono')
        col_fecha_raw = next((c for c in df.columns if 'fecha' in c.lower()), None)
        
        # 1. Limpieza de Moneda
        df[col_total] = pd.to_numeric(df[col_total].str.replace('L', '', regex=False).str.replace(',', '', regex=False).str.strip(), errors='coerce').fillna(0)
        
        # 2. Procesamiento de Fecha Literal (No UTC)
        if col_fecha_raw:
            # Tomamos solo YYYY-MM-DD del texto original
            df['Fecha_Visual'] = df[col_fecha_raw].str[:10]
            # Convertimos a fecha para los gráficos pero sin ajustar horas
            df['Fecha_DT'] = pd.to_datetime(df['Fecha_Visual'], errors='coerce').dt.date
            df = df.dropna(subset=['Fecha_DT'])

        # Rellenar Nulos
        for c in [col_estado, col_envio, col_productos, col_tienda, col_cliente, col_telefono]:
            if c not in df.columns: df[c] = "N/A"
            df[c] = df[c].fillna('Sin información').astype(str)

        # --- FILTROS ---
        st.sidebar.divider()
        st.sidebar.subheader("🔍 Filtros Dinámicos")

        min_f, max_f = df['Fecha_DT'].min(), df['Fecha_DT'].max()
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
            (df['Fecha_DT'] >= fecha_rango[0]) &
            (df['Fecha_DT'] <= fecha_rango[1])
        ]

        # --- DASHBOARD ---
        k1, k2, k3 = st.columns(3)
        k1.metric("📦 Pedidos", f"{len(df_filtrado)}")
        k2.metric("💰 Venta Total", f"L {df_filtrado[col_total].sum():,.2f}")
        k3.metric("🎫 Ticket Promedio", f"L {df_filtrado[col_total].mean():,.2f}" if not df_filtrado.empty else "L 0.00")

        st.divider()

        c1, c2 = st.columns(2)
        with c1:
            st.write("### 💰 Ingresos por Fecha")
            v_fecha = df_filtrado.groupby('Fecha_DT')[col_total].sum().reset_index()
            st.plotly_chart(px.area(v_fecha, x='Fecha_DT', y=col_total, template="plotly_white", color_discrete_sequence=['#00CC96']), use_container_width=True)

        with c2:
            st.write("### 🚚 Logística de Envío")
            st.plotly_chart(px.pie(df_filtrado, names=col_envio, hole=0.5, color_discrete_sequence=px.colors.qualitative.Pastel), use_container_width=True)

        with st.expander("📄 Ver Tabla de Datos"):
            # Usamos Fecha_Visual para mostrar exactamente lo que dice el Excel
            cols_tab = ['Fecha_Visual', col_cliente, col_telefono, col_tienda, col_productos, col_estado, col_envio, col_total]
            columnas_validas = [c for c in cols_tab if c in df_filtrado.columns]
            tabla_final = df_filtrado[columnas_validas].copy().sort_values('Fecha_Visual', ascending=False)
            tabla_final = tabla_final.rename(columns={'Fecha_Visual': 'Fecha', col_total: 'Monto (L)'})
            st.dataframe(tabla_final, use_container_width=True)

    except Exception as e:
        st.error(f"Error procesando información: {e}")
else:
    st.info("👋 Pulsa 'Actualizar Datos' para descargar el reporte.")
