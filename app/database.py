from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.config import settings

# Engine SQLite con configuración optimizada
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False
)

# Activar WAL mode y claves foráneas en SQLite
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if settings.DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    # Importar modelos para que Base.metadata los reconozca
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)

    # Migración automática si las columnas no existen en SQLite
    try:
        with engine.connect() as conn:
            columns_pacientes = conn.execute(text("PRAGMA table_info(pacientes)")).fetchall()
            col_pacientes = [col[1] for col in columns_pacientes]
            if columns_pacientes and "sexo" not in col_pacientes:
                conn.execute(text("ALTER TABLE pacientes ADD COLUMN sexo VARCHAR(20)"))
                conn.commit()

            columns_auditorias = conn.execute(text("PRAGMA table_info(auditorias_rango)")).fetchall()
            col_auditorias = [col[1] for col in columns_auditorias]
            if columns_auditorias:
                if "aplicado_en_historico" not in col_auditorias:
                    conn.execute(text("ALTER TABLE auditorias_rango ADD COLUMN aplicado_en_historico BOOLEAN DEFAULT 0"))
                if "fecha_aplicacion" not in col_auditorias:
                    conn.execute(text("ALTER TABLE auditorias_rango ADD COLUMN fecha_aplicacion DATETIME"))
                if "estado" not in col_auditorias:
                    conn.execute(text("ALTER TABLE auditorias_rango ADD COLUMN estado VARCHAR(30) DEFAULT 'pendiente'"))
                    conn.execute(text("UPDATE auditorias_rango SET estado = 'aplicado' WHERE aplicado_en_historico = 1"))
                conn.commit()
    except Exception:
        pass
