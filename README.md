# cac-elrocho 🩺 `v0.4.0`

> **Cuadro de Mando Clínico Autónomo y Autoalojable con Validación por Inteligencia Artificial (LLM)**

`cac-elrocho` es una aplicación web integral y soberana diseñada para la digitalización, seguimiento evolutivo y supervisión longitudinal de analíticas médicas y controles de laboratorio. 

Diseñada para ser ejecutada de manera autónoma y multiplataforma mediante **Docker** (en **Windows** con Docker Desktop, **Linux** como Debian 13 / Ubuntu en servidores o máquinas virtuales, y **macOS**), la aplicación almacena el historial médico en una base de datos local SQLite (WAL), calcula ratios aterogénicos y metabólicos automáticos, y utiliza modelos LLM multimodales (**Google Gemini API**) para procesar nuevos informes en PDF, auditar cambios en rangos de referencia y emitir recomendaciones clínicas.

---

## ✨ Novedades de la Versión `v0.4.0`
* 🤖 **Arquitectura Multi-Modelo LLM (3 Slots)**: Control soberano desde `.env` para configurar hasta 3 modelos con sus respectivas claves (`LLM_PROVIDER1..3`, `API_KEY1..3`, `MODEL1..3`).
* 🔄 **Failover Secuencial y Contingencia RegEx**: Conmutación automática e inmediata ante límites de cuota (`429 ResourceExhausted`), modelos discontinuados (`404`) o sobrecargas transitorias (`503`). Si todos fallan, conmuta de forma segura al extractor local por patrones RegEx.
* 🏷️ **Transparencia en la Interfaz (UI)**: Etiqueta dinámica en cabecera (`✨ Motor LLM Activo (N mod.)` o `⚠️ Extractor RegEx (Sin LLM)`) y banner de previsualización que identifica el slot y modelo exacto utilizado o la contingencia activa.
* 🩺 **Sanitización Clínica de Metadatos**: Desacoplamiento estricto del médico solicitante (facultativo) respecto a motivos de consulta / revisiones y separación limpia del nombre del laboratorio emisor.
* 📏 **Auditoría Simplificada**: Interfaz renovada para "Auditoría de los rangos de referencia aplicados", con tarjetas a 3 líneas y criterios desplegables en acordeón.
* 📋 *Consulta el historial completo de cambios en [CHANGELOG.md](CHANGELOG.md).*

---

## 🚀 Características Principales

* 📊 **Panel de Control Integral**: Tarjetas KPI, 8 gráficos evolutivos interactivos con Chart.js y tabla de resultados completa con promedio reciente a 18 meses.
* 👤 **Ficha Personal del Paciente**:
  * Configuración soberana y privada de datos personales: **Nombre**, **Documento de Identidad (DNI/NIE)**, **Fecha de Nacimiento** (con cálculo dinámico de edad cumplida) y **Sexo** (Masculino / Femenino / No especificado).
  * Los datos de configuración son privados y nunca son sobreescritos por los informes médicos que se suban.
* 🤖 **Copiloto Clínico con IA (Gemini API)**:
  * Ingesta inteligente de documentos PDF clínicos.
  * **Auditoría de Rangos de Referencia**: Detecta si un laboratorio ha actualizado sus límites de normalidad (por ejemplo, el dintel de LDL de 130 a 116 mg/dL según guías SEA 2023) y explica el motivo clínico.
  * Detección de prediabetes (HbA1c ≥ 5.7%) y semaforización clínica rigurosa.
* 🛡️ **Detección y Control de Analíticas Duplicadas**:
  * Verificación criptográfica por hash **SHA-256** de los archivos PDF subidos y comprobación de colisión por fecha/laboratorio.
  * Banner informativo y selector de acción inteligente: opción de **sobrescribir/actualizar** el informe existente o guardarlo como nueva analítica independiente.
* 🛡️ **Validación de Identidad Flexible (Human-in-the-Loop)**:
  * Comprobación tolerante de identidad entre el informe PDF y el paciente configurado (ignora orden de apellidos/nombre, tildes, mayúsculas y ceros a la izquierda en el DNI).
  * En caso de discrepancia real (por ejemplo, si se sube por error el informe de otra persona), emite una advertencia previa no bloqueante en el modal de revisión.
* 🔐 **Panel de Gestión y Respaldo de Datos**:
  * **Exportación con Marca Temporal**: Descarga copias de seguridad completas en JSON con fecha y hora (`cac-elrocho-backup-YYYYMMDD_HHMMSS.json`) y soporte para **cifrado simétrico AES-256-GCM**.
  * **Importación y Restauración Completa**: Restaura copias de seguridad (planas o cifradas) con sustitución limpia y sin duplicidades.
  * **Purga y Modo Demo**: Posibilidad de vaciar la base de datos para empezar de cero o cargar datos sintéticos de prueba.
* 📁 **Buzón Desatendido (`/inbox`)**: Monitor de carpetas en segundo plano para procesar PDFs subidos vía SFTP, Samba o Nextcloud.
* 🔒 **Privacidad Total**: Documentos originales, bases de datos SQLite y claves de API estrictamente excluidos del control de versiones (`.gitignore`).
* 🤖 **CI/CD y Mantenimiento Automatizado**: Integración continua con **GitHub Actions**, publicación en **GitHub Container Registry (GHCR)** y soporte nativo para **Dependabot**.

---

## 🛠️ Requisitos del Sistema

* **Sistema Operativo**:
  * **Windows**: Windows 10/11 con [Docker Desktop](https://www.docker.com/products/docker-desktop/) (backend WSL2 recomendado).
  * **Linux**: Debian 13 (Trixie), Ubuntu 22.04+ o cualquier distribución Linux con Docker.
  * **macOS**: Docker Desktop para macOS.
* **Recursos Mínimos**:
  * 1 vCPU / Procesador estándar
  * 1 GB de memoria RAM
  * 10 GB de almacenamiento disponible
* **Software**: Docker y Docker Compose (`docker compose`).

---

## 📦 Instalación y Despliegue con Docker Compose

### 1. Clonar el Repositorio
```bash
git clone https://github.com/el-rocho/cac-elrocho.git
cd cac-elrocho
```

### 2. Configurar Variables de Entorno
Copia la plantilla de configuración:
```bash
# En Linux / macOS:
cp .env.example .env

# En Windows (PowerShell / CMD):
copy .env.example .env
```
Edita el archivo `.env` con tu editor preferido (`nano .env`, Bloc de notas, VS Code, etc.) y define tus parámetros esenciales:
```ini
# Configuración multi-modelo LLM (hasta 3 modelos configurables con alternancia por fallo)
LLM_PROVIDER1=gemini
API_KEY1=tu_clave_de_gemini_api_aqui
MODEL1=gemini-flash-lite-latest

LLM_PROVIDER2=gemini
API_KEY2=tu_clave_de_gemini_api_aqui
MODEL2=gemini-2.5-flash

LLM_PROVIDER3=gemini
API_KEY3=tu_clave_de_gemini_api_aqui
MODEL3=gemini-2.5-flash-lite
```
*(Nota: Puedes configurar 1, 2 o los 3 modelos. Si dejas las claves vacías, los modelos fallan o no hay conexión a internet, la aplicación utilizará automáticamente el extractor local inteligente basado en expresiones regulares sin interrumpir el servicio).*

### 3. Levantar los Contenedores
Descarga la imagen precompilada en GitHub Actions y levanta el servicio sin consumir recursos de compilación en tu máquina:
```bash
docker compose pull
docker compose up -d
```
*(Nota: Si deseas compilar localmente desde el código fuente en lugar de usar la imagen precompilada, puedes usar `docker compose up -d --build`).*

Accede desde tu navegador a:
```
http://localhost:8000            # Si lo ejecutas en tu propio equipo (Windows, macOS o Linux)
http://IP_DE_TU_SERVIDOR:8000    # Si lo ejecutas en un servidor remoto o máquina virtual
```

---

## 🔄 Actualización Rápida en el Servidor (Sin Compilar)

Con el flujo de **GitHub Actions** configurado, cada versión etiquetada (`v0.4.0`) y cambio en `main` genera automáticamente la imagen en **GitHub Container Registry (GHCR)**. Para actualizar tu servidor en segundos:

```bash
cd cac-elrocho
git pull
docker compose pull
docker compose up -d
docker image prune -f
```

> [!NOTE]
> **Autenticación en GHCR (solo si el paquete es privado)**:
> Si el paquete en GitHub Packages es privado, solo necesitas autenticarte una vez en el servidor con un Personal Access Token (PAT con permiso `read:packages`):
> ```bash
> echo "TU_GITHUB_PAT" | docker login ghcr.io -u TU_USUARIO_GITHUB --password-stdin
> ```
> Si el paquete está configurado como **Público** (*Package settings > Danger Zone > Change package visibility*), no se requiere ninguna autenticación.

---

## ⚙️ Primeros Pasos y Configuración

1. Dirígete a la pestaña **⚙️ 5. Configuración y Datos** en la barra superior.
2. En la sección **Datos Personales del Paciente**, introduce tu Nombre, DNI, Fecha de Nacimiento y Sexo y pulsa en `Guardar Datos del Paciente`.
3. Ahora puedes:
   * **Subir tus analíticas**: Pulsa en el botón azul de la cabecera `➕ Subir Nueva Analítica (PDF)` o arrastra archivos.
   * **O restaurar una copia previa**: En la pestaña de configuración, selecciona tu archivo `.json` de respaldo y pulsa en `Restaurar Respaldo`.
   * **Explorar con datos demo**: Si deseas probar las gráficas antes de cargar tus análisis reales, pulsa en `Restablecer Datos de Demostración (Demo)`.

---

## 🌐 Configuración HTTPS Automática con Caddy (Opcional)

Si deseas exponer la aplicación en un servidor público o dominio con certificado SSL/HTTPS Let's Encrypt automático:

1. Descomenta el servicio `caddy` en `docker-compose.yml`.
2. Crea un archivo `Caddyfile` en la raíz del proyecto:
```caddy
tudominio.com {
    reverse_proxy app:8000
}
```
3. Reinicia los contenedores con `docker compose up -d`.

---

## 💻 Desarrollo y Ejecución Local (sin Docker)

Si prefieres ejecutar la aplicación de forma nativa con Python:

### En Windows:
```cmd
.\dev.bat
```
*(El script `dev.bat` creará automáticamente el entorno virtual, instalará las dependencias si no existen y arrancará el servidor en http://localhost:8000).*

### En Linux / macOS:
```bash
# 1. Crear entorno virtual
python3 -m venv venv
source venv/bin/activate

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Iniciar servidor de desarrollo
uvicorn app.main:app --reload --port 8000
```

---

## 📄 Licencia y Aviso Médico
Desarrollado para la gestión y seguimiento personal de salud. Los dictámenes y avisos generados por el LLM tienen carácter exclusivamente informativo y de apoyo, y no sustituyen el criterio de un médico especialista colegiado.

