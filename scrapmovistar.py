# ============================================================
# MOVISTAR CHILE – SCRAPING + GOOGLE SHEETS + ALERTAS
# Adaptado para GitHub Actions
# ============================================================

import asyncio
import pandas as pd
from datetime import datetime
import pytz
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from playwright.async_api import async_playwright
import gspread
from google.oauth2.service_account import Credentials

# ---------------------------
# CONFIG GOOGLE SHEETS
# ---------------------------
CREDENTIALS_PATH = "service_account.json"  # sube este archivo al repo
SPREADSHEET_ID = "1vDRY9ugCjZaj-AGkU9jbw7LdvcypzZ8RsLdfqAgt4Yw"
SHEET_LATEST = "latest"
SHEET_PAST = "past"

HEADERS = ["timestamp","sku","producto","precio_oferta","marca"]
CL_TZ = pytz.timezone("America/Santiago")

creds = Credentials.from_service_account_file(
    CREDENTIALS_PATH,
    scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
)

gc = gspread.authorize(creds)
spreadsheet = gc.open_by_key(SPREADSHEET_ID)
ws_latest = spreadsheet.worksheet(SHEET_LATEST)
ws_past = spreadsheet.worksheet(SHEET_PAST)

# ---------------------------
# UTILIDADES
# ---------------------------
def overwrite_sheet_with_current_time(ws, df):
    df_to_write = df.copy()
    current_time = datetime.now(CL_TZ).strftime("%Y-%m-%d %H:%M:%S")
    if "timestamp" in df_to_write.columns:
        df_to_write["timestamp"] = current_time
    ws.clear()
    ws.update([df_to_write.columns.tolist()] + df_to_write.values.tolist())

# ---------------------------
# SCRAPING MOVISTAR
# ---------------------------
async def scrape_movistar():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36")
        )
        page = await context.new_page()
        await page.goto("https://ww2.movistar.cl/ofertas/celulares-liberados/",
                        wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(5000)

        cards = await page.query_selector_all("a.cro-tarjeta")
        if not cards:
            await browser.close()
            raise RuntimeError("❌ No se encontraron tarjetas")

        data = []
        for card in cards:
            try:
                data.append({
                    "timestamp": "",
                    "sku": await card.get_attribute("data-sap"),
                    "producto": (await (await card.query_selector("h2.of-card-name")).inner_text()).strip(),
                    "precio_oferta": (await (await card.query_selector("p.of-price-saleprice")).inner_text()).strip(),
                    "marca": await card.get_attribute("data-brand")
                })
            except:
                continue
        await browser.close()
    return pd.DataFrame(data)

# ---------------------------
# EJECUCIÓN
# ---------------------------
df_new = asyncio.get_event_loop().run_until_complete(scrape_movistar())

# Copiar df_new a 'past' (última publicación) y actualizar 'latest'
overwrite_sheet_with_current_time(ws_past, df_new)
overwrite_sheet_with_current_time(ws_latest, df_new)

# ---------------------------
# ALERTAS DE PRECIO
# ---------------------------
try:
    df_old = pd.DataFrame(ws_past.get_all_records())
    merged = df_old.merge(df_new, on="sku", suffixes=("_old","_new"))
    changes = merged[merged["precio_oferta_old"] != merged["precio_oferta_new"]]

    for _, row in changes.iterrows():
        precio_old = float(row["precio_oferta_old"].replace("$","").replace(".","").replace(",","").strip())
        precio_new = float(row["precio_oferta_new"].replace("$","").replace(".","").replace(",","").strip())
        if precio_old == 0:
            continue
        diff_pct = abs(precio_new - precio_old) / precio_old
        if diff_pct >= 0.5:
            sender_email = "ari.cesped@gmail.com"
            receiver_email = "ari.cesped@gmail.com"
            password = "xmqycfdnigtmrsis"
            message = MIMEMultipart("alternative")
            message["Subject"] = f"🚨 Cambio ≥50%: {row['producto_old']}"
            message["From"] = sender_email
            message["To"] = receiver_email
            text = (f"Producto: {row['producto_old']}\n"
                    f"SKU: {row['sku']}\n"
                    f"Precio anterior: {row['precio_oferta_old']}\n"
                    f"Precio nuevo: {row['precio_oferta_new']}\n"
                    f"Diferencia: {diff_pct*100:.1f}%")
            message.attach(MIMEText(text, "plain"))
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(sender_email, password)
                server.sendmail(sender_email, receiver_email, message.as_string())

except Exception as e:
    print("❌ Error procesando alertas:", e)
