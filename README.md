# Air Care Benchmark & Taxonomist Processor

Este Actor de Apify actúa como un procesador y taxonomizador de datos para la categoría **Air Care**. Toma datasets sin procesar (*raw datasets*) procedentes de scraping (ej. Walmart, Amazon) y aplica reglas de negocio para filtrar recambios, estandarizar marcas y crear registros únicos de dispositivos.

## Funcionalidades Principales

- **Filtrado Automático de Hardware:** Identifica y conserva únicamente dispositivos principales (purificadores, humidificadores, difusores, *plug-in warmers*, *starter kits*), descartando recambios/consumibles (*refills*, cartuchos, frascos sueltos).
- **Extracción y Normalización de Marca:** Detecta la marca a partir de los títulos y genera un código estándar (`brand_code`).
- **Generación de ID Canónico (`device_id`):** Crea un identificador único estandarizado para asociar diferentes variantes o SKUs bajo un mismo dispositivo.
- **Agrupación y Deduplicación:** Consolida variantes secundarias en el campo `associated_variant_skus`.

## Estructura del Proyecto

```text
.actor/
├── actor.json           # Configuración principal del Actor
├── input_schema.json    # Validación de la entrada (raw_dataset)
└── dataset_schema.json  # Esquema de visualización de los resultados en Apify
src/
├── __main__.py          # Punto de entrada del contenedor
└── main.py              # Lógica de filtrado, mapeo y consolidación de datos
Dockerfile               # Configuración del entorno Python 3.11
