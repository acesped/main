# =======================================
# IMPORTS GENERALES
# =======================================
import os
import json
import requests
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials

# =======================================
# AUTORIZACIÓN GOOGLE SHEETS
# =======================================
def cargar_credenciales_google():
    print("🔐 Cargando credenciales desde GOOGLE_CREDENTIALS...")
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
# SCRAPING DEL ÚLTIMO SORTEO
# =======================================
def obtener_ultimo_sorteo():
    url = "https://www.loterias.com/loto-3/resultados"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    listas_bolas = soup.find_all("ul", class_="balls")
    if not listas_bolas:
        raise ValueError("No se encontraron números del sorteo en la web")

    # Tomamos la primera lista (último sorteo)
    bolas = listas_bolas[0].find_all("li", class_="ball")
    numeros = [int(b.text.strip()) for b in bolas]
    if len(numeros) != 3:
        raise ValueError("No se pudieron extraer los 3 números del sorteo")
    return numeros

# =======================================
# APPEND EN GOOGLE SHEETS
# =======================================
def append_ultimo_sorteo(sheet, numeros):
    datos = sheet.get_all_values()
    # Evitar duplicados comparando columnas B-D
    if datos:
        ultima_fila = datos[-1]
        if len(ultima_fila) >= 4 and ultima_fila[1:4] == [str(n) for n in numeros]:
            print("El último sorteo ya está registrado.")
            return
    # Añadir nueva fila (columnas B, C, D)
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

    gc = cargar_credenciales_google()
    SPREADSHEET_ID = "1QYwk8uKydO-xp0QALkh0pVVFmt50jnvU_BwZdRghES0"
    worksheet = gc.open_by_key(SPREADSHEET_ID).worksheet("loto3")

    append_ultimo_sorteo(worksheet, numeros)
