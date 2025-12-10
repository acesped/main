# =======================================
# IMPORTS
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
    MultiHeadAttention, GlobalAveragePooling1D
)
from tensorflow.keras.utils import to_categorical

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
# MODELOS
# =======================================
def crear_modelo_lstm(seq_length, num_classes=10):
    model = Sequential([
        Embedding(input_dim=num_classes, output_dim=32, input_length=seq_length),
        LSTM(64),
        Dense(num_classes, activation='softmax')
    ])
    model.compile(loss='categorical_crossentropy', optimizer='adam')
    return model

def crear_modelo_transformer(seq_length, num_classes=10, embed_dim=32, heads=2, ff_dim=64):
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
# MAIN
# =======================================
if __name__ == "__main__":
    # Descargar resultados de los últimos 10 años
    año_actual = datetime.now().year
    años = list(range(año_actual, año_actual - 10, -1))
    resultados = pd.DataFrame()
    for anio in años:
        df = extraer_resultados_por_anio(anio)
        if not df.empty:
            resultados = pd.concat([resultados, df], ignore_index=True)
    print(f"🔔 Total resultados extraídos: {len(resultados)}")

    # Preparar datos
    seq_length = 10
    X, y = preparar_datos_lstm(resultados, seq_length)
    num_classes = 10
    y_cat = to_categorical(y, num_classes=num_classes)

    # ================= ENTRENAR LSTM =================
    modelo_lstm = crear_modelo_lstm(seq_length, num_classes)
    print("⚡ Entrenando LSTM...")
    modelo_lstm.fit(X, y_cat, epochs=50, batch_size=32, validation_split=0.1)
    modelo_lstm.save_weights("weights_lstm.h5")
    print("✅ Pesos LSTM guardados en weights_lstm.h5")

    # ================= ENTRENAR TRANSFORMER =================
    modelo_trans = crear_modelo_transformer(seq_length, num_classes)
    print("⚡ Entrenando Transformer...")
    modelo_trans.fit(X, y_cat, epochs=50, batch_size=32, validation_split=0.1)
    modelo_trans.save_weights("weights_trans.h5")
    print("✅ Pesos Transformer guardados en weights_trans.h5")
