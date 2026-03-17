import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Importar el Base con todos los modelos para autogenerate
from models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Registrar los metadatos de los modelos (habilita --autogenerate)
target_metadata = Base.metadata

def get_url() -> str:
    """
    Lee la URL de la base de datos desde la variable de entorno POSTGRES_DSN.
    Alembic usa SQLAlchemy sincrónico, por eso reemplazamos el driver asyncpg.
    """
    dsn = os.getenv("POSTGRES_DSN", "")
    # Normalizar el esquema de la URL para SQLAlchemy sincrónico:
    # - postgresql+asyncpg:// → postgresql://  (FastAPI async driver)
    # - postgres://           → postgresql://  (formato corto usado por algunos providers)
    dsn = dsn.replace("postgresql+asyncpg://", "postgresql://")
    if dsn.startswith("postgres://"):
        dsn = dsn.replace("postgres://", "postgresql://", 1)
    return dsn


def run_migrations_offline() -> None:
    """Corre migraciones sin conectar a la DB (genera SQL puro)."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Corre migraciones conectándose directamente a la DB."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
