import re
from apify import Actor

# Palabras clave para la Fase 2: Filtros de exclusión e inclusión
REFILL_KEYWORDS = ['refill', 'refills', 'cartridge', 'oil bottle', 'canister', 'replacement']
DEVICE_KEYWORDS = ['warmer', 'device', 'unit', 'starter kit', 'diffuser', 'dispenser', 'plug-in unit']

def is_hardware_device(title: str, description: str) -> bool:
    """Fase 2: Filtra consumibles y exige términos de hardware."""
    text = f"{title} {description}".lower()
    
    # Regla 2.1: Excluir recambios y consumibles
    if any(kw in text for kw in REFILL_KEYWORDS):
        return False
        
    # Exigir términos obligatorios de dispositivo
    if not any(kw in text for kw in DEVICE_KEYWORDS):
        return False
        
    return True

def create_canonical_key(brand_code: str, title: str) -> str:
    """Fase 4: Limpia el título (elimina fragancias/formatos) y genera el device_id."""
    clean_title = title.lower()
    # Eliminación de fragancias y formatos de paquete comunes
    clean_title = re.sub(r'(lavender|vanilla|linen|amber|citrus|pack of \d+|\d+ count|\d+ pk)', '', clean_title)
    # Generar slug limpio
    model_slug = re.sub(r'[^a-z0-9]+', '_', clean_title).strip('_')
    return f"{brand_code.lower()}_{model_slug}"

async def main() -> None:
    async with Actor:
        # Recuperar la entrada proporcionada al Actor
        actor_input = await Actor.get_input() or {}
        raw_dataset = actor_input.get("raw_dataset", [])
        
        candidates = []

        # FASE 2: Pre-filtrado (Noise Removal)
        for item in raw_dataset:
            title = item.get("title", "")
            description = item.get("description", "")
            
            if is_hardware_device(title, description):
                candidates.append(item)
            else:
                Actor.log.info(f"Omitido (Fase 2 - Consumible/Sin hardware): {title}")

        # FASES 3 Y 4: Taxonomía y Deduplicación
        grouped_devices = {}

        for item in candidates:
            raw_title = item.get("title", "")
            raw_brand = item.get("brand", "unknown_brand")
            brand_code = re.sub(r'[^a-z0-9]', '_', raw_brand.lower())
            
            # Generar la clave única de dispositivo (Fase 4.1)
            device_id = create_canonical_key(brand_code, raw_title)
            
            # Mapeo de taxonomía básico (Fase 3)
            processed_record = {
                "device_id": device_id,
                "brand_code": brand_code,
                "title": raw_title,
                "url": item.get("url", ""),
                "asin_sku": item.get("asin") or item.get("sku"),
                "reviews_count": item.get("reviewsCount", 0),
                "pack_format_code": "starter_kit" if "starter kit" in raw_title.lower() else "device_only",
                "raw_claims": item.get("claims", []),
                "classification_status": "mapped" if brand_code != "unknown_brand" else "review_required"
            }

            if device_id not in grouped_devices:
                grouped_devices[device_id] = []
            grouped_devices[device_id].append(processed_record)

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
            
            master_records.append(master)

        # FASE 5: Guardar el resultado final limpio en la plataforma de Apify
        await Actor.push_data(master_records)
        Actor.log.info(f"Procesamiento finalizado. Dispositivos únicos guardados: {len(master_records)}")
