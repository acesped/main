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
# GOOGLE SHEETS
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

SPREADSHEET_ID = "1QYwk8uKydO-xp0QALkh0pVVFmt50jnvU_BwZdRghES0"
gc = cargar_credenciales_google()

# =======================================
# SCRAPING ÚLTIMO SORTEO
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

def obtener_ultimo_sorteo():
    año_actual = datetime.now().year
    url = f"https://www.loterias.com/loto-3/resultados/{año_actual}"
    print(f"🔎 Obteniendo últimos números del Loto 3 del año {año_actual}...")

    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    tabla = soup.find("table", class_="archives")
    if not tabla:
        raise ValueError("No se encontró la tabla de resultados en la web")

    fila = tabla.tbody.find("tr")
    if not fila:
        raise ValueError("No se encontraron sorteos en la tabla")

    celdas = fila.find_all("td")
    if len(celdas) < 2:
        raise ValueError("Formato de fila inesperado")

    # Fecha del sorteo
    enlace = celdas[0].find("a")
    texto_fecha = enlace.get_text(separator=" ").strip()
    partes = texto_fecha.split()
    fecha_raw = " ".join(partes[1:])
    fecha = corregir_fecha(fecha_raw)

    # Números del sorteo Día
    lista_dia = celdas[1].find_all("ul", class_="balls")[0]
    numeros_dia = [int(li.text.strip()) for li in lista_dia.find_all("li", class_="ball")]

    return fecha, numeros_dia

# =======================================
# APPEND A GOOGLE SHEETS
# =======================================
def append_ultimo_sorteo(worksheet_name, numeros):
    worksheet = gc.open_by_key(SPREADSHEET_ID).worksheet(worksheet_name)
    fecha_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Obtenemos todos los valores existentes
    registros = worksheet.get_all_values()

    # Crear encabezado si no existe
    if len(registros) == 0:
        worksheet.append_row(["FechaHora", "Num1", "Num2", "Num3"], value_input_option="USER_ENTERED")
        registros = worksheet.get_all_values()

    # Evitamos duplicados comparando fecha/hora de ejecución
    for fila in registros[1:]:
        if fila[0] == fecha_hora:
            print(f"⚠️ Sorteo ya registrado en {worksheet_name}.")
            return

    fila = [fecha_hora] + numeros
    worksheet.append_row(fila, value_input_option="USER_ENTERED")
    print(f"✅ Últimos números obtenidos en {worksheet_name}:", numeros, "Fecha/hora:", fecha_hora)

# =======================================
# MAIN
# =======================================
if __name__ == "__main__":
    print("🔎 Obteniendo últimos números del Loto 3 Día...")
    fecha, numeros_dia = obtener_ultimo_sorteo()
    append_ultimo_sorteo("loto3_dia", numeros_dia)
