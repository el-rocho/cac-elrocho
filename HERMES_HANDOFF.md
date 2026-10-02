# Traspaso del proyecto a una VM con Hermes Agent

Esta guía describe cómo reproducir en una VM el estado de trabajo local de este
proyecto sin confundir código, datos clínicos y secretos. Está pensada como
contexto inicial para un agente que vaya a continuar el desarrollo.

## Estado de partida

- Repositorio remoto: `https://github.com/el-rocho/cac-elrocho.git`.
- El árbol de trabajo local contiene cambios **sin confirmar** en `README.md`,
  la configuración de LLM, la API de ajustes, el esquema, la interfaz y sus
  pruebas. El trabajo amplía la configuración de IA a Gemini, OpenAI y
  DeepSeek. No debe asumirse que GitHub contiene esos cambios.
- La aplicación es FastAPI con SQLite, interfaz estática y Docker Compose.
  El comando de validación habitual es `python -m unittest discover -s tests`.
- En Docker, la raíz persistente es `/app` y los volúmenes del repositorio se
  montan como `data`, `inbox`, `config`, `backups` y `logs`.

## Qué entregar a Hermes

Entregar tres piezas independientes. No se deben mezclar los secretos con el
archivo que se vaya a compartir con un agente o a guardar en una ubicación no
cifrada.

| Pieza | Contenido | Finalidad |
| --- | --- | --- |
| `source` | Clon de GitHub y un parche binario de los cambios locales | Código exacto, incluido el trabajo no publicado. |
| `data` | Directorios `data/`, `inbox/`, `backups/` y `logs/` | Base SQLite, adjuntos, PDFs de referencia y material de prueba. |
| `config` | `config/config.json` | Selección de proveedores/modelos sin claves. |

Los ficheros de datos contienen información clínica personal. Transfiérelos
sólo mediante una carpeta compartida de la VM protegida o un archivo cifrado.
Para que Hermes pueda depurar la extracción, `data/uploads/` y
`data/pdfs_referencia_validados/` son especialmente valiosos; contienen los
PDF que explican los casos reales de parsing.

## Qué no transferir por defecto

- `.env`: puede contener contraseña de administración y `SECRET_KEY`.
- `config/llm-credentials.json` y `config/llm-credentials.key`: contienen las
  claves API de los proveedores.
- Entornos virtuales (`venv/`, `.venv*/`), `node_modules/`, `build/`, `dist/`
  y `dist-installer/`: se regeneran en la VM.
- Archivos PDF, CSV, XLSX u ODS sueltos de la raíz: son material privado y
  duplican parcialmente el contenido de `data/`; inclúyelos sólo si Hermes va
  a trabajar precisamente con esos ejemplos.

En la VM configura las claves mediante la interfaz de la aplicación o por su
gestor de secretos. No incluyas claves reales en prompts, commits, parches ni
capturas de pantalla.

## Preparación en el equipo origen

1. Cierra la aplicación o detén el contenedor antes de copiar la base. Esto
   evita separar `analiticas.db` de sus ficheros `-wal` y `-shm`.

   ```powershell
   docker compose stop app
   ```

2. Captura los cambios locales, incluidos los cambios binarios si los hubiera:

   ```powershell
   git diff --binary | Set-Content -Encoding utf8 local-changes.patch
   git status --short
   ```

   Si hubiera ficheros de código nuevos no rastreados, cópialos al paquete
   `source` o añádelos explícitamente al control de versiones antes de crear
   el parche. El comando anterior sólo cubre archivos ya rastreados.

3. Copia a un medio protegido los directorios `data`, `inbox`, `backups`,
   `logs`, el archivo `config/config.json`, `local-changes.patch` y este
   documento. Conserva juntos `analiticas.db`, `analiticas.db-wal` y
   `analiticas.db-shm` cuando existan.

4. Cuando la copia esté verificada, vuelve a levantar el servicio si procede:

   ```powershell
   docker compose start app
   ```

> Una alternativa más limpia para llevar sólo el historial publicado es
> `git bundle create cac-elrocho.bundle --all`. Aun así se necesita
> `local-changes.patch` para transportar el trabajo que no está en GitHub.

## Restauración en la VM

En Debian/Ubuntu con Docker:

```bash
git clone https://github.com/el-rocho/cac-elrocho.git cac-elrocho
cd cac-elrocho
git apply --check /ruta/segura/local-changes.patch
git apply /ruta/segura/local-changes.patch
cp /ruta/segura/config.json config/config.json
cp -a /ruta/segura/data /ruta/segura/inbox /ruta/segura/backups /ruta/segura/logs .
cp .env.example .env
docker compose up -d --build
```

Si se usa un `git bundle`, sustituye el clonado por `git clone
cac-elrocho.bundle cac-elrocho`. Comprueba el estado tras aplicar el parche:

```bash
git status --short
docker compose ps
docker compose logs --tail=100 app
```

No copies los ficheros de credenciales. Configura en la interfaz los slots de
LLM de nuevo y confirma que las llamadas de prueba se hacen con claves
propias de la VM.

## Contexto técnico útil para Hermes

- `app/paths.py` centraliza las rutas persistentes y `APP_DATA_DIR` es la raíz
  canónica. No añadir rutas independientes sin actualizar esa abstracción.
- `app/services/secret_store.py` separa claves de la configuración normal.
  `config/config.json` guarda metadatos; las claves no deben entrar en SQLite
  ni en copias de seguridad de la aplicación.
- La interfaz vive en `app/static/index.html` y `app/static/app.js`; el CSS
  distribuido ya está versionado en `app/static/vendor/tailwind.min.css`.
- Las pruebas cubren regresiones clínicas, migraciones de base y arquitectura
  de configuración. Ejecutarlas antes de continuar y antes de publicar.
- La configuración de producción se monta mediante `docker-compose.yml`;
  exponer el puerto 8000 de la VM a Internet requiere autenticación,
  `SECRET_KEY` y HTTPS configurados de forma deliberada.

## Comprobación de integridad recomendada

Después de transferir, compara hashes de las piezas sensibles desde ambos
equipos (sin publicar los archivos):

```powershell
Get-FileHash data\analiticas.db, local-changes.patch -Algorithm SHA256
```

```bash
sha256sum data/analiticas.db local-changes.patch
```

Si el objetivo es sólo que Hermes revise o continúe el código, basta con el
clon y `local-changes.patch`; no entregues los datos clínicos. Si debe
reproducir problemas de extracción o cambios de esquema, entrégale también
el paquete de datos en un canal cifrado y controlado.
