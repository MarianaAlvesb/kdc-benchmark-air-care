import re
from apify import Actor

# Palabras clave para la Fase 2: Filtros de exclusión e inclusión
REFILL_KEYWORDS = ['refill', 'refills', 'cartridge', 'oil bottle', 'canister', 'replacement']
DEVICE_KEYWORDS = ['warmer', 'device', 'unit', 'starter kit', 'diffuser', 'dispenser', 'plug-in unit', 'purifier', 'humidifier']

def is_hardware_device(title: str, description: str) -> bool:
    """Fase 2: Filtra consumibles y exige términos de hardware."""
    text = f"{title} {description}".lower()
    
    # Exigir términos obligatorios de dispositivo/hardware primero
    has_device_kw = any(kw in text for kw in DEVICE_KEYWORDS)
    if not has_device_kw:
        return False

    # Excluir solo si son recambios sueltos (si tiene término de hardware explícito como warmer o starter kit, se conserva)
    has_refill_kw = any(kw in text for kw in REFILL_KEYWORDS)
    if has_refill_kw and not any(k in text for k in ['starter kit', 'warmer', 'device', 'unit', 'diffuser']):
        return False
        
    return True

def create_canonical_key(brand_code: str, title: str) -> str:
    """Fase 4: Limpia el título (elimina fragancias/formatos) y genera el device_id."""
    clean_title = title.lower()
    # Eliminación de fragancias y formatos de paquete comunes
    clean_title = re.sub(
        r'(lavender|vanilla|linen|amber|citrus|pack of \d+|\d+ count|\d+ pk|white sage|mahogany|cinnamon|apples|juniper|teak|pumpkin|spice|ocean|gain|downy|april fresh|fresh linen|chamomile|rain water)',
        '',
        clean_title
    )
    # Generar slug limpio
    model_slug = re.sub(r'[^a-z0-9]+', '_', clean_title).strip('_')
    
    # Fallback si el slug quedó vacío tras la limpieza
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
        # Recuperar la entrada proporcionada al Actor
        actor_input = await Actor.get_input() or {}
        
        # Leer el raw_dataset del input
        raw_dataset = actor_input.get("raw_dataset", [])
        
        if not raw_dataset:
            Actor.log.warning("No raw_dataset found in input")
            await Actor.push_data([])
            return
        
        candidates = []

        # FASE 2: Pre-filtrado (Noise Removal)
        for item in raw_dataset:
            title = item.get("productTitle") or item.get("title", "")
            description = item.get("description", "")
            
            if is_hardware_device(title, description):
                candidates.append(item)
            else:
                Actor.log.info(f"Omitido (Fase 2 - Consumible/Sin hardware): {title}")

        Actor.log.info(f"Fase 2 completada: {len(candidates)} candidatos seleccionados de {len(raw_dataset)} productos")

        # FASES 3 Y 4: Taxonomía y Deduplicación
        grouped_devices = {}

        for item in candidates:
            raw_title = item.get("productTitle") or item.get("title", "")
            
            # Extraer marca del título del producto
            raw_brand = extract_brand_from_title(raw_title)
            brand_code = re.sub(r'[^a-z0-9]', '_', raw_brand.lower())
            
            # Generar la clave única de dispositivo (Fase 4.1)
            device_id = create_canonical_key(brand_code, raw_title)
            
            # Mapeo de taxonomía básico (Fase 3)
            processed_record = {
                "device_id": device_id,
                "brand_code": brand_code,
                "title": raw_title,
                "url": item.get("productUrl", ""),
                "product_id": item.get("productId", ""),
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

        Actor.log.info(f"Fase 3-4 completada: {len(grouped_devices)} dispositivos únicos identificados")

        # FASE 4.2: Selección del Master Record (Deduplicación)
        master_records = []
        
        for device_id, records in grouped_devices.items():
            # Ordenar por prioridad: 1. Starter Kit / Device Only | 2. Mayor número de reviews
            records.sort(
                key=lambda x: (
                    1 if x["pack_format_code"] in ["starter_kit", "device_only"] else 0,
                    x["reviews_count"]
                ),
                reverse=True
            )
            
            # Seleccionar el primer registro como Master Record
            master = records[0]
            # Guardar SKUs secundarios asociados
            master["associated_variant_skus"] = [r["asin_sku"] for r in records[1:] if r.get("asin_sku")]
            master["variant_count"] = len(records)
            
            master_records.append(master)

        # FASE 5: Guardar el resultado final limpio en la plataforma de Apify
        await Actor.push_data(master_records)
        Actor.log.info(f"Procesamiento finalizado. Dispositivos únicos guardados: {len(master_records)}")
