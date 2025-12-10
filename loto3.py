# =======================================
# IMPORTS GENERALES
# =======================================
import os
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

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
# SCRAPING
# =======================================
def obtener_ultimo_sorteo(anio):
    url = f"https://www.loterias.com/loto-3/resultados/{anio}"
    print(f"🔎 Obteniendo últimos números del Loto 3 del año {anio}...")
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except:
        raise ConnectionError(f"No se pudo acceder a {url}")

    soup = BeautifulSoup(resp.text, "html.parser")
    tabla = soup.find("table", class_="archives")
    if not tabla:
        raise ValueError("No se encontró la tabla de resultados en la web")

    # Buscamos la primera fila válida (último sorteo)
    for fila in tabla.tbody.find_all("tr"):
        celdas = fila.find_all("td")
        if len(celdas) < 2:
            continue
        enlace = celdas[0].find("a")
        if not enlace:
            continue
        texto_fecha = enlace.get_text(separator=" ").strip()
        partes = texto_fecha.split()
        if len(partes) < 3:
            continue
        fecha_raw = " ".join(partes[1:])
        try:
            fecha = corregir_fecha(fecha_raw)
        except:
            continue
        lista = celdas[1].find("ul", class_="balls")
        if not lista:
            continue
        numeros = [li.text.strip() for li in lista.find_all("li", class_="ball")]
        if len(numeros) != 3:
            continue
        numeros = [int(n) for n in numeros]
        return fecha, numeros

    raise ValueError("No se pudieron extraer los 3 números del sorteo")

# =======================================
# FUNCIONES GOOGLE SHEETS
# =======================================
def append_ultimo_sorteo(worksheet, fecha, numeros):
    # Revisar si ya existe la fecha en la hoja
    registros = worksheet.get_all_records()
    for fila in registros:
        if fila.get("Fecha") == fecha.strftime("%Y-%m-%d"):
            print("⚠️ Sorteo ya registrado. No se agrega fila duplicada.")
            return
    # Agregar nueva fila
    fila = [
        fecha.strftime("%Y-%m-%d"),
        numeros[0],
        numeros[1],
        numeros[2]
    ]
    worksheet.append_row(fila, value_input_option="USER_ENTERED")
    print("✅ Sorteo agregado correctamente:", fila)

# =======================================
# MAIN
# =======================================
if __name__ == "__main__":
    anio_actual = datetime.now().year

    fecha, numeros = obtener_ultimo_sorteo(anio=anio_actual)
    print("Últimos números obtenidos:", numeros, "Fecha:", fecha.strftime("%Y-%m-%d"))

    gc = cargar_credenciales_google()
    SPREADSHEET_ID = "1QYwk8uKydO-xp0QALkh0pVVFmt50jnvU_BwZdRghES0"
    worksheet = gc.open_by_key(SPREADSHEET_ID).worksheet("loto3")

    append_ultimo_sorteo(worksheet, fecha, numeros)
