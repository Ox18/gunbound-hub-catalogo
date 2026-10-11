# web-catalogo

Web estática (HTML, CSS y JS sin dependencias). Se abre con doble clic en `index.html`; no necesita servidor.

| Página | Qué es |
|---|---|
| `index.html` | Inicio con las tres secciones. |
| `funcionalidades.html` | El catálogo de funcionalidades del agente de GunBound (el del PDF `GunboundHUB-Catalogo`), con la barra de la web. |
| `avatares.html?juego=gb` / `?juego=db` | Avatares de GunBound (8.619, del cliente `gis/png`) y de DragonBound (6.348, capturados de dragonbound.net), con buscador y filtros por tipo, género y tienda. |

## Regenerar los avatares

```sh
~/gunbound/.venv/bin/python tools/build_avatars.py all   # o gb / db
```

Escribe `avatars/<gb|db>/*.webp` (primer cuadro de cada sprite, 96 px) y `data/avatars-<gb|db>.js`.
Lee los sprites de `~/gunbound/gis/png`, `~/gunbound/dragonbound/.../images/ava`, el storage del hub y
`data/src/` (copia de lo que el agente dejó en su carpeta temporal: `db_avatars.json`, `ava_dl/`,
`catalogo-a4.html` y su `avatares_pdf.py`).

`funcionalidades.html` es `data/src/catalogo-a4.html` envuelto en un documento completo con la barra de navegación
y una corrección: el visor de imágenes (`#viewer`) quedaba siempre abierto porque su `display: grid` le ganaba
al atributo `hidden`.
