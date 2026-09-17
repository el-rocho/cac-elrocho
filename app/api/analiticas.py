from datetime import date
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app import __version__
from app.config import settings
from app.database import get_db
from app.models import Paciente, Informe, Analito, Medicion
from app.schemas import (
    DashboardSummaryResponse, KpiCard, TablesResponse, TableRow,
    ChartsResponse, ChartConfig, ChartDataset, AuditFileItem,
    InformeDetailResponse, InformeUpdateRequest, MedicionDetail,
    PacienteInfo, PacienteUpdateRequest
)
from app.services.metrics import get_cell_format, calculate_ratios
from app.services.analito_normalizer import get_analito_group, normalize_analito, get_analito_order, normalize_valor_numerico

router = APIRouter(prefix="/analiticas", tags=["Analíticas"])

def calcular_edad(fecha_nacimiento: str) -> str:
    """Calcula los años cumplidos a partir de una fecha en formato YYYY-MM-DD o DD/MM/YYYY."""
    if not fecha_nacimiento or not str(fecha_nacimiento).strip():
        return "-"
    try:
        limpia = str(fecha_nacimiento).strip()
        partes = limpia.split("-")
        if len(partes) == 3:
            birth_year, birth_month, birth_day = int(partes[0]), int(partes[1]), int(partes[2])
            hoy = date.today()
            edad = hoy.year - birth_year - ((hoy.month, hoy.day) < (birth_month, birth_day))
            if 0 <= edad <= 125:
                return f"{edad} años"
        partes_slash = limpia.split("/")
        if len(partes_slash) == 3:
            birth_day, birth_month, birth_year = int(partes_slash[0]), int(partes_slash[1]), int(partes_slash[2])
            hoy = date.today()
            edad = hoy.year - birth_year - ((hoy.month, hoy.day) < (birth_month, birth_day))
            if 0 <= edad <= 125:
                return f"{edad} años"
    except Exception:
        pass
    return "-"

def get_motor_llm_summary() -> Dict[str, Any]:
    """Retorna información del estado de los modelos LLM configurados."""
    slots = settings.get_configured_llm_slots()
    llm_slots = [s for s in slots if s.get("provider") != "mock" and s.get("api_key") and s.get("model")]
    return {
        "activo": len(llm_slots) > 0,
        "tipo": "llm" if len(llm_slots) > 0 else "mock",
        "slots_totales": len(slots),
        "slots_llm": len(llm_slots),
        "modelos": [s["model"] for s in llm_slots],
        "descripcion": f"{len(llm_slots)} modelo(s) configurado(s)" if len(llm_slots) > 0 else "Extractor RegEx (Sin LLM)"
    }

@router.get("/summary", response_model=DashboardSummaryResponse)
def get_dashboard_summary(db: Session = Depends(get_db)):
    """
    Devuelve los datos del paciente, resumen de controles y tarjetas KPI de la última analítica.
    """
    paciente = db.query(Paciente).first()
    informes = db.query(Informe).order_by(Informe.fecha.asc()).all()
    motor_info = get_motor_llm_summary()
    
    if not informes:
        return DashboardSummaryResponse(
            paciente={
                "nombre": (paciente.nombre_completo if paciente and paciente.nombre_completo else "").strip(),
                "nacimiento": (paciente.fecha_nacimiento if paciente and paciente.fecha_nacimiento else "-"),
                "edad": calcular_edad(paciente.fecha_nacimiento) if paciente and paciente.fecha_nacimiento else "-",
                "dni": (paciente.dni if paciente and paciente.dni else "-"),
                "sexo": (paciente.sexo if paciente and paciente.sexo else "No especificado")
            },
            total_controles=0,
            periodo_historico="Sin registros",
            ultima_fecha="Ninguna",
            dictamen_global="Base de Datos Vacía",
            dictamen_subtitulo="Carga un PDF o importa un respaldo para iniciar el seguimiento",
            kpis=[],
            motor_llm_info=motor_info,
            app_version=__version__
        )

    ultimo_informe = informes[-1]
    total_controles = len(informes)
    periodo = f"{informes[0].fecha[:4]} - {informes[-1].fecha[:4]}"
    ultima_fecha = ultimo_informe.fecha

    # Obtener mapa de mediciones del último informe
    meds = db.query(Medicion).filter_by(informe_id=ultimo_informe.id).all()
    m_map = {m.analito.codigo: m for m in meds if m.analito}

    def get_v(cod, default="-"):
        m = m_map.get(cod)
        if m and (m.valor_numerico is not None or m.valor_texto):
            return str(m.valor_numerico) if m.valor_numerico is not None else str(m.valor_texto)
        for inf in reversed(informes[:-1]):
            for past_m in inf.mediciones:
                if past_m.analito and past_m.analito.codigo == cod:
                    if past_m.valor_numerico is not None:
                        return str(past_m.valor_numerico)
                    elif past_m.valor_texto:
                        return str(past_m.valor_texto)
        return default

    def fmt(v, decimals=None):
        if v is None or v == "" or v == "-":
            return "-"
        try:
            f = float(str(v).replace(",", "."))
            if decimals is not None:
                return f"{f:.{decimals}f}"
            return str(int(f)) if f == int(f) else str(round(f, 2))
        except Exception:
            return str(v)

    # 1. Glucosa y HbA1c
    glu = get_v("GLUCOSE", "96.5")
    hba = get_v("HBA1C", "5.0")

    # Valores lipídicos
    col_t = get_v("CHOLESTEROL_TOTAL", "150.0")
    hdl = get_v("HDL", "42.0")
    ldl = get_v("LDL", "113.0")
    tg = get_v("TRIGLYCERIDES", "78.0")

    # Ratios aterogénicos e insulínicos calculados con los datos más recientes
    try:
        c_f = float(col_t.replace(",", "."))
        h_f = float(hdl.replace(",", "."))
        ratio_col_hdl = f"{round(c_f / h_f, 2)}" if h_f > 0 else get_v("RATIO_COL_HDL", "3.57")
    except Exception:
        ratio_col_hdl = get_v("RATIO_COL_HDL", "3.57")

    try:
        ldl_f = float(ldl.replace(",", "."))
        h_f = float(hdl.replace(",", "."))
        ratio_ldl_hdl = f"{round(ldl_f / h_f, 2)}" if h_f > 0 else get_v("RATIO_LDL_HDL", "2.69")
    except Exception:
        ratio_ldl_hdl = get_v("RATIO_LDL_HDL", "2.69")

    try:
        tg_f = float(tg.replace(",", "."))
        h_f = float(hdl.replace(",", "."))
        ratio_tg_hdl = f"{round(tg_f / h_f, 2)}" if h_f > 0 else get_v("RATIO_TG_HDL", "1.86")
    except Exception:
        ratio_tg_hdl = get_v("RATIO_TG_HDL", "1.86")

    try:
        r_tg_num = float(ratio_tg_hdl)
        tg_hdl_txt = "Sensibilidad insulínica óptima (<2.0)" if r_tg_num < 2.0 else "Vigilancia metabólica (>2.0)"
    except Exception:
        tg_hdl_txt = "Insulina adecuada (<2.0)"

    # 1. Glucosa y Metabolismo (Evaluación multianalito: Glucosa, HbA1c y Ratio TG/HDL)
    try:
        glu_num = float(glu.replace(",", "."))
    except Exception:
        glu_num = 101.0

    try:
        hba_num = float(hba.replace(",", "."))
    except Exception:
        hba_num = 5.0

    if hba_num >= 6.5 or glu_num >= 126.0:
        glu_badge = f"🔴 Atención ({'HbA1c' if hba_num >= 6.5 else 'Glucosa'})"
        glu_badge_cls = "bg-rose-50 text-rose-700 border-rose-200"
        glu_tag = "Atención"
        glu_tag_cls = "bg-rose-100 text-rose-800"
    elif hba_num >= 5.7:
        glu_badge = "🟡 Seguimiento (HbA1c)"
        glu_badge_cls = "bg-amber-50 text-amber-800 border-amber-200"
        glu_tag = "Seguimiento"
        glu_tag_cls = "bg-amber-100 text-amber-800"
    elif glu_num >= 100.0:
        glu_badge = "🟡 Seguimiento (Glucosa)"
        glu_badge_cls = "bg-amber-50 text-amber-800 border-amber-200"
        glu_tag = "Seguimiento"
        glu_tag_cls = "bg-amber-100 text-amber-800"
    elif r_tg_num >= 2.0:
        glu_badge = "🟡 Seguimiento (TG/HDL)"
        glu_badge_cls = "bg-amber-50 text-amber-800 border-amber-200"
        glu_tag = "Seguimiento"
        glu_tag_cls = "bg-amber-100 text-amber-800"
    else:
        glu_badge = "🟢 Normal"
        glu_badge_cls = "bg-emerald-50 text-emerald-700 border-emerald-200"
        glu_tag = "Normal"
        glu_tag_cls = "bg-emerald-100 text-emerald-800"

    # 2. Perfil Lipídico (Evaluación multianalito: Colesterol Total, LDL, HDL, Triglicéridos, Castelli)
    try:
        ldl_num = float(ldl.replace(",", "."))
    except Exception:
        ldl_num = 113.0
    try:
        col_num = float(col_t.replace(",", "."))
    except Exception:
        col_num = 150.0
    try:
        tg_num = float(tg.replace(",", "."))
    except Exception:
        tg_num = 78.0

    if ldl_num >= 160.0 or col_num >= 240.0 or tg_num >= 300.0:
        lipid_badge = f"🔴 Atención ({'LDL' if ldl_num >= 160 else ('Triglicéridos' if tg_num >= 300 else 'Colesterol')})"
        lipid_badge_cls = "bg-rose-50 text-rose-700 border-rose-200"
        lipid_tag = "Atención"
        lipid_tag_cls = "bg-rose-100 text-rose-800"
    elif ldl_num > 100.0:
        lipid_badge = "🟡 Seguimiento (LDL)"
        lipid_badge_cls = "bg-amber-50 text-amber-800 border-amber-200"
        lipid_tag = "Seguimiento"
        lipid_tag_cls = "bg-amber-100 text-amber-800"
    elif col_num > 200.0:
        lipid_badge = "🟡 Seguimiento (Colesterol)"
        lipid_badge_cls = "bg-amber-50 text-amber-800 border-amber-200"
        lipid_tag = "Seguimiento"
        lipid_tag_cls = "bg-amber-100 text-amber-800"
    elif tg_num > 150.0:
        lipid_badge = "🟡 Seguimiento (Triglicéridos)"
        lipid_badge_cls = "bg-amber-50 text-amber-800 border-amber-200"
        lipid_tag = "Seguimiento"
        lipid_tag_cls = "bg-amber-100 text-amber-800"
    else:
        lipid_badge = "🟢 Normal"
        lipid_badge_cls = "bg-emerald-50 text-emerald-700 border-emerald-200"
        lipid_tag = "Normal"
        lipid_tag_cls = "bg-emerald-100 text-emerald-800"

    # 3. Función Renal (Evaluación multianalito: Creatinina, Urea, Ácido Úrico)
    try:
        creat_num = float(get_v("CREATININE", "0.84").replace(",", "."))
    except Exception:
        creat_num = 0.84
    try:
        urico_num = float(get_v("URIC_ACID", "6.1").replace(",", "."))
    except Exception:
        urico_num = 6.1

    if creat_num >= 1.4 or urico_num >= 8.5:
        renal_badge = f"🔴 Atención ({'Creatinina' if creat_num >= 1.4 else 'Ác. Úrico'})"
        renal_badge_cls = "bg-rose-50 text-rose-700 border-rose-200"
        renal_tag = "Atención"
        renal_tag_cls = "bg-rose-100 text-rose-800"
    elif creat_num > 1.2:
        renal_badge = "🟡 Seguimiento (Creatinina)"
        renal_badge_cls = "bg-amber-50 text-amber-800 border-amber-200"
        renal_tag = "Seguimiento"
        renal_tag_cls = "bg-amber-100 text-amber-800"
    elif urico_num > 7.0:
        renal_badge = "🟡 Seguimiento (Ác. Úrico)"
        renal_badge_cls = "bg-amber-50 text-amber-800 border-amber-200"
        renal_tag = "Seguimiento"
        renal_tag_cls = "bg-amber-100 text-amber-800"
    else:
        renal_badge = "🟢 Normal"
        renal_badge_cls = "bg-emerald-50 text-emerald-700 border-emerald-200"
        renal_tag = "Normal"
        renal_tag_cls = "bg-emerald-100 text-emerald-800"

    # 4. Próstata (Evaluación multianalito: PSA Total, PSA Libre, Ratio Libre/Total)
    psa_t_val = get_v("PSA_TOTAL", "0.69")
    psa_f_val = get_v("PSA_FREE", "0.37")
    try:
        psa_num = float(psa_t_val.replace(",", "."))
    except Exception:
        psa_num = 0.69
    try:
        psa_f_num = float(psa_f_val.replace(",", "."))
        ratio_psa_pct = round((psa_f_num / psa_num) * 100) if psa_num > 0 else 54
    except Exception:
        ratio_psa_pct = 54

    if psa_num >= 4.0:
        psa_badge = "🔴 Atención (PSA)"
        psa_badge_cls = "bg-rose-50 text-rose-700 border-rose-200"
        psa_tag = "Atención"
        psa_tag_cls = "bg-rose-100 text-rose-800"
    elif psa_num > 0.40:
        psa_badge = "🟡 Seguimiento (PSA)"
        psa_badge_cls = "bg-amber-50 text-amber-800 border-amber-200"
        psa_tag = "Seguimiento"
        psa_tag_cls = "bg-amber-100 text-amber-800"
    else:
        psa_badge = "🟢 Normal"
        psa_badge_cls = "bg-emerald-50 text-emerald-700 border-emerald-200"
        psa_tag = "Normal"
        psa_tag_cls = "bg-emerald-100 text-emerald-800"

    # 5. Tiroides (TSH)
    try:
        tsh_num = float(get_v("TSH", "1.80").replace(",", "."))
    except Exception:
        tsh_num = 1.80
    if tsh_num > 10.0 or tsh_num < 0.1:
        tsh_badge = "🔴 Atención (TSH)"
        tsh_badge_cls = "bg-rose-50 text-rose-700 border-rose-200"
        tsh_tag = "Atención"
        tsh_tag_cls = "bg-rose-100 text-rose-800"
    elif tsh_num < 0.27 or tsh_num > 4.29:
        tsh_badge = "🟡 Seguimiento (TSH)"
        tsh_badge_cls = "bg-amber-50 text-amber-800 border-amber-200"
        tsh_tag = "Seguimiento"
        tsh_tag_cls = "bg-amber-100 text-amber-800"
    else:
        tsh_badge = "🟢 Normal"
        tsh_badge_cls = "bg-emerald-50 text-emerald-700 border-emerald-200"
        tsh_tag = "Normal"
        tsh_tag_cls = "bg-emerald-100 text-emerald-800"

    # 6. Vitamina D
    try:
        vitd_num = float(get_v("VITAMIN_D", "37.6").replace(",", "."))
    except Exception:
        vitd_num = 37.6
    if vitd_num < 15.0:
        vitd_badge = "🔴 Atención (Vitamina D)"
        vitd_badge_cls = "bg-rose-50 text-rose-700 border-rose-200"
        vitd_tag = "Atención"
        vitd_tag_cls = "bg-rose-100 text-rose-800"
    elif vitd_num < 30.0:
        vitd_badge = "🟡 Seguimiento (Vitamina D)"
        vitd_badge_cls = "bg-amber-50 text-amber-800 border-amber-200"
        vitd_tag = "Seguimiento"
        vitd_tag_cls = "bg-amber-100 text-amber-800"
    else:
        vitd_badge = "🟢 Normal"
        vitd_badge_cls = "bg-emerald-50 text-emerald-700 border-emerald-200"
        vitd_tag = "Normal"
        vitd_tag_cls = "bg-emerald-100 text-emerald-800"

    kpis = [
        KpiCard(
            title="Glucosa y Metabolismo",
            tag=glu_tag,
            tag_class=glu_tag_cls,
            main_label="Glucosa en ayunas",
            main_value=fmt(glu),
            unit="mg/dL",
            subtitle_1=f"HbA1c: {fmt(hba, 1)}%",
            subtitle_2=f"TG/HDL: {ratio_tg_hdl}",
            subtitle_3="",
            badge_text=glu_badge,
            badge_class=glu_badge_cls
        ),
        KpiCard(
            title="Perfil Lipídico",
            tag=lipid_tag,
            tag_class=lipid_tag_cls,
            main_label="Colesterol Total",
            main_value=fmt(col_t),
            unit="mg/dL",
            subtitle_1=f"LDL {fmt(ldl)} · HDL {fmt(hdl)} · TG {fmt(tg)}",
            subtitle_2=f"Col/HDL: {ratio_col_hdl}",
            subtitle_3=f"LDL/HDL: {ratio_ldl_hdl}",
            badge_text=lipid_badge,
            badge_class=lipid_badge_cls
        ),
        KpiCard(
            title="Función Renal",
            tag=renal_tag,
            tag_class=renal_tag_cls,
            main_label="Creatinina sérica",
            main_value=fmt(get_v("CREATININE", "0.84"), 2),
            unit="mg/dL",
            subtitle_1=f"Urea: {fmt(get_v('UREA', '45.0'))} mg/dL",
            subtitle_2=f"Ác. Úrico: {fmt(get_v('URIC_ACID', '6.1'), 1)} mg/dL",
            subtitle_3="",
            badge_text=renal_badge,
            badge_class=renal_badge_cls
        ),
        KpiCard(
            title="Próstata",
            tag=psa_tag,
            tag_class=psa_tag_cls,
            main_label="PSA Total",
            main_value=fmt(psa_t_val, 2),
            unit="ng/mL",
            subtitle_1=f"PSA Libre: {fmt(psa_f_val, 2)} ng/mL",
            subtitle_2=f"Ratio libre: {ratio_psa_pct}%",
            subtitle_3="",
            badge_text=psa_badge,
            badge_class=psa_badge_cls
        ),
        KpiCard(
            title="Tiroides",
            tag=tsh_tag,
            tag_class=tsh_tag_cls,
            main_label="Hormona TSH",
            main_value=fmt(get_v("TSH", "1.80"), 2),
            unit="µUI/mL",
            subtitle_1="Rango normal: 0.27 - 4.29",
            subtitle_2="",
            subtitle_3="",
            badge_text=tsh_badge,
            badge_class=tsh_badge_cls
        ),
        KpiCard(
            title="Vitamina D",
            tag=vitd_tag,
            tag_class=vitd_tag_cls,
            main_label="25-OH Vitamina D",
            main_value=fmt(get_v("VITAMIN_D", "37.6"), 1),
            unit="ng/mL",
            subtitle_1="Rango normal: > 30.0 ng/mL",
            subtitle_2="",
            subtitle_3="",
            badge_text=vitd_badge,
            badge_class=vitd_badge_cls
        )
    ]

    return DashboardSummaryResponse(
        paciente={
            "nombre": (paciente.nombre_completo if paciente and paciente.nombre_completo else "").strip(),
            "nacimiento": (paciente.fecha_nacimiento if paciente and paciente.fecha_nacimiento else "-"),
            "edad": calcular_edad(paciente.fecha_nacimiento) if paciente and paciente.fecha_nacimiento else "-",
            "dni": (paciente.dni if paciente and paciente.dni else "-"),
            "sexo": (paciente.sexo if paciente and paciente.sexo else "No especificado")
        },
        total_controles=total_controles,
        periodo_historico=periodo,
        ultima_fecha=ultima_fecha,
        dictamen_global=ultimo_informe.dictamen_global or "Favorable",
        dictamen_subtitulo=ultimo_informe.observaciones_ia or "Parámetros analizados por el sistema",
        kpis=kpis,
        motor_llm_info=motor_info,
        app_version=__version__
    )

@router.get("/paciente", response_model=PacienteInfo)
def get_paciente(db: Session = Depends(get_db)):
    """
    Obtiene los datos del paciente registrado en la aplicación.
    """
    paciente = db.query(Paciente).first()
    if not paciente:
        return PacienteInfo(
            id=None,
            nombre_completo="",
            fecha_nacimiento=None,
            dni=None,
            sexo="No especificado",
            edad="-"
        )
    return PacienteInfo(
        id=paciente.id,
        nombre_completo=paciente.nombre_completo or "",
        fecha_nacimiento=paciente.fecha_nacimiento,
        dni=paciente.dni,
        sexo=paciente.sexo if paciente.sexo in ["Masculino", "Femenino"] else "No especificado",
        edad=calcular_edad(paciente.fecha_nacimiento)
    )

@router.put("/paciente", response_model=PacienteInfo)
def update_paciente(payload: PacienteUpdateRequest, db: Session = Depends(get_db)):
    """
    Actualiza la ficha de datos personales del paciente.
    """
    paciente = db.query(Paciente).first()
    if not paciente:
        paciente = Paciente(
            nombre_completo=(payload.nombre_completo or "").strip()
        )
        db.add(paciente)

    paciente.nombre_completo = (payload.nombre_completo or "").strip()
    paciente.fecha_nacimiento = payload.fecha_nacimiento.strip() if payload.fecha_nacimiento else None
    paciente.dni = payload.dni.strip() if payload.dni else None
    paciente.sexo = payload.sexo.strip() if payload.sexo in ["Masculino", "Femenino"] else "No especificado"

    db.commit()
    db.refresh(paciente)

    return PacienteInfo(
        id=paciente.id,
        nombre_completo=paciente.nombre_completo or "",
        fecha_nacimiento=paciente.fecha_nacimiento,
        dni=paciente.dni,
        sexo=paciente.sexo or "No especificado",
        edad=calcular_edad(paciente.fecha_nacimiento)
    )

@router.get("/tables", response_model=TablesResponse)
def get_tables(db: Session = Depends(get_db)):
    """
    Devuelve los datos estructurados para las tablas de Bioquímica,
    Hemograma, Coagulación y Enzimas e Iones.
    """
    informes = db.query(Informe).order_by(Informe.fecha.asc()).all()
    dates = [inf.etiqueta_corta for inf in informes]
    informe_ids = [inf.id for inf in informes]
    
    # Identificar índices de los controles dentro de los últimos 18 meses (respecto a la última analítica)
    recent_indices = []
    if informes:
        try:
            from datetime import datetime, timedelta
            ultima_fecha_dt = datetime.strptime(informes[-1].fecha, "%Y-%m-%d").date()
            cutoff_18m = ultima_fecha_dt - timedelta(days=548)  # ~18 meses
            recent_indices = [
                idx for idx, inf in enumerate(informes)
                if datetime.strptime(inf.fecha, "%Y-%m-%d").date() >= cutoff_18m
            ]
        except Exception:
            recent_indices = [idx for idx, inf in enumerate(informes) if idx >= max(0, len(informes) - 3)]
    if not recent_indices and informes:
        recent_indices = [len(informes) - 1]

    analitos = db.query(Analito).order_by(Analito.orden.asc(), Analito.id.asc()).all()
    
    bio_rows = []
    for a in analitos:
        meds = db.query(Medicion).filter_by(analito_id=a.id).all()
        if not meds:
            continue
        med_by_inf = {m.informe_id: (m.valor_numerico if m.valor_numerico is not None else m.valor_texto) for m in meds}
        
        vals = [med_by_inf.get(inf_id, None) for inf_id in informe_ids]
        
        # Calcular promedio reciente (últimos 18 meses)
        recent_vals = [vals[i] for i in recent_indices if i < len(vals)]
        num_vals_recent = [v for v in recent_vals if isinstance(v, (int, float))]
        avg_recent = f"{sum(num_vals_recent) / len(num_vals_recent):.1f}" if num_vals_recent else "-"
        
        # Ajustes de decimales específicos
        if a.codigo in ["CREATININE", "TSH", "PSA_TOTAL", "PSA_FREE", "RATIO_PSA_L_T", "RATIO_COL_HDL", "RATIO_LDL_HDL", "RATIO_TG_HDL"]:
            if num_vals_recent:
                avg_recent = f"{sum(num_vals_recent) / len(num_vals_recent):.2f}"

        bio_rows.append(TableRow(
            name=a.nombre_visible,
            unit=a.unidad_estandar,
            ref=a.ref_texto_defecto or "",
            vals=vals,
            recentAvg=avg_recent,
            avg=avg_recent,
            group=get_analito_group(a.codigo)
        ))

    # Paneles de muestra para demostración
    hem_data = [
        ['Hematíes', '10^6/µL', '4.80', '4.85', '4.78', '4.90', '4.82', '4.81', '4.83', '4.82', '4.00 - 5.65', 'Normal'],
        ['Hemoglobina', 'g/dL', '15.2', '15.4', '15.0', '15.3', '15.1', '15.2', '15.3', '15.2', '12.5 - 17.2', 'Óptimo (Normal)'],
        ['Hematocrito', '%', '45.0', '44.8', '45.2', '44.5', '45.1', '44.9', '45.0', '45.0', '37.0 - 49.0', 'Normal'],
        ['Plaquetas', '10^3/µL', '240', '245', '238', '242', '240', '241', '240', '241', '140 - 370', 'Óptimo'],
        ['Leucocitos', '10^3/µL', '5.10', '5.20', '4.90', '5.15', '5.05', '5.08', '5.10', '5.08', '3.60 - 10.50', 'Normal']
    ]

    coag_data = [
        ['Tiempo de Protrombina', 'segundos', '11.5', '11.8', '11.2', '11.4', '11.5', '11.5', '11.5', '11.5', '10.0 - 14.5', 'Normal'],
        ['Índice de Quick', '%', '105', '102', '108', '100', '104', '103', '104', '104', '70 - 130 %', 'Normocoagulado'],
        ['INR', 'ratio', '0.95', '0.98', '0.94', '0.97', '0.96', '0.96', '0.96', '0.96', '0.85 - 1.15', 'Óptimo']
    ]

    enz_data = [
        ['GOT / AST', 'U/L', '22', '24', '20', '23', '21', '22', '22', '22', 'Inf. 40', 'Óptimo'],
        ['GPT / ALT', 'U/L', '21', '23', '19', '22', '20', '21', '21', '21', '10 - 49', 'Óptimo'],
        ['GGT', 'U/L', '18', '16', '17', '15', '16', '16', '16', '16', 'Inf. 60', 'Excelente'],
        ['TSH (Tiroides)', 'µUI/mL', '1.45', '1.80', '1.65', '2.10', '2.20', '1.84', '1.84', '1.84', '0.27 - 4.29', 'Óptimo (Eutiroideo)']
    ]

    informes_meta = [
        {
            "id": inf.id,
            "fecha": inf.fecha,
            "etiqueta_corta": inf.etiqueta_corta,
            "laboratorio": inf.laboratorio or "Desconocido"
        }
        for inf in informes
    ]

    return TablesResponse(
        dates=dates,
        informes=informes_meta,
        bioquimica=bio_rows,
        hemograma=hem_data,
        coagulacion=coag_data,
        enzimas=enz_data
    )

@router.get("/charts", response_model=ChartsResponse)
def get_charts_data(db: Session = Depends(get_db)):
    """
    Devuelve los datasets para Chart.js configurados para los 8 gráficos visuales.
    """
    informes = db.query(Informe).order_by(Informe.fecha.asc()).all()
    dates = [inf.etiqueta_corta for inf in informes]
    informe_ids = [inf.id for inf in informes]

    def get_series(*codigos: str):
        analitos = db.query(Analito).filter(Analito.codigo.in_(codigos)).all()
        if not analitos:
            return [None] * len(informe_ids)
        a_ids = [a.id for a in analitos]
        meds = db.query(Medicion).filter(Medicion.analito_id.in_(a_ids)).all()
        med_map = {}
        for m in meds:
            if m.valor_numerico is not None:
                med_map[m.informe_id] = m.valor_numerico
        return [med_map.get(i_id, None) for i_id in informe_ids]

    glucosa_vals = get_series("GLUCOSE", "GLUCOSA")
    col_t_vals = get_series("CHOLESTEROL_TOTAL", "COLESTEROL_TOTAL", "COLESTEROL")
    hdl_vals = get_series("HDL", "HDL_COLESTEROL")
    ldl_vals = get_series("LDL", "LDL_COLESTEROL")
    tg_vals = get_series("TRIGLYCERIDES", "TRIGLICERIDOS")
    urea_vals = get_series("UREA")
    creat_vals = get_series("CREATININE", "CREATININA")
    urico_vals = get_series("URIC_ACID", "ACIDO_URICO")
    psa_t_vals = get_series("PSA_TOTAL", "PSA")
    psa_free_vals = get_series("PSA_FREE", "PSA_LIBRE")
    tsh_vals = get_series("TSH")

    # Ratios con fallback calculado dinámicamente si no estaban guardados en BD
    raw_castelli1 = get_series("RATIO_COL_HDL", "COCIENTE_COL_HDL")
    castelli1_vals = []
    for idx, i_id in enumerate(informe_ids):
        val = raw_castelli1[idx]
        if val is None and col_t_vals[idx] is not None and hdl_vals[idx] and hdl_vals[idx] > 0:
            val = round(col_t_vals[idx] / hdl_vals[idx], 2)
        castelli1_vals.append(val)

    raw_castelli2 = get_series("RATIO_LDL_HDL", "COCIENTE_LDL_HDL")
    castelli2_vals = []
    for idx, i_id in enumerate(informe_ids):
        val = raw_castelli2[idx]
        if val is None and ldl_vals[idx] is not None and hdl_vals[idx] and hdl_vals[idx] > 0:
            val = round(ldl_vals[idx] / hdl_vals[idx], 2)
        castelli2_vals.append(val)

    raw_tg_hdl = get_series("RATIO_TG_HDL", "COCIENTE_TG_HDL")
    tg_hdl_vals = []
    for idx, i_id in enumerate(informe_ids):
        val = raw_tg_hdl[idx]
        if val is None and tg_vals[idx] is not None and hdl_vals[idx] and hdl_vals[idx] > 0:
            val = round(tg_vals[idx] / hdl_vals[idx], 2)
        tg_hdl_vals.append(val)

    raw_psa_ratio = get_series("RATIO_PSA_L_T", "RATIO_PSA")
    psa_ratio_vals = []
    for idx, i_id in enumerate(informe_ids):
        val = raw_psa_ratio[idx]
        if val is not None:
            if val <= 1.0:
                val = round(val * 100, 1)
            else:
                val = round(val, 1)
        elif psa_free_vals[idx] is not None and psa_t_vals[idx] and psa_t_vals[idx] > 0:
            val = round((psa_free_vals[idx] / psa_t_vals[idx]) * 100, 1)
        psa_ratio_vals.append(val)

    return ChartsResponse(
        glucosa=ChartConfig(
            labels=dates,
            datasets=[
                ChartDataset(
                    label="Glucosa Basal (mg/dL)",
                    data=glucosa_vals,
                    borderColor="#2563eb",
                    backgroundColor="rgba(37, 99, 235, 0.1)",
                    borderWidth=2.5,
                    fill=True,
                    yAxisID="y"
                )
            ]
        ),
        lipidos=ChartConfig(
            labels=dates,
            datasets=[
                ChartDataset(label="Colesterol Total", data=col_t_vals, borderColor="#2563eb", borderWidth=2.5, yAxisID="y"),
                ChartDataset(label="LDL-Colesterol", data=ldl_vals, borderColor="#f59e0b", borderWidth=2.5, yAxisID="y"),
                ChartDataset(label="HDL-Colesterol", data=hdl_vals, borderColor="#10b981", borderWidth=2.0, yAxisID="y"),
                ChartDataset(label="Triglicéridos", data=tg_vals, borderColor="#8b5cf6", borderWidth=1.5, yAxisID="y")
            ]
        ),
        castelli=ChartConfig(
            labels=dates,
            datasets=[
                ChartDataset(label="Castelli I: Col.T / HDL (Ref < 5.0)", data=castelli1_vals, borderColor="#8b5cf6", backgroundColor="rgba(139, 92, 246, 0.1)", borderWidth=2.5, yAxisID="y"),
                ChartDataset(label="Castelli II: LDL / HDL (Ref < 4.3)", data=castelli2_vals, borderColor="#ec4899", backgroundColor="rgba(236, 72, 153, 0.1)", borderWidth=2.5, yAxisID="y")
            ]
        ),
        ratios_tg=ChartConfig(
            labels=dates,
            datasets=[
                ChartDataset(
                    label="Triglicéridos / HDL (Ref < 2.0)",
                    data=tg_hdl_vals,
                    borderColor="#06b6d4",
                    backgroundColor="rgba(6, 182, 212, 0.15)",
                    borderWidth=2.5,
                    fill=True,
                    yAxisID="y"
                )
            ]
        ),
        renal=ChartConfig(
            labels=dates,
            datasets=[
                ChartDataset(label="Urea (mg/dL)", data=urea_vals, borderColor="#3b82f6", borderWidth=2.0, yAxisID="y"),
                ChartDataset(label="Creatinina (mg/dL)", data=creat_vals, borderColor="#8b5cf6", borderWidth=2.0, yAxisID="y1")
            ]
        ),
        urico=ChartConfig(
            labels=dates,
            datasets=[
                ChartDataset(label="Ácido Úrico (mg/dL)", data=urico_vals, borderColor="#059669", backgroundColor="rgba(5, 150, 105, 0.1)", borderWidth=2.5, fill=True, yAxisID="y")
            ]
        ),
        psa=ChartConfig(
            labels=dates,
            datasets=[
                ChartDataset(label="PSA Total (ng/mL)", data=psa_t_vals, borderColor="#8b5cf6", borderWidth=2.5, yAxisID="y"),
                ChartDataset(label="Ratio PSA L/T (%)", data=psa_ratio_vals, borderColor="#10b981", borderWidth=2.0, yAxisID="y1")
            ]
        ),
        tsh=ChartConfig(
            labels=dates,
            datasets=[
                ChartDataset(label="TSH (µUI/mL)", data=tsh_vals, borderColor="#0284c7", backgroundColor="rgba(2, 132, 199, 0.1)", borderWidth=2.0, fill=True, yAxisID="y")
            ]
        )
    )

@router.get("/files", response_model=List[AuditFileItem])
def get_audit_files(db: Session = Depends(get_db)):
    """
    Devuelve el inventario completo de archivos de analíticas subidos al sistema.
    """
    informes = db.query(Informe).order_by(Informe.fecha.desc(), Informe.id.desc()).all()
    res = []
    for inf in informes:
        res.append(AuditFileItem(
            id=inf.id,
            fecha=inf.fecha,
            etiqueta_corta=inf.etiqueta_corta,
            laboratorio=inf.laboratorio or "Desconocido",
            facultativo=inf.facultativo or "No especificado",
            archivo_pdf=inf.archivo_pdf,
            total_mediciones=len(inf.mediciones),
            dictamen_global=inf.dictamen_global or "Sin dictamen",
            created_at=inf.created_at.strftime("%Y-%m-%d %H:%M") if inf.created_at else None
        ))
    return res

@router.delete("/files/{informe_id}")
def delete_audit_file(informe_id: int, db: Session = Depends(get_db)):
    """
    Elimina una analítica y sus mediciones asociadas de la base de datos.
    """
    informe = db.query(Informe).filter_by(id=informe_id).first()
    if not informe:
        raise HTTPException(status_code=404, detail="Analítica no encontrada")

    if informe.archivo_pdf:
        pdf_path = settings.DATA_DIR / "uploads" / informe.archivo_pdf
        if pdf_path.exists():
            try:
                pdf_path.unlink()
            except Exception:
                pass

    db.delete(informe)
    db.commit()
    return {"status": "success", "message": f"Analítica ID {informe_id} eliminada correctamente"}

@router.get("/catalog")
def get_canonical_catalog():
    """
    Devuelve el catálogo canónico estructurado y agrupado por especialidad clínica
    para alimentar los selectores de analitos y evitar inconsistencias en la base de datos.
    """
    from app.services.analito_normalizer import CANONICAL_CATALOG
    grouped = {}
    for code, item in CANONICAL_CATALOG.items():
        if item.get("es_ratio") or code.startswith("RATIO_"):
            continue
        g = item.get("grupo", "Otras Determinaciones")
        grouped.setdefault(g, []).append({
            "codigo": code,
            "nombre": item["nombre"],
            "unidad": item.get("unidad", ""),
            "ref": item.get("ref", "")
        })
    return grouped

@router.get("/informes/{informe_id}", response_model=InformeDetailResponse)
def get_informe_detail(informe_id: int, db: Session = Depends(get_db)):
    """
    Devuelve los metadatos completos y todas las mediciones de un informe específico para su edición.
    """
    informe = db.query(Informe).filter_by(id=informe_id).first()
    if not informe:
        raise HTTPException(status_code=404, detail="Analítica no encontrada")

    mediciones_db = (
        db.query(Medicion)
        .join(Analito, Medicion.analito_id == Analito.id)
        .filter(Medicion.informe_id == informe.id)
        .order_by(Analito.orden.asc(), Analito.nombre_visible.asc(), Medicion.id.asc())
        .all()
    )

    ratio_codes = {
        "RATIO_COL_HDL", "RATIO_LDL_HDL", "RATIO_TG_HDL",
        "RATIO_LDL_COL", "RATIO_HDL_COL", "RATIO_TG_COL", "RATIO_PSA_L_T"
    }

    mediciones_list = []
    for m in mediciones_db:
        codigo = m.analito.codigo if m.analito else ""
        nombre = m.analito.nombre_visible if m.analito else "Desconocido"
        val = m.valor_numerico if m.valor_numerico is not None else (m.valor_texto or "")
        mediciones_list.append(MedicionDetail(
            id=m.id,
            codigo=codigo,
            nombre=nombre,
            valor=val,
            unidad=m.unidad or (m.analito.unidad_estandar if m.analito else ""),
            rango_referencia=m.ref_texto or (m.analito.ref_texto_defecto if m.analito else ""),
            estado_estimado=m.estado_semaforo or "Normal",
            es_ratio=(codigo in ratio_codes)
        ))

    return InformeDetailResponse(
        id=informe.id,
        fecha=informe.fecha,
        etiqueta_corta=informe.etiqueta_corta,
        laboratorio=informe.laboratorio or "",
        facultativo=informe.facultativo or "",
        dictamen_global=informe.dictamen_global or "",
        archivo_pdf=informe.archivo_pdf,
        mediciones=mediciones_list
    )

@router.put("/informes/{informe_id}")
def update_informe(informe_id: int, req: InformeUpdateRequest, db: Session = Depends(get_db)):
    """
    Actualiza los metadatos y mediciones de un informe ya guardado en la base de datos.
    Recalcula automáticamente los ratios dependientes (Castelli, TG/HDL, PSA, etc.).
    """
    informe = db.query(Informe).filter_by(id=informe_id).first()
    if not informe:
        raise HTTPException(status_code=404, detail="Analítica no encontrada")

    # 1. Actualizar metadatos del informe
    informe.fecha = req.fecha
    partes_fecha = req.fecha.split("-")
    if len(partes_fecha) == 3:
        informe.etiqueta_corta = f"{partes_fecha[2]}/{partes_fecha[1]}/{partes_fecha[0][2:]}"
    else:
        informe.etiqueta_corta = req.fecha

    informe.laboratorio = req.laboratorio
    informe.facultativo = req.facultativo or "No especificado"
    informe.dictamen_global = req.dictamen_global or "Control favorable"

    # 2. Borrar mediciones previas asociadas a este informe para sincronización limpia
    db.query(Medicion).filter_by(informe_id=informe.id).delete()
    db.flush()

    # 3. Procesar mediciones del request
    mediciones_dict = {}
    analitos_procesados = {}

    ratio_codes = {
        "RATIO_COL_HDL", "RATIO_LDL_HDL", "RATIO_TG_HDL",
        "RATIO_LDL_COL", "RATIO_HDL_COL", "RATIO_TG_COL", "RATIO_PSA_L_T"
    }

    for item in req.mediciones:
        if not item.nombre or not item.nombre.strip():
            continue

        # Si el usuario no modificó manualmente un ratio calculado, se recalculará automáticamente abajo
        if item.codigo in ratio_codes and item.es_ratio:
            continue

        code_key, norm_nombre, norm_cat, norm_unit = normalize_analito(
            item.nombre,
            unidad=item.unidad,
            valor=item.valor,
            codigo_sugerido=item.codigo
        )

        analito = db.query(Analito).filter_by(codigo=code_key).first()
        if not analito:
            analito = Analito(
                codigo=code_key,
                nombre_visible=norm_nombre,
                categoria=norm_cat,
                unidad_estandar=norm_unit,
                ref_texto_defecto=item.rango_referencia,
                orden=get_analito_order(code_key)
            )
            db.add(analito)
            db.flush()

        num_val, _ = normalize_valor_numerico(code_key, item.valor, item.unidad)
        if num_val is None:
            try:
                num_val = float(str(item.valor).replace(",", ".").split()[0])
            except (ValueError, TypeError, IndexError):
                num_val = None

        if code_key in analitos_procesados:
            med_existente = analitos_procesados[code_key]
            if med_existente.valor_numerico is None and num_val is not None:
                med_existente.valor_numerico = num_val
                med_existente.valor_texto = None
                med_existente.unidad = item.unidad or norm_unit
                med_existente.ref_texto = item.rango_referencia
                mediciones_dict[code_key] = num_val
            continue

        med = Medicion(
            informe_id=informe.id,
            analito_id=analito.id,
            valor_numerico=num_val,
            valor_texto=str(item.valor) if num_val is None else None,
            unidad=item.unidad or norm_unit,
            ref_texto=item.rango_referencia,
            estado_semaforo=getattr(item, "estado_estimado", None) or "Normal"
        )
        db.add(med)
        db.flush()
        analitos_procesados[code_key] = med

        if num_val is not None:
            mediciones_dict[code_key] = num_val

    # 4. Recalcular ratios automáticos derivados y guardarlos
    ratios_calc = calculate_ratios(mediciones_dict)
    ratio_names = {
        "RATIO_COL_HDL": ("Colesterol Total / HDL (Castelli I)", "ratio", "< 5.0"),
        "RATIO_LDL_HDL": ("LDL / HDL (Castelli II)", "ratio", "< 4.3"),
        "RATIO_TG_HDL": ("Triglicéridos / HDL", "ratio", "< 2.0"),
        "RATIO_LDL_COL": ("Ratio LDL / Col. Total", "ratio", "< 0.65"),
        "RATIO_HDL_COL": ("Ratio HDL / Col. Total", "ratio", "> 0.20"),
        "RATIO_TG_COL": ("Ratio TG / Col. Total", "ratio", "< 0.50"),
        "RATIO_PSA_L_T": ("Ratio PSA Libre / Total", "%", "> 20 %")
    }

    for r_code, r_val in ratios_calc.items():
        if r_code in analitos_procesados and analitos_procesados[r_code].valor_numerico is not None:
            continue

        nom, uni, ref = ratio_names.get(r_code, (r_code, "ratio", ""))
        a_ratio = db.query(Analito).filter_by(codigo=r_code).first()
        if not a_ratio:
            a_ratio = Analito(
                codigo=r_code,
                nombre_visible=nom,
                categoria="bioquimica",
                unidad_estandar=uni,
                ref_texto_defecto=ref,
                orden=get_analito_order(r_code)
            )
            db.add(a_ratio)
            db.flush()

        med_ratio = Medicion(
            informe_id=informe.id,
            analito_id=a_ratio.id,
            valor_numerico=r_val,
            unidad=uni,
            ref_texto=ref
        )
        db.add(med_ratio)

    db.commit()
    return {
        "status": "success",
        "message": f"Analítica del {informe.fecha} actualizada correctamente.",
        "informe_id": informe.id
    }


