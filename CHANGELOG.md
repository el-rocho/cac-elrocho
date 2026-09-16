# Registro de Cambios (Changelog) - `cac-elrocho`
Todas las modificaciones notables de este proyecto están documentadas en este archivo siguiendo el formato de [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/) y las convenciones de [Versionado Semántico](https://semver.org/lang/es/).

---

## [v0.4.0] - 2026-09-16

### 🤖 Arquitectura Multi-Modelo LLM y Failover Secuencial
* **Configuración de hasta 3 slots en `.env`**: El usuario controla con total soberanía hasta 3 modelos independientes (`LLM_PROVIDER1..3`, `API_KEY1..3`, `MODEL1..3`) con sus respectivas claves de API.
* **Alternancia automática por fallo o cuota agotada**:
  * Intento prioritario en **Slot 1**.
  * Si el modelo agota su cuota diaria (`429 RESOURCE_EXHAUSTED`), es discontinuado (`404`) o sufre caídas de servicio (`503`), conmuta automáticamente al **Slot 2**, y sucesivamente al **Slot 3**.
  * Detección flexible: Si el usuario solo define 1 o 2 modelos, el sistema opera con normalidad sin errores.
* **Extractor de contingencia RegEx (Sin LLM)**: Si todos los modelos configurados fallan o no se ha configurado ninguno, conmuta transparentemente a un extractor local basado en patrones de expresiones regulares.
* **Transparencia en la interfaz de usuario (UI)**:
  * Etiqueta dinámica en la cabecera: muestra `✨ Motor LLM Activo (N mod.)` con tooltip detallado, o `⚠️ Extractor RegEx (Sin LLM)` / `⚠️ Extractor RegEx (Contingencia Activa)` en caso de fallback.
  * Banner informativo en la ventana modal de previsualización: identifica con precisión el slot y modelo utilizado (`[Slot 1: gemini-flash-lite-latest]`) o avisa explícitamente del uso de expresiones regulares.

### 🩺 Precisión Clínica y Sanitización de Metadatos
* **Diferenciación estricta Facultativo vs. Tipo de Revisión**: El extractor no confunde motivos de consulta ("Control anual", "Revisión especialista", etc.) con el nombre del médico solicitante.
* **Desacoplamiento Médico / Laboratorio**: El nombre del médico solicitante ya no se concatena ni se incluye entre paréntesis dentro del nombre del laboratorio o centro emisor.
* **Simplificación y homologación de la sección Auditoría**: Título simplificado a "Auditoría de los rangos de referencia aplicados", tarjetas condensadas a 3 líneas con información limpia y criterios aplicados desplegables mediante acordeón.

### 🧹 Refactorización de Interfaz y Textos
* **Limpieza de textos en Exportar / Importar Respaldo**: Eliminación de textos superfluos y clarificación de la advertencia de reemplazo total en la restauración.
* **Puesta a punto (Modo Demo)**: Texto clarificado sobre la sustitución de datos de prueba y botón renombrado a "Cargar datos del modo Demo".

---

## [v0.3.0] - 2026-09-16

### 🛡️ Detección y Prevención de Analíticas Repetidas
* **Indexación criptográfica por SHA-256**: Cada documento PDF analizado genera inmediatamente su hash \SHA-256\, almacenado en la tabla \informes\ para garantizar unicidad a nivel de archivo.
* **Comprobación en dos niveles**:
  1. **Duplicado exacto de archivo**: Alerta si se intenta subir un PDF idéntico a uno ya procesado anteriormente.
  2. **Colisión de fecha y laboratorio**: Detecta si ya existe un informe registrado en la base de datos para esa misma fecha y centro médico.
* **Experiencia de usuario y resolución de duplicados**:
  * Banner visual interactivo en la ventana modal de previsualización que identifica el informe previo coincidente.
  * Selector de acción en el diálogo de confirmación:
    * 🟢 **Sobrescribir / Actualizar registro existente** *(por defecto)*: Actualiza metadatos y mediciones de forma atómica sin duplicar datos en tablas ni gráficos.
    * ⚪ **Guardar como nuevo registro adicional**: En caso de requerir registrar dos informes independientes en la misma fecha.
* **Migración y backfill automático**: Rutina de arranque en segundo plano que calcula e indexa retroactivamente el hash \SHA-256\ de todos los PDFs existentes en el sistema.

### 💾 Copias de Seguridad y Restauración Segura
* **Nombres con marca temporal**: Las copias de seguridad exportadas ahora incluyen fecha y hora exactas en el nombre de archivo (\cac-elrocho-backup-YYYYMMDD_HHMMSS.json\ o \.enc.json\).
* **Integración con File System Access API**: Compatible con \window.showSaveFilePicker\, permitiendo seleccionar la carpeta de destino y detectando cancelaciones (\AbortError\) sin mostrar alertas erróneas de éxito.
* **Transparencia en la importación (Wipe & Restore)**: Mensajes informativos y diálogo de confirmación explícito que aclaran que la importación realiza una restauración completa (sustitución total limpia sin riesgo de duplicidades).
* **Persistencia de integridad en respaldos**: Los campos \sha256\ y \rchivo_pdf\ ahora forman parte del esquema JSON de exportación e importación.

---

## [v0.2.0] - 2026-06-15

### 👤 Ficha del Paciente y Validación de Identidad
* **Configuración soberana del usuario**: Gestión de nombre completo, DNI/NIE, fecha de nacimiento (con cálculo automático de edad) y sexo.
* **Validación flexible de identidad**: Comprobación semántica tolerante ante discrepancias de nombre o DNI en informes médicos escaneados.

### 🤖 Copiloto de IA y Auditoría de Rangos
* Integración con **Google Gemini API** (y modo de contingencia inteligente sin conexión).
* **Auditoría de variaciones de rangos**: Detección y explicación de cambios en los límites de normalidad de laboratorios (directrices SEA 2023).
* Recálculo automático de cocientes aterogénicos (Castelli I, II, TG/HDL, PSA Libre/Total).

---

## [v0.1.0] - 2026-03-01

### 🚀 Lanzamiento Inicial
* Cuadro de mando clínico con KPIs, tablas históricas y 8 gráficas evolutivas en Chart.js.
* Extracción automatizada de parámetros analíticos desde documentos PDF con PyMuPDF.
* Soporte para ejecución en contenedores Docker y despliegue multiplataforma.
