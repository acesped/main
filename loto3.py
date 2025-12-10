# loto3.py
import os
import json
import requests
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials

# =======================================
# CARGA DE CREDENCIALES GOOGLE SHEETS
# =======================================
def cargar_credenciales():
    creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS"])
    creds = Credentials.from_service_account_info(
        creds_dict,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
    )
    return gspread.authorize(creds)

# =======================================
# SCRAPING ÚLTIMO SORTEO LOTO 3
# =======================================
def obtener_ultimo_sorteo():
    url = "https://www.loterias.com/loto-3/resultados"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    
    soup = BeautifulSoup(resp.text, "html.parser")
    
    # Buscamos la primera tabla con resultados
    tabla = soup.find("table", class_="archives")
    if not tabla:
        raise ValueError("No se encontró la tabla de resultados en la web")
    
    # Tomamos la primera fila (último sorteo)
    fila = tabla.tbody.find("tr")
    celdas = fila.find_all("td")
    
    # Obtenemos los números
    lista_bolas = celdas[1].find("ul", class_="balls")
    numeros = [int(li.text.strip()) for li in lista_bolas.find_all("li", class_="ball")]
    
    if len(numeros) != 3:
        raise ValueError("No se pudieron extraer los 3 números del sorteo")
    
    return numeros  # [num1, num2, num3]

# =======================================
# FUNCIONES GOOGLE SHEETS
# =======================================
def append_ultimo_sorteo(sheet, numeros):
    # Obtenemos todas las filas existentes
    datos = sheet.get_all_values()
    
    # Revisamos si el último sorteo ya existe (comparando columna B-D)
    if datos:
        ultima_fila = datos[-1]
        if len(ultima_fila) >= 4:
            if ultima_fila[1:4] == [str(n) for n in numeros]:
                print("El último sorteo ya está registrado en la hoja.")
                return
    
    # Append en la siguiente fila vacía (columnas B, C, D)
    fila_vacia = len(datos) + 1
    sheet.update(f'B{fila_vacia}', [numeros])
    print(f"Sorteo agregado: {numeros} en fila {fila_vacia}")

# =======================================
# MAIN
# =======================================
if __name__ == "__main__":
    print("🔎 Obteniendo últimos números del Loto 3...")
    numeros = obtener_ultimo_sorteo()
    print("Últimos números obtenidos:", numeros)
    
    gc = cargar_credenciales()
    spreadsheet = gc.open_by_key("1QYwk8uKydO-xp0QALkh0pVVFmt50jnvU_BwZdRghES0")
    worksheet = spreadsheet.worksheet("loto3")
    
    append_ultimo_sorteo(worksheet, numeros)
