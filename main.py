# =======================================
# IMPORTS GENERALES
# =======================================
import os
import json
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import numpy as np
import tensorflow as tf
from tensorflow.keras.models import Sequential, Model
from tensorflow.keras.layers import (
    LSTM, Dense, Embedding, Input, LayerNormalization,
    Dropout, MultiHeadAttention, GlobalAveragePooling1D
)
from tensorflow.keras.utils import to_categorical

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


gc = cargar_credenciales_google()
SPREADSHEET_ID = "1QYwk8uKydO-xp0QALkh0pVVFmt50jnvU_BwZdRghES0"
worksheet = gc.open_by_key(SPREADSHEET_ID).worksheet("results")


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
# SCRAPING
# =======================================
def extraer_resultados_por_anio(anio):
    url = f"https://www.loterias.com/loto-3/resultados/{anio}"
    print(f"🔎 Procesando año {anio}...")

    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except:
        print(f"❌ Error al obtener datos del año {anio}")
        return pd.DataFrame()

    soup = BeautifulSoup(resp.text, "html.parser")
    tabla = soup.find("table", class_="archives")

    if not tabla:
        return pd.DataFrame()

    datos = []
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

        listas = celdas[1].find_all("ul", class_="balls")
        for lista in listas:
            try:
                tipo = lista.find("li").text.strip()
                numeros = [li.text.strip() for li in lista.find_all("li", class_="ball")]
                if len(numeros) != 3:
                    continue

                ultimo = int(numeros[2])
                datos.append({
                    "Fecha": fecha,
                    "Turno": tipo,
                    "Último Número": ultimo,
                })
            except:
                pass

    return pd.DataFrame(datos)


# =======================================
# PREPROCESAMIENTO
# =======================================
def preparar_datos_lstm(df, seq_length=10):
    df = df.sort_values("Fecha").reset_index(drop=True)
    numeros = df["Último Número"].values
    X, y = [], []
    for i in range(len(numeros) - seq_length):
        X.append(numeros[i:i+seq_length])
        y.append(numeros[i+seq_length])
    return np.array(X), np.array(y)


# =======================================
# MODELOS SIN ENTRENAR (SE CARGAN PESOS)
# =======================================
def crear_modelo_lstm(seq_length, num_classes=10):
    model = Sequential([
        Embedding(input_dim=num_classes, output_dim=32, input_length=seq_length),
        LSTM(64),
        Dense(num_classes, activation='softmax')
    ])
    model.compile(loss='categorical_crossentropy', optimizer='adam')
    return model


def crear_modelo_transformer(seq_length, num_classes=10, embed_dim=32, heads=2, ff_dim=64, dropout=0.1):
    inputs = Input(shape=(seq_length,), dtype="int32")
    x = Embedding(num_classes, embed_dim)(inputs)

    attn = MultiHeadAttention(num_heads=heads, key_dim=embed_dim)(x, x)
    out1 = LayerNormalization(epsilon=1e-6)(x + attn)

    ff = Dense(ff_dim, activation="relu")(out1)
    ff = Dense(embed_dim)(ff)
    out2 = LayerNormalization(epsilon=1e-6)(out1 + ff)

    x = GlobalAveragePooling1D()(out2)
    outputs = Dense(num_classes, activation="softmax")(x)

    model = Model(inputs, outputs)
    model.compile(optimizer="adam", loss="categorical_crossentropy")
    return model


# =======================================
# ENSAMBLE
# =======================================
def ensemble_predict(preds_list):
    avg = np.mean(preds_list, axis=0)
    return np.argmax(avg, axis=1), np.max(avg, axis=1)


# =======================================
# MONTE CARLO
# =======================================
def simulacion_monte_carlo_fast(modelos, entrada, num_simulaciones=5000):
    p1 = modelos[0].predict(entrada, verbose=0)[0]
    p2 = modelos[1].predict(entrada, verbose=0)[0]
    probs = (p1 + p2) / 2
    return np.random.choice(np.arange(10), size=num_simulaciones, p=probs)


# =======================================
# MAIN
# =======================================
if __name__ == "__main__":

    año_actual = datetime.now().year
    años = list(range(año_actual, año_actual - 10, -1))

    resultados = pd.DataFrame()
    for anio in años:
        df = extraer_resultados_por_anio(anio)
        if not df.empty:
            resultados = pd.concat([resultados, df], ignore_index=True)

    print(f"🔔 Total resultados extraídos: {len(resultados)}")

    seq_length = 10
    X, y = preparar_datos_lstm(resultados, seq_length)
    ultima_seq = resultados.sort_values("Fecha")["Último Número"].values[-seq_length:]
    entrada = np.array([ultima_seq])

    # ========== CARGA DE MODELOS PRE-ENTRENADOS ==========
    print("📥 Cargando pesos pre-entrenados...")

    modelo_lstm = crear_modelo_lstm(seq_length)
    modelo_lstm.load_weights("weights_lstm.h5")

    modelo_trans = crear_modelo_transformer(seq_length)
    modelo_trans.load_weights("weights_trans.h5")

    print("✅ Modelos cargados correctamente.")

    # ================= PREDICCIONES ======================
    p_lstm = modelo_lstm.predict(entrada, verbose=0)
    p_trans = modelo_trans.predict(entrada, verbose=0)

    pred_clase, pred_prob = ensemble_predict([p_lstm, p_trans])

    # Monte Carlo
    resultados_mc = simulacion_monte_carlo_fast([modelo_lstm, modelo_trans], entrada, 5000)
    conteo = pd.Series(resultados_mc).value_counts().sort_index()
    num_max = conteo.idxmax()
    prob_mc = conteo.max() / 5000.0

    # ================= GUARDAR EN GOOGLE SHEETS =================
    print("📤 Enviando resultados a Google Sheets...")

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    fila = [
        timestamp,
        int(np.argmax(p_lstm)), float(np.max(p_lstm)),
        int(np.argmax(p_trans)), float(np.max(p_trans)),
        int(pred_clase[0]), float(pred_prob[0]),
        int(num_max), float(prob_mc)
    ]

    worksheet.append_row(fila, value_input_option="USER_ENTERED")

    print("✅ Google Sheets actualizado correctamente.")
