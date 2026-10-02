# Traspaso del proyecto a una VM con Hermes Agent

Esta guía describe cómo reproducir en una VM el estado de trabajo local de este
proyecto sin confundir código, datos clínicos y secretos. Está pensada como
contexto inicial para un agente que vaya a continuar el desarrollo.

## Estado de partida

- Repositorio remoto: `https://github.com/el-rocho/cac-elrocho.git`.
- En el momento de actualizar esta guía, la rama `main` local está sincronizada
  con GitHub. El soporte de Gemini, OpenAI y DeepSeek se publicó en
  `e4f17a8` (`Add OpenAI and DeepSeek LLM providers`), incluida su
  documentación en el README.
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
| `source` | Clon de GitHub en la rama `main` | Código publicado y documentación técnica. |
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

2. Comprueba que no haya trabajo local pendiente:

   ```powershell
   git status --short
   ```

   Una salida vacía significa que basta con clonar GitHub. Si hubiera cambios
   sin confirmar en el futuro, publícalos con commit y push antes del traspaso.
   Sólo si no se pueden publicar, crea un parche adicional:

   ```powershell
   git diff --binary | Set-Content -Encoding utf8 local-changes.patch
   ```

   Los ficheros nuevos no rastreados no entran en ese parche: añádelos a Git o
   cópialos explícitamente junto a él.

3. Copia a un medio protegido los directorios `data`, `inbox`, `backups`,
   `logs`, el archivo `config/config.json` y este documento. Conserva juntos
   `analiticas.db`, `analiticas.db-wal` y `analiticas.db-shm` cuando existan.
   Incluye `local-changes.patch` solamente en el caso excepcional anterior.

4. Cuando la copia esté verificada, vuelve a levantar el servicio si procede:

   ```powershell
   docker compose start app
   ```

> Si la VM no puede acceder a GitHub, crea un archivo portable del historial
> publicado con `git bundle create cac-elrocho.bundle --all`.

## Restauración en la VM

En Debian/Ubuntu con Docker:

```bash
git clone https://github.com/el-rocho/cac-elrocho.git cac-elrocho
cd cac-elrocho
cp /ruta/segura/config.json config/config.json
cp -a /ruta/segura/data /ruta/segura/inbox /ruta/segura/backups /ruta/segura/logs .
cp .env.example .env
docker compose up -d --build
```

Si se usa un `git bundle`, sustituye el clonado por `git clone
cac-elrocho.bundle cac-elrocho`. Si excepcionalmente existe un parche local,
aplícalo después del clonado con `git apply --check` y `git apply`.
Comprueba el estado al terminar:

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
Get-FileHash data\analiticas.db -Algorithm SHA256
```

```bash
sha256sum data/analiticas.db
```

Si se ha creado excepcionalmente `local-changes.patch`, calcula también su
hash por separado.

Si el objetivo es sólo que Hermes revise o continúe el código, basta con el
clon de GitHub; no entregues los datos clínicos. Si debe reproducir problemas
de extracción o cambios de esquema, entrégale también el paquete de datos en
un canal cifrado y controlado.
