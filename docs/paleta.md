# Paleta y tema visual

Fuente única de verdad: `app/theme.py`. Este documento explica los colores y su uso.
El contraste AA se verifica con `tests/test_app_base.py` (pares definidos en `PARES_TEXTO_AA`).

## Colores

| Rol | Nombre en código | HEX | Uso |
|---|---|---|---|
| Dato observado (primario) | `COLOR_OBSERVADO` | `#0072B2` | Series y barras de dato observado. |
| Extranjeros | `COLOR_EXTRANJERO` | `#0072B2` | Universo de visitantes extranjeros en comparativas por tipo. |
| Nacionales | `COLOR_NACIONAL` | `#009E73` | Universo nacional expandido por telefonía; se muestra con escala propia. |
| Categórico 1–5 | `CATEGORICOS` | `#0072B2` `#009E73` `#56B4E9` `#CC79A7` `#44546A` | Comparar categorías (tipo, subdestino, mercado). |
| Secuencial (volumen) | `SECUENCIAL` | `#EAF2F8` `#C6DBEF` `#9ECAE1` `#6BAED6` `#3182BD` `#08519C` | Mapas de calor y barras por magnitud (claro = poco). |
| **Estimación** | `COLOR_ESTIMACION` | `#D55E00` | Línea/marcadores de estimaciones. **Exclusivo.** |
| Estimación, banda | `COLOR_ESTIMACION_BANDA` | `rgba(213,94,0,0.18)` | Banda de error del pronóstico. |
| Estimación, texto | `COLOR_ESTIMACION_TEXTO` | `#A33F00` | Rótulos «Estimación» (variante oscura, cumple AA). |
| Sin dato (relleno) | `COLOR_SIN_DATO` | `#9AA0A6` | Huecos, celdas sin cobertura. No usar para texto. |
| Sin dato (texto) | `COLOR_SIN_DATO_TEXTO` | `#5F6368` | Rótulo «Sin dato». |
| Texto | `TEXTO` / `TEXTO_SECUNDARIO` | `#1F2933` / `#4B5563` | Texto principal y secundario. |
| Encabezado | `ENCABEZADO` + `TEXTO_SOBRE_ENCABEZADO` | `#0B3C5D` + `#FFFFFF` | Barra superior institucional. |
| Fondos | `FONDO` / `FONDO_PAGINA` | `#FFFFFF` / `#F5F7FA` | Gráficos / página. |

## Justificación

- **Categórica:** parte de la paleta Okabe-Ito (Okabe e Ito, 2008), diseñada para ser distinguible con
  las formas comunes de daltonismo. Se descartan el naranja y el amarillo para no acercarse al color
  de estimación y por su bajo contraste sobre blanco. No se hizo una simulación automática de
  daltonismo; por eso la estimación añade una señal no cromática (línea punteada, banda y rótulo).
- **Secuencial:** una sola gama (azul) con luminosidad creciente: la magnitud se lee por claridad,
  no por tono, lo que funciona también en escala de grises y con daltonismo. Comparte el tono del
  color observado, de modo que «más oscuro» siempre es «más volumen observado».
- **Estimación:** un solo tono (bermellón) contrastante con todo el resto del tablero y reservado
  únicamente a cifras estimadas (regla 5). Ningún color categórico ni secuencial se le parece; una
  prueba verifica que sea disjunto de las demás paletas. La variante oscura `#A33F00` existe porque
  `#D55E00` sobre blanco no alcanza 4.5:1 como texto.
- **Sin dato:** gris neutro, sin tono, para que la ausencia nunca se confunda con un valor (regla 1).
  Se usa una variante más oscura para texto.
- **Contraste:** todo texto usa los pares de `PARES_TEXTO_AA` (razón ≥ 4.5:1, WCAG 2.x AA).
  Los colores de relleno (`COLOR_SIN_DATO`, `COLOR_ESTIMACION`, categóricos claros) no deben usarse
  como color de texto.
- **Comparación de tipos:** azul identifica a extranjeros y verde a nacionales. Cuando se muestran
  juntos, el gráfico conserva un eje vertical para cada universo y una leyenda interactiva; los
  valores no se suman ni se comparan como si fueran la misma unidad de medición.
- **Series por año:** en comparativas temporales, 2023 usa azul claro y círculo, 2024 verde y
  cuadrado discontinuo, y 2025 magenta y rombo punteado. Así, las series siguen siendo
  distinguibles cuando se cruzan o se ven en escala de grises.

## Plantilla Plotly

`theme.PLANTILLA` (registrada como `observatorio`): fuente `Inter/Segoe UI/Roboto`, tamaño 13, `colorway` =
`CATEGORICOS`, fondo blanco, grilla gris clara, leyenda horizontal bajo el gráfico, márgenes
`l=56 r=24 t=72 b=56`, título alineado a la izquierda, escala secuencial por defecto.

## Utilidades

| Función | Propósito |
|---|---|
| `subtitulo_periodo(ini, fin, fuente)` | Subtítulo «Período: sep 2025 – dic 2025 · Fuente: …» (regla 11). |
| `titulo_con_subtitulo(titulo, subtitulo)` | Título Plotly con subtítulo en segunda línea. |
| `figura_sin_dato(titulo, periodo)` | Figura con el rótulo «Sin dato», sin trazos. |
| `rotulo_estimacion(texto)` | «Estimación» o «<texto> · Estimación». |
| `estilo_estimacion()` | Línea punteada y banda con el color exclusivo de estimación. |
| `aplicar_plantilla(fig)` | Aplica la plantilla común. |
| `razon_contraste`, `cumple_aa` | Comprobación de contraste WCAG. |
