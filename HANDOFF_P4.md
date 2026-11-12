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
- Prueba de instalación limpia: ETL correcto desde cinco archivos fuente. Docker Compose validó configuración, pero el motor Docker local estaba apagado y no permitió levantar el contenedor. Abrir Docker Desktop y ejecutar `docker compose up --build` resuelve ese único bloqueo externo.

## Pendiente operativo

Tras iniciar Docker Desktop, ejecutar desde una clonación limpia:

```bash
python -m etl.run_all
docker compose up --build
```

Abrir `http://localhost:8050` y comprobar las cuatro pestañas. No hay cambios metodológicos pendientes.
