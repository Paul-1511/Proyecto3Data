# HANDOFF - Persona 4: cierre e integración

## Entrega cerrada

- Rama: `p4/reto-integracion`.
- Punto de partida verificado: tag `handoff-p3`; lectura completa de `HANDOFF_P1.md`, `HANDOFF_P2.md`, `HANDOFF_P3.md` y `docs/data_contract.md`.
- Paquete sin datos: `outputs/observatorio-inguat-sin-datos.zip` (validado con `unzip -t`; excluye `data/raw/`, `data/processed/` y `.git/`).

## Módulo 4

`app/modulo4.py` implementa el reto territorial de Cobán y Alta Verapaz:

1. Perfil territorial: promedio mensual y proporción de visitantes de más de un día por Cobán, Lanquín y Cuevas de Candelaria.
2. Intensidad de sábado: presencia diaria de sábado frente a lunes-viernes; no se usa para derivar visitantes mensuales.
3. Mercado emisor extranjero principal por subdestino.

El módulo mantiene el tipo y período globales, pero intencionalmente conserva los tres subdestinos para permitir el contraste. No genera un total de destino. Sus fichas están en `docs/fichas_modulo4.md` y las pruebas en `tests/test_modulo4.py`.

## Integración y calidad

- Paleta consistente y mensajes clave por módulo; no hay barra de exportación ni tablas masivas.
- `README.md` incluye inicio limpio y solución de problemas de Docker.
- `docs/checklist_final.md` documenta las trece reglas y evidencias.
- `docs/memoria_tecnica.md` y `docs/memoria_tecnica.pdf` contienen la memoria final con las diez secciones solicitadas.
- Pruebas: `python3 -m pytest -q` -> **256 passed, 8 skipped**.
- Prueba de instalación limpia: ETL correcto desde cinco archivos fuente. La imagen se construyó desde cero con `docker compose up --build -d`; el tablero respondió HTTP 200 y el healthcheck quedó `healthy` en `http://localhost:8050`.
- La imagen conserva raíz de solo lectura y usa `HOME=/tmp` para que Gunicorn pueda abrir su socket temporal sin escribir en un directorio persistente.

No hay pendientes operativos ni metodológicos.
