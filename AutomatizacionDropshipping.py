import time
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

# --- CONFIGURACIÓN DE DESCARGA AUTOMÁTICA ---
chrome_options = Options()
download_path = os.path.join(os.path.expanduser("~"), "Downloads") 

prefs = {
    "download.default_directory": download_path,
    "download.prompt_for_download": False,
    "directory_upgrade": True,
    "safebrowsing.enabled": False # Desactiva advertencias para descargas automáticas
}
chrome_options.add_experimental_option("prefs", prefs)

# Inicializar el navegador
driver = webdriver.Chrome(options=chrome_options)

try:
    # 1. Inicio
    driver.maximize_window()
    driver.get("https://smartcommerce.lat/sign-in")
    wait = WebDriverWait(driver, 30)

    print(">>> Iniciando sesión...")

    # 2. Correo Electrónico (Full XPath proporcionado)
    xpath_email = "/html/body/app-root/layout/empty-layout/div/div/auth-sign-in/div/div[1]/div[2]/form/div[1]/input"
    email_field = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_email)))
    email_field.send_keys("rv309962@gmail.com")

    # 3. Contraseña (Full XPath proporcionado)
    xpath_pass = "/html/body/app-root/layout/empty-layout/div/div/auth-sign-in/div/div[1]/div[2]/form/div[2]/div/input"
    pass_field = driver.find_element(By.XPATH, xpath_pass)
    pass_field.send_keys("Rodrigo052002")

    # 4. Clic en botón de Login
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
    print(">>> Login exitoso. Esperando carga del dashboard...")

    # 5. Clic en el botón 'Pedidos' (Full XPath proporcionado)
    xpath_btn_pedidos = "/html/body/app-root/layout/dense-layout/fuse-vertical-navigation/div/div[2]/fuse-vertical-navigation-group-item[3]/fuse-vertical-navigation-basic-item[1]/div/a/div/div/span"
    btn_pedidos = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_btn_pedidos)))
    btn_pedidos.click()
    print(">>> Entrando a la sección de Pedidos...")

    # 6. Clic en el botón de Exportar Excel (Full XPath CORREGIDO)
    print(">>> Ejecutando clic en descarga de Excel...")
    xpath_btn_excel = "/html/body/app-root/layout/dense-layout/div/div[2]/app-orders/div/mat-drawer-container/mat-drawer-content/app-orders-header/div/div[3]/app-excel-export-button/button"
    
    # Esperamos a que la tabla cargue y el botón sea visible
    btn_excel = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_btn_excel)))
    btn_excel.click()
    
    print(f">>> Descarga completada en: {download_path}")
    
    # Pausa final para asegurar que el navegador no se cierre antes de que el archivo se escriba en el disco
    time.sleep(8)

except Exception as e:
    print(f"!!! Error en el proceso: {e}")

finally:
    print(">>> Cerrando navegador.")
    driver.quit()