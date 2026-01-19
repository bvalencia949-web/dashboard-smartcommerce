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

CUENTAS = [
    {"nombre": "Honduras", "user": "rv309962@gmail.com", "pass": "Rodrigo052002"},
    {"nombre": "El Salvador", "user": "overcloudselsalvador@gmail.com", "pass": "Rodrigo052002"}
]

def descargar_reporte(usuario, clave, nombre_archivo):
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    prefs = {"download.default_directory": DOWNLOAD_PATH, "download.prompt_for_download": False}
    chrome_options.add_experimental_option("prefs", prefs)
    
    driver = None
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()) if os.name == 'nt' else None, options=chrome_options)
        driver.get("https://smartcommerce.lat/sign-in")
        wait = WebDriverWait(driver, 45)

        # Login
        wait.until(EC.presence_of_element_located((By.XPATH, "/html/body/app-root/layout/empty-layout/div/div/auth-sign-in/div/div[1]/div[2]/form/div[1]/input"))).send_keys(usuario)
        driver.find_element(By.XPATH, "/html/body/app-root/layout/empty-layout/div/div/auth-sign-in/div/div[1]/div[2]/form/div[2]/div/input").send_keys(clave)
        driver.execute_script("arguments[0].click();", driver.find_element(By.CSS_SELECTOR, "button[type='submit']"))

        # Navegación
        time.sleep(8)
        btn_pedidos = wait.until(EC.presence_of_element_located((By.XPATH, "/html/body/app-root/layout/dense-layout/fuse-vertical-navigation/div/div[2]/fuse-vertical-navigation-group-item[3]/fuse-vertical-navigation-basic-item[1]/div/a/div/div/span")))
        driver.execute_script("arguments[0].click();", btn_pedidos)

        # Descarga
        time.sleep(6)
        btn_excel = wait.until(EC.presence_of_element_located((By.XPATH, "/html/body/app-root/layout/dense-layout/div/div[2]/app-orders/div/mat-drawer-container/mat-drawer-content/app-orders-header/div/div[3]/app-excel-export-button/button")))
        driver.execute_script("arguments[0].click();", btn_excel)
        
        timeout = 55
        start = time.time()
        while time.time() - start < timeout:
            archivos = [f for f in os.listdir(DOWNLOAD_PATH) if f.endswith(".xlsx") and not f.startswith("reporte_")]
            if archivos:
                reciente = max([os.path.join(DOWNLOAD_PATH, f) for f in archivos], key=os.path.getctime)
                nuevo_nombre = os.path.join(DOWNLOAD_PATH, f"reporte_{nombre_archivo}.xlsx")
                if os.path.exists(nuevo_nombre): os.remove(nuevo_nombre)
                os.rename(reciente, nuevo_nombre)
                return True
            time.sleep(2)
        return False
    except Exception as e:
        st.error(f"Error en {nombre_archivo}: {e}")
        return False
    finally:
        if driver: driver.quit()

# --- INTERFAZ ---
st.set_page_config(page_title="BI Global SmartCommerce", layout="wide")
st.title("📊 Consolidado Global: Honduras & El Salvador")

if st.sidebar.button("🚀 Sincronizar Ambas Cuentas"):
    for f in glob.glob(os.path.join(DOWNLOAD_PATH, "reporte_*.xlsx")): os.remove(f)
    with st.spinner("Extrayendo datos de ambos servidores..."):
        for cuenta in CUENTAS:
            descargar_reporte(cuenta['user'], cuenta['pass'], cuenta['nombre'])
        st.rerun()

archivos_descargados = glob.glob(os.path.join(DOWNLOAD_PATH, "reporte_*.xlsx"))

if archivos_descargados:
    lista_dfs = []
    
    # DINÁMICA DE CARGA DE TABLAS
    for f in archivos_descargados:
        try:
            # SmartCommerce tiene los encabezados en la fila 10 (skiprows=9)
            # Esto carga correctamente el rango A11:R11 como títulos de columnas
            temp_df = pd.read_excel(f, skiprows=9).dropna(how='all')
            
            if not temp_df.empty:
                # 1. Identificar país
                pais = "Honduras" if "Honduras" in f else "El Salvador"
                temp_df['Pais_Origen'] = pais
                
                # 2. Forzar que las columnas sean strings para evitar conflictos en la unión
                temp_df.columns = [str(col).strip() for col in temp_df.columns]
                
                # 3. Eliminar filas basura que a veces se filtran (repetir el encabezado)
                # Si una fila tiene el mismo nombre que la columna 'Total', se elimina.
                col_ref = next((c for c in temp_df.columns if 'total' in c.lower()), temp_df.columns[0])
                temp_df = temp_df[temp_df[col_ref].astype(str).str.lower() != 'total']
                
                lista_dfs.append(temp_df)
        except Exception as e:
            st.warning(f"No se pudo leer el archivo de {f}: {e}")

    if lista_dfs:
        # UNIFICACIÓN DE DATOS (Mismos encabezados para todos)
        df_global = pd.concat(lista_dfs, ignore_index=True, sort=False)

        # Identificación de columnas clave
        col_total = next((c for c in df_global.columns if 'total' in c.lower()), 'Total')
        col_envio = next((c for c in df_global.columns if 'envío' in c.lower() or 'envio' in c.lower()), 'Estado de envío')
        col_tienda = next((c for c in df_global.columns if 'tienda' in c.lower()), 'Tienda')
        
        # Limpieza de Moneda (L y $)
        df_global[col_total] = pd.to_numeric(
            df_global[col_total].astype(str).str.replace('L', '').str.replace('$', '').str.replace(',', '').str.strip(), 
            errors='coerce'
        ).fillna(0)

        # --- DASHBOARD ---
        st.sidebar.subheader("🔍 Filtros de Visualización")
        paises_sel = st.sidebar.multiselect("Seleccionar Países", df_global['Pais_Origen'].unique(), default=df_global['Pais_Origen'].unique())
        df_final = df_global[df_global['Pais_Origen'].isin(paises_sel)]

        k1, k2, k3 = st.columns(3)
        k1.metric("📦 Pedidos Totales", f"{len(df_final)}")
        k2.metric("💰 Venta Consolidada", f"L {df_final[col_total].sum():,.2f}")
        k3.metric("🎫 Ticket Promedio", f"L {df_final[col_total].mean():,.2f}" if len(df_final) > 0 else "0")

        st.divider()

        # Gráficos
        c1, c2 = st.columns(2)
        with c1:
            st.write("### 💰 Ventas por País")
            v_pais = df_final.groupby('Pais_Origen')[col_total].sum().reset_index()
            st.plotly_chart(px.bar(v_pais, x='Pais_Origen', y=col_total, color='Pais_Origen', text_auto='.2s'), use_container_width=True)
        
        with c2:
            st.write("### 🚚 Logística (Estados)")
            if col_envio in df_final.columns:
                st.plotly_chart(px.pie(df_final, names=col_envio, hole=0.4), use_container_width=True)

        with st.expander("📄 Ver Tabla Maestra Consolidada"):
            st.dataframe(df_final, use_container_width=True)
else:
    st.info("👋 Por favor, pulsa **'Sincronizar Ambas Cuentas'** para generar el reporte unificado.")
