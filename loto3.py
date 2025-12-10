# =======================================
# IMPORTS
# =======================================
import os
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# =======================================
# AUTORIZACIÓN GOOGLE SHEETS
# =======================================
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

# =======================================
# DICCIONARIO MESES
# =======================================
MESES = {
    "ene.": "01", "feb.": "02", "mar.": "03", "abr.": "04",
    "may.": "05", "jun.": "06", "jul.": "07", "ago.": "08",
    "sep.": "09", "oct.": "10", "nov.": "11", "dic.": "12",
}

def corregir_fecha(fecha_str):
    for mes_abrev, mes_num in MESES.items():
        if mes_abrev in fecha_str:
            fecha_str = fecha_str.replace(mes_abrev, mes_num)
            return datetime.strptime(fecha_str, "%d %m %Y")
    raise ValueError(f"Mes no reconocido en fecha '{fecha_str}'")

# =======================================
# SCRAPING ÚLTIMO SORTEO
# =======================================
def obtener_ultimo_sorteo(anio=None):
    if anio is None:
        anio = datetime.now().year
    url = f"https://www.loterias.com/loto-3/resultados/{anio}"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Tomamos la primera fila de la tabla de resultados del año
    tabla = soup.find("table", class_="archives")
    if not tabla:
        raise ValueError("No se encontró la tabla de resultados en la web")

    fila = tabla.tbody.find("tr")
    if not fila:
        raise ValueError("No se encontró ninguna fila de resultados")

    # Fecha
    enlace = fila.find("a")
    if not enlace:
        raise ValueError("No se encontró la fecha del sorteo")
    partes_fecha = enlace.text.strip().split()
    fecha_raw = " ".join(partes_fecha[1:])
    fecha = corregir_fecha(fecha_raw)

    # Números
    celdas = fila.find_all("td")
    if len(celdas) < 2:
        raise ValueError("No hay celdas con resultados")
    listas = celdas[1].find_all("ul", class_="balls")
    if not listas:
        raise ValueError("No se encontraron los números del sorteo")
    numeros = [int(li.text.strip()) for li in listas[0].find_all("li", class_="ball")]
    if len(numeros) != 3:
        raise ValueError("No se pudieron extraer los 3 números del sorteo")

    return fecha, numeros

# =======================================
# APPEND EN GOOGLE SHEETS
# =======================================
def append_ultimo_sorteo(sheet, fecha, numeros):
    datos = sheet.get_all_values()
    # Verificar si ya existe el sorteo
    for fila in datos:
        if fila and len(fila) >= 2 and fila[1:4] == [str(n) for n in numeros]:
            print("El último sorteo ya está registrado.")
            return
    # Agregar nueva fila
    fila_vacia = len(datos) + 1
    sheet.update(f'B{fila_vacia}:D{fila_vacia}', [numeros])
    sheet.update(f'A{fila_vacia}', fecha.strftime("%Y-%m-%d"))
    print(f"Sorteo agregado: {numeros} en fila {fila_vacia} con fecha {fecha.strftime('%Y-%m-%d')}")

# =======================================
# MAIN
# =======================================
if __name__ == "__main__":
    año_actual = datetime.now().year
    print(f"🔎 Obteniendo últimos números del Loto 3 del año {año_actual}...")
    fecha, numeros = obtener_ultimo_sorteo(anio_actual)
    print("Últimos números obtenidos:", numeros, "Fecha:", fecha.strftime("%Y-%m-%d"))

    gc = cargar_credenciales_google()
    SPREADSHEET_ID = "1QYwk8uKydO-xp0QALkh0pVVFmt50jnvU_BwZdRghES0"
    worksheet = gc.open_by_key(SPREADSHEET_ID).worksheet("loto3")

    append_ultimo_sorteo(worksheet, fecha, numeros)
