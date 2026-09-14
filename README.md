# cac-elrocho 🩺

> **Cuadro de Mando Clínico Autónomo y Autoalojable con Validación por Inteligencia Artificial (LLM)**

`cac-elrocho` es una aplicación web integral diseñada para la gestión, seguimiento evolutivo y supervisión de analíticas médicas y controles de laboratorio. 

Diseñada para ser ejecutada de manera autónoma en una **máquina virtual con Debian 13** (o cualquier servidor con Docker), la aplicación almacena de forma soberana el historial médico en una base de datos local SQLite (WAL), calcula ratios aterogénicos y metabólicos automáticos, y utiliza un modelo LLM multimodal (**Google Gemini API**) para procesar nuevos informes en PDF, auditar cambios en rangos de referencia y emitir recomendaciones clínicas.

---

## 🚀 Características Principales

* 📊 **Panel de Control Integral**: Tarjetas KPI, 8 gráficos evolutivos interactivos con Chart.js y tabla bioquímica comparativa que destaca el promedio reciente frente al histórico global.
* 🧪 **Modo Demostración Seguro por Defecto**: La instalación incluye un conjunto sintético y demostrativo de pruebas para explorar todas las capacidades visuales e interactivas sin comprometer ningún dato personal.
* 🤖 **Copiloto Clínico con IA (Gemini API)**:
  * Ingesta inteligente de documentos PDF clínicos.
  * **Auditoría de Rangos de Referencia**: Detecta si un laboratorio ha actualizado sus límites de normalidad (por ejemplo, el dintel de LDL de 130 a 116 mg/dL según guías SEA 2023) y explica el motivo clínico.
  * Detección de prediabetes (HbA1c ≥ 5.7%) y semaforización clínica rigurosa.
* 🛡️ **Enfoque Human-in-the-Loop**: Modal de revisión previa donde el usuario verifica los datos extraídos por la IA antes de consolidarlos con un solo clic.
* 🔐 **Panel de Gestión y Respaldo de Datos**:
  * **Exportación Segura**: Descarga copias de seguridad completas en JSON con **cifrado simétrico AES-256-GCM** protegido por contraseña.
  * **Importación y Restauración**: Restaura copias de seguridad (planas o cifradas) en un clic.
  * **Purga de Datos / Puesta a Cero**: Botón para limpiar la base de datos y comenzar con tus propios datos privados.
* 📁 **Buzón Desatendido (`/inbox`)**: Monitor de carpetas en segundo plano para procesar PDFs subidos vía SFTP, Samba o Nextcloud.
* 🔒 **Privacidad Total**: Documentos originales, bases de datos y claves de API estrictamente excluidos del control de versiones (`.gitignore`).

---

## 🛠️ Requisitos del Sistema (Debian 13)

* **Sistema Operativo**: Debian 13 (Trixie) / Ubuntu 22.04+ / Cualquier distribución Linux con Docker.
* **Recursos Mínimos**:
  * 1 vCPU
  * 1 GB de memoria RAM
  * 10 GB de almacenamiento disponible
* **Software**: Docker y Docker Compose plugin (`docker compose`).

---

## 📦 Instalación y Despliegue con Docker Compose

### 1. Clonar el Repositorio
```bash
git clone https://github.com/el-rocho/cac-elrocho.git
cd cac-elrocho
```

### 2. Configurar Variables de Entorno
Copia la plantilla y configura tu clave de Gemini API:
```bash
cp .env.example .env
nano .env
```
Parámetros esenciales:
```ini
LLM_PROVIDER=gemini
GEMINI_API_KEY=tu_clave_de_gemini_api_aqui
GEMINI_MODEL=gemini-2.5-flash
```
*(Nota: Si dejas `GEMINI_API_KEY` vacío o usas `LLM_PROVIDER=mock`, la aplicación utilizará un motor de extracción inteligente local con patrones clínicos sin requerir conexión a internet).*

### 3. Levantar los Contenedores
```bash
docker compose up -d --build
```

La aplicación arrancará automáticamente en **Modo Demostración**.

Accede desde tu navegador a:
```
http://IP_DE_TU_MAQUINA_DEBIAN:8000
```

---

## ⚙️ Primeros Pasos con tus Propios Datos

1. Dirígete a la pestaña **⚙️ 7. Configuración y Datos** en la barra superior.
2. Pulsa en **⚠️ Limpiar Base de Datos (Comenzar de Cero)** para eliminar los datos demostrativos sintéticos.
3. Ahora puedes:
   * **Subir tus analíticas**: Pulsa en el botón azul de la cabecera `➕ Subir Nueva Analítica (PDF)`.
   * **O restaurar una copia previa**: En la misma pestaña de configuración, selecciona tu archivo `.json` de respaldo (e introduce la contraseña si lo cifraste) y pulsa en `Restaurar Respaldo`.

---

## 🌐 Configuración HTTPS Automática con Caddy (Opcional)

Si deseas exponer la aplicación con certificado SSL/HTTPS Let's Encrypt de forma automática en Debian 13:

1. Descomenta el servicio `caddy` en `docker-compose.yml`.
2. Crea un archivo `Caddyfile` en la raíz del proyecto:
```caddy
tudominio.com {
    reverse_proxy app:8000
}
```
3. Reinicia los contenedores con `docker compose up -d`.

---

## 💻 Desarrollo Local (sin Docker)

```bash
# Crear entorno virtual
python -m venv venv
# En Windows:
venv\Scripts\activate
# En Linux:
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Iniciar servidor de desarrollo
uvicorn app.main:app --reload --port 8000
```

---

## 📄 Licencia y Aviso Médico
Desarrollado para la gestión y seguimiento personal de salud. Los dictámenes y avisos generados por el LLM tienen carácter exclusivamente informativo y de apoyo, y no sustituyen el criterio de un médico especialista colegiado.
