# AGENTS.md — guía de trabajo para agentes (cac-elrocho)

Aplicación de escritorio/web self-hosted para gestionar analíticas clínicas.
Repositorio público: `https://github.com/el-rocho/cac-elrocho` (GitHub Pages en
`docs/`, imágenes en GHCR y releases con instalador de Windows).

## Comandos canónicos

```bash
# PRUEBAS (obligatorio antes de dar por terminado cualquier cambio)
.venv/bin/python -m unittest discover -s tests

# Arranque en desarrollo (interfaz en http://localhost:8000)
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Datos DEMO (sintéticos). OJO: reset-demo y /backup/wipe BORRAN la base
# entera. Copia data/analiticas.db antes de usarlos y confirma con Javier si
# la aplicación puede tener datos reales o importados en ese momento.
curl -X POST http://127.0.0.1:8000/api/v1/backup/reset-demo

# Estilos del frontend (Tailwind). CI falla si el CSS generado no está commiteado
npm run build:styles
git diff --exit-code -- app/static/vendor/tailwind.min.css

# Contenedor
docker compose up -d --build
```

La suite (42 pruebas, ~5 s) es autosuficiente: crea una raíz de datos temporal,
carga los datos demo y no toca `data/` del repositorio. Equivale al paso `Run
tests` de `.github/workflows/docker-publish.yml`, que se ejecuta en cada push a
`main`, PR y etiqueta. No hay linter ni formateador configurados: la suite es el
único gate automático.

## Regla de privacidad (no negociable)

**Nunca publicar en GitHub nombres reales de pacientes ni de médicos, ni números
de documentos de identidad (DNI/NIE/pasaporte).** Aplica a todo lo que se sube o
se hace público: commits (código, comentarios, docstrings, datos de prueba),
README, CHANGELOG, `docs/`, capturas de pantalla, nombres de archivo, mensajes de
commit, issues, PR, releases y notas de versión.

- Los **datos clínicos numéricos pueden ser reales** (valores, unidades, rangos de
  referencia, fechas, laboratorios): lo que se anonimiza son las personas, no los
  resultados. Política acordada con Javier.
- Se anonimizan siempre: el nombre del paciente (usar «Paciente Ejemplo (Modo
  Demo)» o «el-rocho»), el nombre de cualquier facultativo (usar ficticios, como
  los de `app/seed_data.py`: «Dra. Miriam Salas», «Dr. Iván Bermejo») y el
  DNI/NIE/nº de documento (`00000000T`, `X0000000X`). Los nombres de laboratorios
  y hospitales reales están permitidos.
- Evitar los metadatos que identifican un informe concreto: nº de
  referencia/petición y nombres de archivo PDF reales. En la base DEMO se usan
  referencias ficticias (`DEMO-AAAA-NNN`).
- Datos de ejemplo permitidos (los de `app/seed_data.py`): «Paciente Ejemplo
  (Modo Demo)», «Paciente Sintético», DNI `00000000T`, NIE `X0000000X`,
  laboratorios y facultativos ficticios como «Laboratorio Central Demo».
- Nombres de médicos reales extraídos de informes tampoco se copian a ejemplos,
  docstrings ni prompts del código.
- Nunca neutralizar el `.gitignore` ni usar `git add -f` para incorporar
  `data/`, `inbox/`, `backups/`, `logs/`, `config/`, `*.pdf`, `*.csv`,
  `*.xlsx`, `*.db*`, `*.sqlite*` ni credenciales. `tests/test_gitignore_privacy.py`
  verifica que esos patrones siguen cubiertos y que no hay ficheros
  sensibles rastreados por Git.
- Las capturas de pantalla para `docs/` y el README se toman con la base DEMO
  (`reset-demo`) o, como mínimo, con nombres y documentos anonimizados; antes de
  publicar se inspecciona el PNG para confirmar que no aparece ningún nombre real.
- Antes de cada commit: `git status --short` y revisar el diff completo. Si el
  diff toca `docs/assets/*.png` o cualquier binario, inspeccionar visualmente el
  contenido antes de publicar.
- Si se descubre un dato real ya publicado: parar, avisar a Javier con la ruta y
  el contenido afectado, y **no reescribir el historial de Git por iniciativa
  propia**.
- Los secretos (`.env`, `config/llm-credentials.json`, `*.key`) no se leen, no se
  copian a prompts, parches, commits ni respuestas, y no entran en SQLite ni en
  las copias de seguridad de la aplicación.

## Arquitectura (mapa rápido)

- `app/main.py`: FastAPI, ciclo de vida (init de BD, backfill de hashes,
  armonización, watcher de `/inbox`) y servido del frontend estático.
- `app/api/`: routers REST bajo `/api/v1` — `analiticas.py` (panel, histórico,
  gráficos, tablas), `upload.py` (PDF/CSV, previsualización, confirmación),
  `ai_review.py` (revisión LLM), `settings.py`, `backup.py` (exportar, importar,
  `wipe`, `reset-demo`).
- `app/services/`: lógica pesada — extracción (`analito_normalizer.py`,
  `parser.py`), LLM multiproveedor (`llm_service.py`), tendencias y cálculos
  clínicos (`clinical_trends.py`), métricas, armonización de unidades, copias de
  seguridad y `secret_store.py` para claves.
- `app/models.py` + `app/database.py`: SQLAlchemy sobre SQLite en modo WAL con
  PRAGMA de FK y timeout. El esquema evoluciona con migraciones **aditivas e
  idempotentes** (`SQLITE_COLUMN_MIGRATIONS`); nunca recrear ni borrar tablas con
  datos clínicos.
- `app/paths.py` + `app/config.py`: `APP_DATA_DIR` es la única raíz de datos
  (`data/`, `uploads/`, `inbox/`, `backups/`, `config/`, `logs/`). En Docker es
  `/app`; ejecutando desde el clon es la raíz del repositorio. No introducir
  rutas nuevas fuera de `AppPaths`.
- `app/static/`: frontend sin build (`index.html` + `app.js` + Chart.js vendido),
  salvo el CSS de Tailwind, que se genera y se versiona.
- `app/seed_data.py`: datos DEMO sintéticos, base del modo demostración.
- `tests/`: regresiones clínicas, migraciones, arquitectura de configuración y
  extracción. `tests/test_support.py` fija el entorno temporal de la suite.
- `launcher.py` y `packaging/`: ejecutable de escritorio (PyInstaller) e
  instalador Inno Setup para Windows.

## Capturas de pantalla para la documentación

- Ancho de referencia de las capturas existentes: 1273 px. Lee las dimensiones del
  PNG a reemplazar con `struct.unpack('>II', open(png,'rb').read()[16:24])`.
- Con la app levantada, fija el viewport (`Emulation.setDeviceMetricsOverride`,
  ancho 1273, `deviceScaleFactor` 1) y navega a `http://127.0.0.1:8000`; cambia de
  pestaña clicando su botón en la barra superior.
- Si la página es más corta que scroll máximo + viewport (p. ej. la base DEMO tiene
  5 informes), la barra de pestañas no se puede llevar a la fila 0: captura con
  `Page.captureScreenshot` y `clip` desde la barra de pestañas hasta el final del
  panel.
- Usa timeouts largos: los auxiliares del harness esperan 5 s por respuesta IPC y
  fallan bajo carga; `cdp(..., _response_timeout=120)` sí responde.
- Tras modificar `app/seed_data.py` hay que reiniciar el servidor: el proceso en
  marcha conserva el módulo antiguo en memoria y sirve datos obsoletos.
- Antes de publicar, inspecciona el PNG (visión) para descartar nombres reales.
  Receta completa: skill `local-webapp-doc-screenshots`.

## Convenciones

- Idioma del proyecto: español en UI, documentación y mensajes de commit.
- Tarjetas de valoración clínica de la pestaña «1. Información»: máximo **cuatro
  viñetas** por tarjeta (constante `MAX_DETERMINACIONES_TARJETA` en
  `app/static/app.js`) y el contador «+ N determinaciones» se calcula en
  `syncClinicalCards()` contando las determinaciones de la plantilla
  `eval-tpl-<área>` que abre el modal: no escribir ese número a mano. Si las
  viñetas ya cubren todas las determinaciones del modal (caso de función
  tiroidea), la tarjeta no lleva contador numérico sino una nota cualitativa.
- No hacer commit ni push sin autorización explícita: `main` publica imagen
  Docker, Pages y, con etiqueta, releases con instalador.
- Cambios quirúrgicos: no reformatear archivos completos ni tocar finales de
  línea (el repositorio mezcla LF y CRLF en algunos ficheros).
- `app/services/llm_service.py` mezcla LF y CRLF: la herramienta de parches
  reescribe el archivo entero y genera un diff de miles de líneas. Editarlo a
  nivel de bytes (`read_bytes()` + `replace()`) y comprobar siempre
  `git diff --numstat`; si aparece ruido de finales de línea, `git checkout --`
  sobre el archivo y repetir la edición.
- Los textos clínicos, avisos médicos y umbrales de referencia son sensibles:
  modificarlos requiere justificación explícita y prueba que lo cubra.
- Toda funcionalidad nueva o corregida debe llegar con su prueba en `tests/`.
