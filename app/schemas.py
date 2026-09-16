from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field

# --- Esquemas de Datos del Dashboard ---

class KpiCard(BaseModel):
    title: str
    tag: str
    tag_class: str
    main_value: str
    unit: str
    subtitle_1: str
    subtitle_2: str
    badge_text: str
    badge_class: str

class DashboardSummaryResponse(BaseModel):
    paciente: Dict[str, Any]
    total_controles: int
    periodo_historico: str
    ultima_fecha: str
    dictamen_global: str
    dictamen_subtitulo: str
    kpis: List[KpiCard]

class TableRow(BaseModel):
    name: str
    unit: str
    ref: str
    vals: List[Any] # Floats, strings or None
    recentAvg: str
    avg: str
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
    yAxisID: Optional[str] = None
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

class ConfirmacionRequest(BaseModel):
    temp_id: str
    fecha: str
    laboratorio: str
    facultativo: Optional[str] = None
    mediciones: List[MedicionExtraida]
    dictamen_global: Optional[str] = None

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


