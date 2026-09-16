# Registro de Cambios (Changelog) - \cac-elrocho
Todas las modificaciones notables de este proyecto están documentadas en este archivo siguiendo el formato de [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/) y las convenciones de [Versionado Semántico](https://semver.org/lang/es/).

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
