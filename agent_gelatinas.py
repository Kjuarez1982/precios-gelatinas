import asyncio
import re
from datetime import datetime
import pandas as pd
from playwright.async_api import async_playwright

CSV_EXPORT_NAME = "historico_gelatinas.csv"

TARGETS = [
    {"supermercado": "Walmart GT", "url": "https://www.walmart.com.gt/abarrotes/azucar-y-postres/gelatinas-y-flan"},
    {"supermercado": "Maxi Despensa", "url": "https://www.maxidespensa.com.gt/abarrotes/azucar-y-postres/gelatinas-y-flan"},
    {"supermercado": "La Torre", "url": "https://www.latorre.com.gt/gelatinas"}
]

def limpiar_precio(texto):
    if not texto: return 0.0
    m = re.search(r"(\d+(?:\.\d+)?)", texto.replace(",", ""))
    return float(m.group(1)) if m else 0.0

def extraer_marca(nombre):
    n = nombre.lower()
    if "castilla" in n: return "Castilla"
    if "royal" in n: return "Royal"
    if "imperial" in n: return "Imperial"
    if "suli" in n: return "Suli (Marca Privada)"
    if "great value" in n: return "Great Value (Marca Privada)"
    if "dely" in n: return "Dely"
    if "gely" in n: return "Gely"
    if "pronto" in n: return "Pronto"
    return "Otras"

def extraer_gramos(nombre):
    n = nombre.lower()
    # Buscar patrones como 85g, 85 g, 85 gramos
    m_g = re.search(r"(\d+(?:\.\d+)?)\s*(?:g|gr|gramos|g\b)", n)
    if m_g:
        return float(m_g.group(1))
    
    # Buscar patrones en onzas (1 oz ≈ 28.35 g)
    m_oz = re.search(r"(\d+(?:\.\d+)?)\s*(?:oz|onzas)", n)
    if m_oz:
        return round(float(m_oz.group(1)) * 28.35, 1)
        
    # En gelatinas en sobre el tamaño estándar en Centroamérica suele ser 85g
    if "sobre" in n or "bolsa" in n:
        return 85.0
    return None

def extraer_segmento(nombre):
    n = nombre.lower()
    if any(k in n for k in ["light", "zero", "cero", "sin azucar", "sin azúcar", "diet"]):
        return "Zero / Light"
    return "Regular"

async def recolectar_tienda(page, tienda):
    nombre_tienda = tienda["supermercado"]
    url = tienda["url"]
    items = []
    print(f"Visitando: {nombre_tienda}...")
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
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
                elif any(p in l.lower() for p in ["gelatina", "gely", "dely", "castilla", "royal", "imperial"]):
                    nombre = l

            if nombre and precio > 0:
                gramos = extraer_gramos(nombre)
                precio_100g = round((precio / gramos) * 100, 2) if gramos and gramos > 0 else None

                items.append({
                    "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "Supermercado": nombre_tienda,
                    "Marca": extraer_marca(nombre),
                    "Segmento": extraer_segmento(nombre),
                    "Producto": nombre,
                    "Gramos": gramos,
                    "Precio_Quetzales": precio,
                    "Precio_por_100g": precio_100g
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
        df_nuevo = pd.DataFrame(todos).drop_duplicates(subset=["Supermercado", "Producto", "Precio_Quetzales"])
        try:
            df_existente = pd.read_csv(CSV_EXPORT_NAME)
            df_final = pd.concat([df_existente, df_nuevo], ignore_index=True).drop_duplicates(
                subset=["Fecha", "Supermercado", "Producto", "Precio_Quetzales"]
            )
        except:
            df_final = df_nuevo
        df_final.to_csv(CSV_EXPORT_NAME, index=False, encoding="utf-8-sig")
        print(f"¡Éxito! Se actualizaron {len(df_final)} registros con variables RGM.")

if __name__ == "__main__":
    asyncio.run(main())
