from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field

# --- Esquemas de Datos del Dashboard ---

class AnalitoFila(BaseModel):
    codigo: Optional[str] = None
    label: str
    val: str
    unit: Optional[str] = ""
    is_altered: Optional[bool] = False
    var_symbol: Optional[str] = None      # '↑', '↓', '→'
    var_delta: Optional[str] = None       # '+0.3', '-6', ''
    trend_symbol: Optional[str] = None    # '↗', '↘', '→'
    clinical_trend: Optional[str] = None  # 'FAVORABLE', 'ESTABLE', 'DESFAVORABLE'
    es_historico: Optional[bool] = False
    fecha_origen: Optional[str] = None    # '27/09/2018' o '2018-09-27'
    footnote_symbol: Optional[str] = None # '¹', '²', '³'

class KpiCard(BaseModel):
    id: Optional[str] = None
    title: str
    tag: str
    tag_class: str
    main_label: Optional[str] = None
    main_value: str
    unit: str
    main_value_class: Optional[str] = "text-slate-900"
    is_altered: Optional[bool] = False
    main_var_symbol: Optional[str] = None
    main_var_delta: Optional[str] = None
    main_trend_symbol: Optional[str] = None
    main_clinical_trend: Optional[str] = None
    main_is_historical: Optional[bool] = False
    main_fecha_origen: Optional[str] = None
    main_footnote_symbol: Optional[str] = None
    subtitle_1: Optional[str] = ""
    subtitle_2: Optional[str] = ""
    subtitle_3: Optional[str] = ""
    subtitles: Optional[List[str]] = []
    filas: Optional[List[AnalitoFila]] = []
    badge_text: str
    badge_class: str
    trend_global: Optional[str] = "sin_tendencia"
    trend_badge_text: Optional[str] = "Sin tendencia"
    trend_badge_class: Optional[str] = "bg-slate-100 text-slate-600 border-slate-200"
    notas_pie: Optional[List[Dict[str, str]]] = []

class MetricaSimple(BaseModel):
    label: str
    val: str
    unit: str = ""
    ref: Optional[str] = ""
    is_altered: Optional[bool] = False

class OtrosValoresSeccion(BaseModel):
    id: str
    titulo: str
    icono: Optional[str] = ""
    badge_text: str
    badge_class: str
    items: List[MetricaSimple]
    nota: Optional[str] = None

class DashboardSummaryResponse(BaseModel):
    paciente: Dict[str, Any]
    total_controles: int
    periodo_historico: str
    ultima_fecha: str
    dictamen_global: str
    dictamen_subtitulo: str
    kpis: List[KpiCard]
    otros_valores: Optional[List[OtrosValoresSeccion]] = []
    motor_llm_info: Optional[Dict[str, Any]] = None
    app_version: Optional[str] = None

class TableCell(BaseModel):
    val: Optional[Any] = None
    ref: Optional[str] = None
    status: Optional[str] = "Normal"
    is_altered: bool = False

class TableRow(BaseModel):
    name: str
    unit: str
    ref: str
    vals: List[Any] # Floats, strings or None
    cells: Optional[List[TableCell]] = None
    recentAvg: str
    avg: Optional[str] = "-"
    group: Optional[str] = None

class TablesResponse(BaseModel):
    dates: List[str] # ['07/09/22', '01/12/22', ...]
    informes: Optional[List[Dict[str, Any]]] = None # Listado con id, fecha, etiqueta_corta y lab
    bioquimica: List[TableRow]
    hemograma: List[List[str]]
    coagulacion: List[List[str]]
    enzimas: List[List[str]]

class ChartDataset(BaseModel):
    label: str
    data: List[Any]
    borderColor: Optional[str] = None
    backgroundColor: Optional[str] = None
    borderWidth: Optional[float] = 2.0
    tension: Optional[float] = 0.2
    fill: Optional[bool] = False
    yAxisID: Optional[str] = "y"
    spanGaps: Optional[bool] = True
    pointRadius: Optional[float] = 4.0
    pointHoverRadius: Optional[float] = 6.0

class ChartConfig(BaseModel):
    labels: List[str]
    datasets: List[ChartDataset]

class ChartsResponse(BaseModel):
    glucosa: ChartConfig
    lipidos: ChartConfig
    castelli: ChartConfig
    ratios_tg: ChartConfig
    renal: ChartConfig
    urico: ChartConfig
    psa: ChartConfig
    tsh: ChartConfig

# --- Esquemas para Extracción e IA ---

class MedicionExtraida(BaseModel):
    codigo: Optional[str] = Field(default=None, description="Código canónico del analito (ej: CHOLESTEROL_TOTAL, HDL, RATIO_COL_HDL, GLUCOSE)")
    nombre: str = Field(description="Nombre del analito encontrado en el informe")
    valor: str = Field(description="Valor numérico o textual (ej: '96.7' o '< 1.7')")
    unidad: str = Field(description="Unidad de medida (ej: 'mg/dL', '%', 'ng/mL')")
    rango_referencia: str = Field(description="Intervalo de normalidad del laboratorio (ej: '60 - 100', '< 116')")
    estado_estimado: Optional[str] = Field(default="Normal", description="Optimo, Normal, Limite, Atencion, Alto o Bajo")

class RangoDetectado(BaseModel):
    analito: str
    rango_anterior: Optional[str]
    rango_nuevo: str
    explicacion: str

class AnaliticaPreviewResponse(BaseModel):
    temp_id: str
    fecha: str
    laboratorio: str
    facultativo: Optional[str] = None
    total_parametros: int
    mediciones: List[MedicionExtraida]
    alertas_ia: List[str]
    rangos_modificados: List[RangoDetectado]
    dictamen_preliminar: str
    paciente_detectado: Optional[str] = None
    dni_detectado: Optional[str] = None
    aviso_discrepancia_paciente: Optional[str] = None
    sha256: Optional[str] = None
    es_duplicado: Optional[bool] = False
    tipo_duplicado: Optional[str] = None # 'exacto_archivo' | 'misma_fecha_lab' | None
    informe_existente_id: Optional[int] = None
    informe_existente_info: Optional[str] = None
    aviso_duplicado: Optional[str] = None
    motor_extraccion: Optional[str] = "llm" # 'llm' o 'mock'
    modelo_utilizado: Optional[str] = None
    slot_utilizado: Optional[int] = None

class RegenerateDictamenRequest(BaseModel):
    mediciones: List[MedicionExtraida]
    fecha: str
    laboratorio: str
    facultativo: Optional[str] = None
    modo: Optional[str] = "completo" # "completo" | "resumido"

class RegenerateDictamenResponse(BaseModel):
    dictamen_global: str
    alertas_ia: List[str]

class ConfirmacionRequest(BaseModel):
    temp_id: str
    fecha: str
    laboratorio: str
    facultativo: Optional[str] = None
    mediciones: List[MedicionExtraida]
    dictamen_global: Optional[str] = None
    sha256: Optional[str] = None
    sobrescribir_existente: Optional[bool] = False
    informe_id_a_reemplazar: Optional[int] = None

class AuditFileItem(BaseModel):
    id: int
    fecha: str
    etiqueta_corta: str
    laboratorio: str
    facultativo: Optional[str] = "No especificado"
    archivo_pdf: Optional[str] = None
    total_mediciones: int
    dictamen_global: Optional[str] = None
    created_at: Optional[str] = None

class MedicionDetail(BaseModel):
    id: Optional[int] = None
    codigo: Optional[str] = None
    nombre: str
    valor: Any
    unidad: str
    rango_referencia: Optional[str] = None
    estado_estimado: Optional[str] = None
    es_ratio: Optional[bool] = False

class InformeDetailResponse(BaseModel):
    id: int
    fecha: str
    etiqueta_corta: str
    laboratorio: str
    facultativo: Optional[str] = None
    dictamen_global: Optional[str] = None
    archivo_pdf: Optional[str] = None
    mediciones: List[MedicionDetail]

class InformeUpdateRequest(BaseModel):
    fecha: str
    laboratorio: str
    facultativo: Optional[str] = None
    dictamen_global: Optional[str] = None
    mediciones: List[MedicionDetail]

# --- Esquemas de Paciente ---

class PacienteInfo(BaseModel):
    id: Optional[int] = None
    nombre_completo: Optional[str] = ""
    fecha_nacimiento: Optional[str] = None
    dni: Optional[str] = None
    sexo: Optional[str] = "No especificado"
    centro_referencia: Optional[str] = None
    edad: Optional[str] = None

class PacienteUpdateRequest(BaseModel):
    nombre_completo: Optional[str] = ""
    fecha_nacimiento: Optional[str] = None
    dni: Optional[str] = None
    sexo: Optional[str] = "No especificado"
    centro_referencia: Optional[str] = None


