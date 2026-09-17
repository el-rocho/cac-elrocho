# Registro de Cambios (Changelog) - `cac-elrocho`
Todas las modificaciones notables de este proyecto están documentadas en este archivo siguiendo el formato de [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/) y las convenciones de [Versionado Semántico](https://semver.org/lang/es/).

---
## [v0.5.0] - 2026-09-17

### 📄 Extracción Robusta con LLM Multimodal y Validación Cruzada
* **Ingesta Multimodal Nativa de Documentos PDF**: Integración directa del binario PDF con la API de Google Gemini (`types.Part.from_bytes`), permitiendo al modelo interpretar directamente la estructura visual, tablas y glifos del documento original y reduciendo drásticamente las imprecisiones de extracción de texto plano.
* **Validación Cruzada de Coherencia Analítica (Marcas de Laboratorio vs. Valores)**:
  * **Comprobación de marcas de anormalidad**: Si el documento incluye asteriscos (`*`), negritas o indicadores (`H`, `L`), el sistema verifica que el valor extraído sea patológico y no un artefacto de OCR o nota aclaratoria (por ejemplo, asegurando la captura de Bilirrubina patológica frente a notas de límite de detección).
  * **Descarte de falsos positivos**: Si un analito carece de marcas de alteración clínica en el informe, se descartan lecturas erróneas por similitud de caracteres tipográficos (ej. diferenciación precisa de cifras en Hierro sérico).
* **Normalización Numérica y Escalado Automático (`normalize_valor_numerico`)**:
  * Limpieza automática de prefijos, asteriscos y notación de millares y comas en formato español.
  * Escalado automático de unidades clínicas canónicas: Hematíes a millones (x10^6/µL), Plaquetas y Leucocitos a miles (x10^3/µL).

### 🤖 Modelos Recomendados y Rendimiento Óptimo
* **Nuevo Esquema de Modelos LLM Recomendados**: Actualización de recomendaciones en configuración (`.env.example` y documentación) priorizando `gemini-2.5-flash` (Slot 1: balance óptimo de velocidad y precisión multimodal), `gemini-2.5-flash-lite` (Slot 2: respaldo ultraligero y alta disponibilidad) y `gemini-2.5-pro` (Slot 3: razonamiento profundo), todos accesibles mediante la API gratuita de Google AI Studio.
* **Persistencia del sistema Multi-Slot con Failover**: Mantenimiento del esquema de hasta 3 slots con conmutación automática ante cuota agotada o fallos y extractor RegEx local como red de seguridad.

### 🧪 Ampliación del Catálogo de Analitos
* **Coagulación y Hemostasia**: Cobertura e indexación de Tiempo de Protrombina (TP), Índice de Quick, INR, Ratio TP, TTPA / Cefalina, Fibrinógeno y Dímero D.
* **Inmunología y Alergología**: Detección dinámica y normalización de Inmunoglobulina E Total (IgE) y anticuerpos IgE específicos (gramíneas como *Cynodon dactylon*, *Lolium perenne*, ciprés/arizónica, epitelios, etc.).
* **Perfil de Orina**: Extracción de pH, densidad y parámetros sistemáticos.

### 🔄 Regeneración Dinámica y Resumen de Dictamen Clínico
* **Botón "🔄 Regenerar dictamen"**: Reevaluación clínica automatizada basada exclusivamente en las mediciones de la tabla con las correcciones manuales realizadas por el usuario.
* **Botón "📝 Resumir dictamen"**: Generación de síntesis clínica concisa (2-3 frases) centrada exclusivamente en los parámetros alterados o fuera de rango.
* **Aviso Proactivo de Desincronización**: Detección visual interactiva en los modales de previsualización y edición cuando se modifican valores en la tabla, alertando para mantener el dictamen actualizado antes de guardar.
* **Áreas de Texto Flexibles**: Campos de dictamen autoextensibles y redimensionables para facilitar la lectura de valoraciones extensas.

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
* **Versión dinámica en pie de página (Footer)**: Desacoplamiento total del número de versión en el frontend; se inyecta y actualiza de forma dinámica en base a `__version__` de la aplicación, garantizando que el pie de página siempre refleje la versión en curso sin requerir modificaciones manuales en el HTML.

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
