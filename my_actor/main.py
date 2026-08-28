import re
import asyncio
from apify import Actor

# Palabras clave para la Fase 2: Filtros de exclusión e inclusión
REFILL_KEYWORDS = ['refill', 'refills', 'cartridge', 'oil bottle', 'canister', 'replacement']
DEVICE_KEYWORDS = ['warmer', 'device', 'unit', 'starter kit', 'diffuser', 'dispenser', 'plug-in unit', 'purifier', 'humidifier']

def is_hardware_device(title: str, description: str) -> bool:
    """Fase 2: Filtra consumibles y exige términos de hardware."""
    title_clean = str(title or "").lower()
    desc_clean = str(description or "").lower()
    text = f"{title_clean} {desc_clean}"
    
    # Exigir términos obligatorios de dispositivo/hardware primero
    has_device_kw = any(kw in text for kw in DEVICE_KEYWORDS)
    if not has_device_kw:
        return False

    # Excluir solo si son recambios sueltos sin hardware explicito
    has_refill_kw = any(kw in text for kw in REFILL_KEYWORDS)
    if has_refill_kw and not any(k in text for k in ['starter kit', 'warmer', 'device', 'unit', 'diffuser']):
        return False
        
    return True

def create_canonical_key(brand_code: str, title: str) -> str:
    """Fase 4.1: Limpia el título (elimina fragancias/formatos) y genera el device_id."""
    clean_title = title.lower()
    clean_title = re.sub(
        r'(lavender|vanilla|linen|amber|citrus|pack of \d+|\d+ count|\d+ pk|white sage|mahogany|cinnamon|apples|juniper|teak|pumpkin|spice|ocean|gain|downy|april fresh|fresh linen|chamomile|rain water)',
        '',
        clean_title
    )
    model_slug = re.sub(r'[^a-z0-9]+', '_', clean_title).strip('_')
    
    if not model_slug:
        model_slug = "device"
        
    return f"{brand_code.lower()}_{model_slug}"

def extract_brand_from_title(title: str) -> str:
    """Extrae la marca del título del producto."""
    known_brands = [
        "Air Wick", "Febreze", "Glade", "Shark", "Dreo", "Winix", 
        "Levoit", "Airfire", "GermGuardian", "Bcooss", "Noahstrong", 
        "Mainstays", "Fimilo", "Better Homes & Gardens", "Great Value", "Yankee Candle"
    ]
    title_lower = title.lower()
    for brand in known_brands:
        if title_lower.startswith(brand.lower()):
            return brand.replace('. ', '_').replace(' ', '_')
    return "unknown_brand"

async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}
        
        # FASE 1: Ingesta de Parámetros y Scraping en Walmart
        search_term = actor_input.get("search_term", "air freshener")
        max_items = actor_input.get("max_items", 50)
        
        Actor.log.info(f"Iniciando ejecucion para search_term='{search_term}' (máx: {max_items} productos)...")
        
        # Uso del nuevo cliente nativo del SDK 4.x
        client = Actor.new_client()
        
        run = client.actor("apify/walmart-scraper").call(
            run_input={
                "search": search_term,
                "maxItems": max_items
            }
        )
        
        dataset_id = run.get("defaultDatasetId")
        dataset_page = client.dataset(dataset_id).list_items()
        
        if hasattr(dataset_page, 'items'):
            raw_dataset = list(dataset_page.items)
        elif isinstance(dataset_page, dict) and 'items' in dataset_page:
            raw_dataset = dataset_page['items']
        elif isinstance(dataset_page, list):
            raw_dataset = dataset_page
        else:
            raw_dataset = []
            
        Actor.log.info(f"Scraping completado. {len(raw_dataset)} productos brutos obtenidos de Walmart.")

        if not raw_dataset:
            Actor.log.warning("No se obtuvieron resultados de Walmart para procesar.")
            await Actor.push_data([])
            return
        
        # FASE 2: Pre-filtrado (Noise Removal)
        candidates = []
        for item in raw_dataset:
            title = item.get("productTitle") or item.get("title", "")
            description = item.get("description", "")
            
            if is_hardware_device(title, description):
                candidates.append(item)
            else:
                Actor.log.info(f"Omitido (Fase 2 - Consumible/Sin hardware): {title}")

        Actor.log.info(f"Fase 2 completada: {len(candidates)} candidatos seleccionados de {len(raw_dataset)} productos")

        # FASES 3 Y 4.1: Mapeo de Taxonomía y Agrupación Canónica
        grouped_devices = {}
        for item in candidates:
            raw_title = item.get("productTitle") or item.get("title", "")
            
            raw_brand = extract_brand_from_title(raw_title)
            brand_code = re.sub(r'[^a-z0-9]', '_', raw_brand.lower())
            
            device_id = create_canonical_key(brand_code, raw_title)
            
            processed_record = {
                "device_id": device_id,
                "brand_code": brand_code,
                "title": raw_title,
                "url": item.get("productUrl") or item.get("url", ""),
                "product_id": item.get("productId", ""),
                "price": item.get("price") or item.get("salePrice", 0),
                "asin_sku": item.get("productId", ""),
                "reviews_count": item.get("reviewCount", 0),
                "rating": item.get("rating", 0),
                "pack_format_code": "starter_kit" if "starter kit" in raw_title.lower() else "device_only",
                "seller": item.get("seller", ""),
                "image_url": item.get("image", ""),
                "raw_claims": item.get("claims", []),
                "classification_status": "mapped" if brand_code != "unknown_brand" else "review_required"
            }

            if device_id not in grouped_devices:
                grouped_devices[device_id] = []
            grouped_devices[device_id].append(processed_record)

        Actor.log.info(f"Fases 3-4.1 completadas: {len(grouped_devices)} dispositivos únicos agrupados")

        # FASE 4.2: Selección del Master Record (Deduplicación)
        master_records = []
        for device_id, records in grouped_devices.items():
            records.sort(
                key=lambda x: (
                    1 if x["pack_format_code"] in ["starter_kit", "device_only"] else 0,
                    x["reviews_count"]
                ),
                reverse=True
            )
            
            master = records[0]
            master["associated_variant_skus"] = [r["asin_sku"] for r in records[1:] if r.get("asin_sku")]
            master["variant_count"] = len(records)
            
            master_records.append(master)

        # FASE 5: Exportación de Resultados
        await Actor.push_data(master_records)
        Actor.log.info(f"Procesamiento finalizado. Dispositivos únicos guardados: {len(master_records)}")

if __name__ == '__main__':
    asyncio.run(main())
