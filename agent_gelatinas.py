import asyncio
import re
from datetime import datetime
import pandas as pd
from playwright.async_api import async_playwright

CSV_EXPORT_NAME = "historico_gelatinas.csv"

# Tiendas a visitar
TARGETS = [
    {"supermercado": "Walmart GT", "url": "https://www.walmart.com.gt/abarrotes/azucar-y-postres/gelatinas-y-flan"},
    {"supermercado": "Maxi Despensa", "url": "https://www.maxidespensa.com.gt/abarrotes/azucar-y-postres/gelatinas-y-flan"},
    {"supermercado": "La Torre", "url": "https://www.latorre.com.gt/gelatinas"}
]

def limpiar_precio(texto):
    if not texto: return 0.0
    m = re.search(r"(\d+(?:\.\d+)?)", texto.replace(",", ""))
    return float(m.group(1)) if m else 0.0

async def recolectar_tienda(page, tienda):
    nombre_tienda = tienda["supermercado"]
    url = tienda["url"]
    items = []
    print(f"Visitando: {nombre_tienda}...")
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        # Bajamos un poco en la página para que carguen los productos
        for _ in range(3):
            await page.mouse.wheel(0, 1200)
            await asyncio.sleep(2)

        tarjetas = await page.locator("article, div[class*='product-summary']").all()
        for t in tarjetas:
            texto = await t.inner_text()
            lineas = [l.strip() for l in texto.split("\n") if l.strip()]
            precio, nombre = 0.0, ""
            for l in lineas:
                if re.match(r"^Q\s?\d+", l):
                    precio = limpiar_precio(l)
                elif any(p in l.lower() for p in ["gelatina", "gely", "dely", "castilla"]):
                    nombre = l
            if nombre and precio > 0:
                items.append({
                    "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "Supermercado": nombre_tienda,
                    "Producto": nombre,
                    "Precio_Quetzales": precio
                })
    except Exception as e:
        print(f"Nota en {nombre_tienda}: {e}")
    return items

async def main():
    todos = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0")
        page = await context.new_page()
        for t in TARGETS:
            datos = await recolectar_tienda(page, t)
            todos.extend(datos)
        await browser.close()

    if todos:
        df_nuevo = pd.DataFrame(todos).drop_duplicates()
        try:
            df_existente = pd.read_csv(CSV_EXPORT_NAME)
            df_final = pd.concat([df_existente, df_nuevo], ignore_index=True).drop_duplicates()
        except:
            df_final = df_nuevo
        df_final.to_csv(CSV_EXPORT_NAME, index=False, encoding="utf-8-sig")
        print(f"¡Éxito! Se guardaron {len(df_final)} registros.")

if __name__ == "__main__":
    asyncio.run(main())
