from sqlalchemy import Column, Integer, String, Float, Text, Date, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from app.database import Base
from app.time_utils import utc_now

class Paciente(Base):
    __tablename__ = "pacientes"

    id = Column(Integer, primary_key=True, index=True)
    nombre_completo = Column(String(200), nullable=False)
    fecha_nacimiento = Column(String(50), nullable=True) # YYYY-MM-DD
    dni = Column(String(50), nullable=True)
    sexo = Column(String(20), nullable=True)
    centro_referencia = Column(String(200), nullable=True)

    informes = relationship("Informe", back_populates="paciente", cascade="all, delete-orphan")


class Informe(Base):
    __tablename__ = "informes"

    id = Column(Integer, primary_key=True, index=True)
    paciente_id = Column(Integer, ForeignKey("pacientes.id"), nullable=False)
    fecha = Column(String(10), nullable=False, index=True) # YYYY-MM-DD
    etiqueta_corta = Column(String(20), nullable=False)    # DD/MM/AA
    laboratorio = Column(String(150), nullable=True)
    facultativo = Column(String(150), nullable=True)
    referencia = Column(String(100), nullable=True) # Número de referencia / petición / protocolo
    archivo_pdf = Column(String(255), nullable=True)
    sha256 = Column(String(64), nullable=True, unique=True)
    
    dictamen_global = Column(String(200), nullable=True)
    observaciones_ia = Column(Text, nullable=True)
    estado = Column(String(20), default="confirmado") # 'borrador' o 'confirmado'
    created_at = Column(DateTime(timezone=True), default=utc_now)

    paciente = relationship("Paciente", back_populates="informes")
    mediciones = relationship("Medicion", back_populates="informe", cascade="all, delete-orphan")
    auditorias_rango = relationship("AuditoriaRango", back_populates="informe", cascade="all, delete-orphan")


class Analito(Base):
    __tablename__ = "analitos"

    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String(50), unique=True, nullable=False, index=True)
    nombre_visible = Column(String(100), nullable=False)
    categoria = Column(String(50), nullable=False, index=True) # 'bioquimica', 'hemograma', 'coagulacion', 'enzimas_iones'
    unidad_estandar = Column(String(50), nullable=False)
    ref_texto_defecto = Column(String(100), nullable=True)
    orden = Column(Integer, default=0)

    mediciones = relationship("Medicion", back_populates="analito")
    auditorias = relationship("AuditoriaRango", back_populates="analito")


class Medicion(Base):
    __tablename__ = "mediciones"

    id = Column(Integer, primary_key=True, index=True)
    informe_id = Column(Integer, ForeignKey("informes.id"), nullable=False, index=True)
    analito_id = Column(Integer, ForeignKey("analitos.id"), nullable=False, index=True)
    
    valor_numerico = Column(Float, nullable=True)
    valor_texto = Column(String(50), nullable=True)
    unidad = Column(String(50), nullable=False)
    
    ref_min = Column(Float, nullable=True)
    ref_max = Column(Float, nullable=True)
    ref_texto = Column(String(100), nullable=True)
    
    estado_semaforo = Column(String(50), nullable=True) # 'optimo', 'bueno', 'atencion', 'alto', 'bajo'
    nota_clinica = Column(String(200), nullable=True)

    informe = relationship("Informe", back_populates="mediciones")
    analito = relationship("Analito", back_populates="mediciones")


class AuditoriaRango(Base):
    __tablename__ = "auditorias_rango"

    id = Column(Integer, primary_key=True, index=True)
    analito_id = Column(Integer, ForeignKey("analitos.id"), nullable=False)
    informe_id = Column(Integer, ForeignKey("informes.id"), nullable=False)
    rango_anterior = Column(String(100), nullable=True)
    rango_nuevo = Column(String(100), nullable=False)
    explicacion_ia = Column(Text, nullable=True)
    fecha_deteccion = Column(DateTime(timezone=True), default=utc_now)
    aplicado_en_historico = Column(Boolean, default=False)
    fecha_aplicacion = Column(DateTime, nullable=True)
    estado = Column(String(30), default="pendiente")  # 'pendiente', 'aplicado', 'mantenido'

    analito = relationship("Analito", back_populates="auditorias")
    informe = relationship("Informe", back_populates="auditorias_rango")
