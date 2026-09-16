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

    # Migración automática si la columna 'sexo' no existe en 'pacientes' (SQLite)
    try:
        with engine.connect() as conn:
            columns_info = conn.execute(text("PRAGMA table_info(pacientes)")).fetchall()
            col_names = [col[1] for col in columns_info]
            if columns_info and "sexo" not in col_names:
                conn.execute(text("ALTER TABLE pacientes ADD COLUMN sexo VARCHAR(20)"))
                conn.commit()
    except Exception:
        pass
