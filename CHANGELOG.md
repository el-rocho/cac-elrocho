# Registro de Cambios (Changelog) - `cac-elrocho`
Todas las modificaciones notables de este proyecto están documentadas en este archivo siguiendo el formato de [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/) y las convenciones de [Versionado Semántico](https://semver.org/lang/es/).

## [v0.9.1] - 2026-09-23

* **Datos de demostración sintéticos**: una instalación nueva muestra tres analíticas ficticias anonimizadas, sin incluir ni modificar datos clínicos reales.
* **CI/CD**: pruebas obligatorias sobre SQLite temporal, runner fijado a Ubuntu 24.04 y acciones Docker actualizadas para Node 24.

## [v0.9.0] - 2026-09-23

### 🔗 Unificación de informes y referencias
* **Fusión o reemplazo de informes coincidentes**: Ante informes de la misma fecha, permite conservar analitos previos y actualizar/añadir los nuevos, o reemplazar íntegramente el informe seleccionado.
* **Número de referencia de petición**: Se extrae desde PDF/LLM, se puede revisar y editar en la interfaz, y se expone en el historial y auditoría de archivos.
* **Respaldo íntegro**: Las referencias de informe se serializan y restauran en las copias de seguridad JSON, incluidas las cifradas AES-GCM.

### 📈 Seguimiento clínico y verificación
* **Variaciones contextualizadas**: El panel compara únicamente con el control anterior dentro de 24 meses y respeta los umbrales de significación clínica.
* **Pruebas seguras**: Incorporada cobertura de extracción de referencias, fusión y restauración usando SQLite temporal; retirados escenarios dependientes de datos demo no deterministas.

---
## [v0.8.1] - 2026-09-21

### 🐛 Corrección en Carga de Cabecera y Tarjetas KPI en Producción
* **Resolución de NameError en Tipado (`Optional`, `Tuple`)**: Incorporadas las importaciones de tipado estricto en `app/api/analiticas.py` requeridas por Python 3.12 en entornos de despliegue Docker, resolviendo el fallo en el endpoint `/api/v1/analiticas/summary` que impedía renderizar la información personal del header, las etiquetas del modelo LLM/analítica y las tarjetas KPI tras cargar datos.

### 🛡️ Robustez y Armonización Automática en Importación de Respaldos
* **Auto-registro del Catálogo Canónico**: Garantizada la existencia de todas las determinaciones analíticas canónicas (`T4_TOTAL`, `T3_TOTAL`, anticuerpos, etc.) en la base de datos al importar copias de seguridad de cualquier versión previa.
* **Armonización Post-Importación Inmediata**: Integración de la rutina de armonización de escalas, unidades y semáforos al restaurar copias de seguridad (`/api/v1/backup/import`), asegurando consistencia clínica inmediata sin requerir reinicio del servidor.

---
## [v0.8.0] - 2026-09-21

### 📄 Extracción Tabular Avanzada de PDFs y Resiliencia Multimodal
* **Reconstrucción Horizontal de Tablas**: Configuración de extracción con ordenamiento espacial (`sort=True` en PyMuPDF y modo `layout` en pypdf), garantizando que las tablas columnarias de laboratorios (como Recoletas o Quirónsalud) asocien analito, valor y rangos en la misma línea en lugar de separar columnas en bloques distantes.
* **Red de Seguridad Heurística para Extracción**: Algoritmo de respaldo determinista en `llm_service.py` que detecta y rescata automáticamente determinaciones críticas de función renal (`EGFR_CKD_EPI` / Filtrado Glomerular) y perfil tiroideo si un modelo LLM ligero o con cupo limitado no los extrae de forma completa.
* **Priorización de Modelos LLM**: Configuración optimizada de cuotas en `.env` (Slot 1: `gemini-3.6-flash`, Slot 2: `gemini-3.8-flash`, Slot 3: `gemini-3.5-flash-lite`).

### 🦋 Ampliación Integral del Eje Tiroideo (T4 Total y T3 Total)
* **Tarjeta KPI de Función Tiroidea Enriquecida**:
  * **T4 Total** incorporada como parámetro **Principal** junto a TSH y T4 Libre, permitiendo el seguimiento de tiroxina total demandada habitualmente por especialistas.
  * **T3 Total** incorporada como parámetro **Secundario** junto a T3 Libre y el panel de anticuerpos (Anti-TPO, Anti-TG, TRAb).
* **Modal de Detalle Clínico y Guía Informativa**: Actualización de la ventana modal y del panel informativo con explicaciones fisiológicas y tablas de referencia para T4 Total (5.1 – 14.1 µg/dL) y T3 Total (0.80 – 2.00 ng/mL).
* **Catálogo Canónico y Desambiguación Semántica**: Registro en `CANONICAL_CATALOG` y reglas de discriminación en `analito_normalizer.py` para distinguir inequívocamente entre formas totales y libres ante sinónimos como `T4`, `TT4`, `T3` o `TT3`.

### 🩸 Calibración y Corrección de Escala en Basófilos y Diferencial Leucocitario
* **Resolución del Error de Multiplicación x1000 en Basófilos (`40` vs `40000`)**:
  * Sustituido el umbral genérico fijo (`< 50.0`) en `standardize_medicion` por umbrales fisiológicos específicos para cada subpoblación celular (Basófilos: `< 2.0`, Eosinófilos: `< 5.0`, Monocitos: `< 15.0`, Linfocitos: `< 25.0`, Neutrófilos: `< 30.0`).
  * Resuelto el problema que provocaba que cualquier valor normal de basófilos inferior a 50 (como `40 /µL`) se multiplicara automáticamente a `40000`, impidiendo además su corrección manual en la herramienta de edición y en la ventana de pre-ingesta.
  * Detección y corrección retrospectiva automática mediante `db_harmonizer` para restaurar los valores anómalos preexistentes a su magnitud clínica real (`40 /µL`).
* **Normalización Semántica de la Fórmula Leucocitaria**: Inclusión de reglas explícitas en `normalize_analito` para asignar directamente los códigos canónicos (`BASOFILOS_ABS`, `EOSINOFILOS_ABS`, `MONOCITOS_ABS`, `LINFOCITOS_ABS`, `NEUTROFILOS_ABS`) a partir de los nombres textuales del laboratorio.
* **Extracción Robusta ante Columnas Relativas y Absolutas**: Optimización de expresiones regulares en extracción para priorizar la columna de valor absoluto en lugar del porcentaje (`%`) en la fórmula leucocitaria.

### 📐 Homogeneización Automática de Magnitudes Basada en Rangos de Referencia
* **Detección Dinámica de Órdenes de Magnitud (`ref_ratio`)**: Algoritmo matemático en `standardize_medicion` que compara los límites del intervalo de referencia informado por el laboratorio frente al intervalo canónico (`max_canon / max_ref`). Permite discernir de forma infalible cuándo una analítica expresa magnitudes diferenciadas en un factor de 1000 (ej: `x10^3/µL` vs `/µL`), submúltiplos (`/L`), o escalas de concentración (`g/L` vs `g/dL`).
* **Conversión Dual Sincronizada (Valor y Rango)**: Homogeneización simétrica de la cifra numérica y del intervalo de referencia al formato estándar de la aplicación (ej: `0.0 - 0.2` en miles se escala a `0 - 200 /µL`), garantizando que la evaluación del semáforo clínico (`Normal`, `Alto`, `Bajo`) no arroje falsas alertas por desalineación de escalas.
* **Ampliación a Analitos Críticos**: Cobertura integral en fórmula leucocitaria (`BASOFILOS_ABS`, `EOSINOFILOS_ABS`, `MONOCITOS_ABS`, `LINFOCITOS_ABS`, `NEUTROFILOS_ABS`), `LEUCOCITOS`, `PLAQUETAS`, `HEMATIES`, `HEMOGLOBINA`, `PROTEINAS_TOTALES` y `ALBUMINA`.
* **Depuración de Unidades Redundantes**: Limpieza preventiva en `db_harmonizer` para evitar duplicidad de unidades textuales en la referencia oficial de analitos (`ref_texto_defecto`).

---
## [v0.7.0] - 2026-09-20

### 📌 Tabla Evolutiva con Columnas Fijas y Doble Scroll Sincronizado
* **Columnas Fijas (Sticky)**: Parámetro, Unidades e Intervalo de Referencia permanecen anclados a la izquierda con delimitador sombreado, facilitando la lectura sin perder el contexto al desplazarse horizontalmente por fechas.
* **Doble Barra de Desplazamiento**: Scroll horizontal superior e inferior sincronizados en tiempo real para una navegación fluida en historiales analíticos extensos.
* **Navegación Rápida**: Botones dedicados para saltar de forma inmediata a los resultados más antiguos (inicio) o a las analíticas más recientes (final).

### 🔍 Modal de Detalle Completo de KPIs y Jerarquía de Parámetros
* **Ventana Modal Interactiva**: Apertura de desglose detallado al hacer clic en cualquier tarjeta KPI del cuadro de mando (o con teclado `Enter`/`Espacio`), con navegación directa entre tarjetas mediante flechas anterior y siguiente.
* **Jerarquización Analítica**: Clasificación visual de analitos en **Principal**, **Secundario** y **Complementario** (`es_principal`, `tipo_parametro`), aportando claridad diagnóstica inmediata.
* **Detalle Enriquecido**: Presentación amplia y sin recortes de valores históricos con notas al pie, variación respecto al control anterior y estado de tendencia longitudinal.

### ⚖️ Gestión Reversible de Auditorías de Rangos de Referencia
* **Opción "Mantener Histórico"**: Posibilidad de conservar los rangos de normalidad originales tanto de forma individual como en lote ("Mantener todos"), evitando sobreescribir los criterios históricos cuando el usuario lo prefiera.
* **Ciclo de Estados Formal**: Auditorías estructuradas en estados `pendiente`, `aplicado` y `mantenido`.
* **Reversibilidad y Recálculo Automático**: Si se revierte una decisión, se restauran los rangos previos y se recalculan al instante los semáforos clínicos de las mediciones afectadas.
* **Persistencia en Copias de Seguridad**: Soporte completo en el servicio de respaldo (backup/restore JSON) para conservar el estado de auditorías y decisiones tomadas.

### 🦋 Función Tiroidea Avanzada y Catalogación de Anticuerpos
* **Evaluación Fisiológica Conjunta**: Análisis integrado y recíproco de **TSH** y **T4 Libre** en la tarjeta "Función Tiroidea" (eutiroideo, hipotiroidismo, hipertiroidismo o discordancias clínicas).
* **Carácter Complementario**: Parámetros como **T3 Libre** y anticuerpos no penalizan negativamente por sí solos la valoración global si el eje principal TSH-T4L es normal.
* **Nuevos Analitos Específicos**: Inclusión en catálogo y normalización automática de **Anti-TPO** (Anticuerpos anti-peroxidasa), **Anti-TG** (Anticuerpos anti-tiroglobulina) y **TRAb** (Anticuerpos anti-receptor de TSH).

---
## [v0.6.0] - 2026-09-19

### 📊 Rediseño y Calibración Cardiometabólica del Cuadro de Mando
* **6 Tarjetas KPI Principales Reorganizadas**: Enfoque clínico prioritario en Perfil Lipídico Avanzado, Metabolismo Glucídico y Riesgo Aterogénico, Función Renal y Filtrado Glomerular, Metabolismo del Hierro, Perfil Hepático y Enzimas, y Eje Tiroideo / Vigilancia.
* **Formato de 1 Analito por Fila**: Presentación visual limpia y ordenada de cada parámetro con sus unidades y rangos.
* **Preservación Histórica Rigurosa**:
  * Asociación de valores mediante superíndices de fecha y notas al pie explicativas cuando un analito proviene de una determinación previa.
  * Bloqueo estricto de cálculo de ratios (Castelli I, II, TG/HDL) entre mediciones pertenecientes a fechas o informes diferentes, evitando cocientes distorsionados.

### 📈 Tendencias Longitudinales y Variaciones Analíticas
* **Semáforo y Tendencia en Tarjetas KPI**: Indicadores visuales de dirección (ascendente, descendente, estable) y puntos de estado global en cada panel.
* **Variaciones Porcentuales Contextuales**: Cálculo automático del cambio relativo frente al control anterior, distinguiendo si la tendencia representa mejoría o deterioro clínico.
* **Guía Médica Desplegable**: Panel de orientación con umbrales clínicos según directrices de la OMS (2024 para hemoglobina/anemia, ferritina, VCM, leucocitos y plaquetas) y notas sobre interpretación contextual.

### 🧪 Armonización Automática de Unidades y Escalas (`db_harmonizer`)
* **Estandarización Preventiva en Base de Datos**: Rutina ejecutada automáticamente durante el inicio (`lifespan`) para normalizar discrepancias históricas en magnitudes analíticas:
  * Fórmula leucocitaria absoluta (Linfocitos, Neutrófilos, Monocitos, Eosinófilos, Basófilos) en `/µL`.
  * Leucocitos y Plaquetas en `x10^3/µL`.
  * Hematíes en `x10^6/µL` (resolviendo inconsistencias entre notación con punto de millares y formato decimal).
  * Homologación proporcional de rangos de normalidad.
* **Estandarización en Ingesta y Edición**: Función `standardize_medicion` integrada en la subida, confirmación y edición de analíticas.

### 🔍 Auditoría y Detección Proactiva de Rangos de Referencia con IA
* **Escaneo Automático de Variaciones Metodológicas (`/api/v1/ai/detectar`)**: Detección cronológica de cambios en los criterios de referencia de los laboratorios (ej. directrices SEA/ESC en LDL, analizadores enzimáticos de urea o hematimetría).
* **Homologación Retrospectiva**: Capacidad de extender los rangos de referencia actualizados a todo el historial clínico, recalculando automáticamente el estado del semáforo.

### 🛡️ Estabilidad y Robustez en la Extracción y Almacenamiento
* **Cálculo Automático de eGFR**: Generación e inserción calculada de Filtrado Glomerular (CKD-EPI) en la tabla evolutiva cuando no viene explícito en el informe y se dispone de creatinina, edad y sexo.
* **Semaforización Celular en Tabla Histórica**: Evaluación individualizada del estado clínico (`TableCell`) para cada analítica histórica.
* **Nuevos Analitos**: Soporte ampliado para Anticuerpos Anti-CCP, ANA y marcadores tumorales (CEA, CA 19-9, CA-125).

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
