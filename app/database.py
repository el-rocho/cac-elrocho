from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.config import settings

# Engine SQLite con configuración optimizada
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    echo=False
)

# Activar WAL mode y claves foráneas en SQLite
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if settings.database_url.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# SQLite no actualiza tablas existentes al llamar a ``create_all``. Estas
# migraciones son aditivas e idempotentes para conservar las instalaciones que
# ya tienen datos clínicos de versiones anteriores.
SQLITE_COLUMN_MIGRATIONS = {
    "pacientes": {
        "centro_referencia": "VARCHAR(200)",
    },
    "informes": {
        "referencia": "VARCHAR(100)",
        "sha256": "VARCHAR(64)",
        "estado": "VARCHAR(20) DEFAULT 'confirmado'",
        "created_at": "DATETIME",
    },
    "mediciones": {
        "estado_semaforo": "VARCHAR(50)",
    },
    "auditorias_rango": {
        "aplicado_en_historico": "BOOLEAN DEFAULT 0",
        "fecha_aplicacion": "DATETIME",
        "estado": "VARCHAR(30) DEFAULT 'pendiente'",
    },
}

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def migrate_sqlite_schema(bind=engine) -> None:
    """Añade columnas introducidas en versiones posteriores sin tocar datos."""
    if bind.dialect.name != "sqlite":
        return

    schema = inspect(bind)
    table_names = set(schema.get_table_names())
    with bind.begin() as connection:
        for table, columns in SQLITE_COLUMN_MIGRATIONS.items():
            if table not in table_names:
                continue
            existing_columns = {column["name"] for column in schema.get_columns(table)}
            for column, definition in columns.items():
                if column not in existing_columns:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))


def init_db():
    # Importar modelos para que Base.metadata los reconozca
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    migrate_sqlite_schema()


def close_database():
    """Libera las conexiones SQLite al finalizar el proceso FastAPI."""
    engine.dispose()
