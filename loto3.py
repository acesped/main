# actualizar_loto3.py
import os
import json
import requests
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# ================= GOOGLE SHEETS =================
def cargar_credenciales_google():
    creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS"])
    creds = Credentials.from_service_account_info(
        creds_dict,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
    )
    return gspread.authorize(creds)

gc = cargar_credenciales_google()
SPREADSHEET_ID = "1QYwk8uKydO-xp0QALkh0pVVFmt50jnvU_BwZdRghES0"
worksheet = gc.open_by_key(SPREADSHEET_ID).worksheet("loto3")

# ================= SCRAPING =================
def obtener_ultimo_sorteo():
    url = "https://www.loterias.com/loto-3/resultados"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        print(f"❌ Error al obtener los datos: {e}")
        return None, None

    soup = BeautifulSoup(resp.text, "html.parser")
    tabla = soup.find("table", class_="archives")
    if not tabla:
        print("❌ No se encontró la tabla de resultados.")
        return None, None

    # Tomamos la primera fila (último sorteo)
    fila = tabla.tbody.find("tr")
    celdas = fila.find_all("td")

    # Fecha
    enlace = celdas[0].find("a")
    fecha = enlace.get_text(strip=True) if enlace else "Fecha no disponible"

    # Últimos 3 números (turno vespertino normalmente)
    lista_bolas = celdas[1].find("ul", class_="balls")
    numeros = [li.text.strip() for li in lista_bolas.find_all("li", class_="ball")] if lista_bolas else []

    if len(numeros) != 3:
        print("❌ No se encontraron 3 números en el último sorteo.")
        return fecha, None

    return fecha, numeros

# ================= APPEND A GOOGLE SHEETS =================
def append_a_sheet(fecha, numeros):
    if numeros:
        fila = [fecha] + numeros  # columna 1 = fecha, columnas 2-4 = números
        worksheet.append_row(fila, value_input_option="USER_ENTERED")
        print(f"✅ Último sorteo agregado: {fila}")
    else:
        print("❌ No se pudo agregar el sorteo a la hoja.")

if __name__ == "__main__":
    fecha, numeros = obtener_ultimo_sorteo()
    append_a_sheet(fecha, numeros)
