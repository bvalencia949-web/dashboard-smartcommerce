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
        # --- CORRECCIÓN CLAVE: LEER TODO COMO TEXTO PRIMERO ---
        # Usamos dtype=str para que pandas no intente adivinar fechas ni números
        df_raw = pd.read_excel(ultimo_archivo, skiprows=9, dtype=str).dropna(how='all')

        # Definición de columnas
        col_total = 'Total'
        col_estado = 'Estado'
        col_envio = 'Estado de envío'
        col_productos = 'Productos'
        col_tienda = next((c for c in df_raw.columns if 'tienda' in c.lower() or 'comercio' in c.lower()), 'Tienda')
        col_cliente = next((c for c in df_raw.columns if 'cliente' in c.lower() or 'nombre' in c.lower()), 'Cliente')
        col_telefono = next((c for c in df_raw.columns if 'teléfono' in c.lower() or 'telefono' in c.lower() or 'celular' in c.lower()), 'Teléfono')
        col_fecha_orig = next((c for c in df_raw.columns if 'fecha' in c.lower()), None)

        # 1. Procesar Total (Convertir el texto a número para cálculos)
        if col_total in df_raw.columns:
            df_raw[col_total] = pd.to_numeric(df_raw[col_total].str.replace('L', '', regex=False).str.replace(',', '', regex=False).str.strip(), errors='coerce').fillna(0)
        
        # 2. Procesar Fecha (La mantenemos como texto para la tabla, pero creamos una versión para filtros)
        if col_fecha_orig:
            # Creamos una columna interna de fecha real SOLO para los gráficos y el slider
            # Pero la limpiamos de cualquier zona horaria
            df_raw['Fecha_DT'] = pd.to_datetime(df_raw[col_fecha_orig], errors='coerce').dt.normalize()
            # La columna visual 'Fecha_Texto' será el texto original del Excel cortado (solo YYYY-MM-DD)
            df_raw['Fecha_Texto'] = df_raw[col_fecha_orig].str[:10]
        
        # Limpiar el resto de columnas
        for c in [col_estado, col_envio, col_productos, col_tienda, col_cliente, col_telefono]:
            if c not in df_raw.columns: df_raw[c] = "N/A"
            df_raw[c] = df_raw[c].fillna('Sin información').astype(str)

        # --- FILTROS DINÁMICOS ---
        st.sidebar.divider()
        st.sidebar.subheader("🔍 Filtros Dinámicos")

        if 'Fecha_DT' in df_raw.columns:
            min_f, max_f = df_raw['Fecha_DT'].min().date(), df_raw['Fecha_DT'].max().date()
            fecha_rango = st.sidebar.slider("Rango de Fechas", min_value=min_f, max_value=max_f, value=(min_f, max_f))
        
        f_tienda = st.sidebar.multiselect("Tienda", options=sorted(df_raw[col_tienda].unique()))
        f_estado = st.sidebar.multiselect("Estado", options=sorted(df_raw[col_estado].unique()))
        f_envio = st.sidebar.multiselect("Estado de envío", options=sorted(df_raw[col_envio].unique()))
        f_prod = st.sidebar.multiselect("Productos", options=sorted(df_raw[col_productos].unique()))

        q_tienda = f_tienda if f_tienda else df_raw[col_tienda].unique()
        q_estado = f_estado if f_estado else df_raw[col_estado].unique()
        q_envio = f_envio if f_envio else df_raw[col_envio].unique()
        q_prod = f_prod if f_prod else df_raw[col_productos].unique()

        # Aplicar filtros
        df_filtrado = df_raw[
            (df_raw[col_tienda].isin(q_tienda)) &
            (df_raw[col_estado].isin(q_estado)) &
            (df_raw[col_envio].isin(q_envio)) &
            (df_raw[col_productos].isin(q_prod)) &
            (df_raw['Fecha_DT'].dt.date >= fecha_rango[0]) &
            (df_raw['Fecha_DT'].dt.date <= fecha_rango[1])
        ]

        # KPIs
        k1, k2, k3 = st.columns(3)
        k1.metric("📦 Pedidos", f"{len(df_filtrado)}")
        k2.metric("💰 Venta Total", f"L {df_filtrado[col_total].sum():,.2f}")
        k3.metric("🎫 Ticket Promedio", f"L {df_filtrado[col_total].mean():,.2f}" if not df_filtrado.empty else "L 0.00")

        st.divider()

        # Gráficos (Usan Fecha_DT para el orden)
        c1, c2 = st.columns(2)
        with c1:
            st.write("### 💰 Ingresos por Fecha")
            ventas_f = df_filtrado.groupby('Fecha_DT')[col_total].sum().reset_index()
            st.plotly_chart(px.area(ventas_f, x='Fecha_DT', y=col_total, template="plotly_white", color_discrete_sequence=['#00CC96']), use_container_width=True)

        with c2:
            st.write("### ⏳ Pedidos Pendientes")
            pend = df_filtrado[df_filtrado[col_estado].str.contains('Pendiente|Confirmar', case=False, na=False)]
            if not pend.empty:
                df_pend = pend.groupby('Fecha_DT').size().reset_index(name='Cant')
                st.plotly_chart(px.bar(df_pend, x='Fecha_DT', y='Cant', color_discrete_sequence=['#FF4B4B']), use_container_width=True)

        # TABLA FINAL
        with st.expander("📄 Ver Tabla de Datos"):
            # Usamos Fecha_Texto que es el valor literal del Excel
            cols_tab = ['Fecha_Texto', col_cliente, col_telefono, col_tienda, col_productos, col_estado, col_envio, col_total]
            columnas_validas = [c for c in cols_tab if c in df_filtrado.columns]
            
            tabla_final = df_filtrado[columnas_validas].copy().sort_values('Fecha_Texto', ascending=False)
            tabla_final = tabla_final.rename(columns={'Fecha_Texto': 'Fecha', col_total: 'Monto (L)'})
            st.dataframe(tabla_final, use_container_width=True)

    except Exception as e:
        st.error(f"Error procesando información: {e}")
else:
    st.info("👋 Pulsa 'Actualizar Datos' para descargar el reporte.")
