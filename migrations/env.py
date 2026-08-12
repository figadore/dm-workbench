"""Alembic runtime configured only from validated environment settings."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from dm_assistant.config import load_database_settings
from dm_assistant.db import Base
from dm_assistant.modules.campaign_knowledge import models as campaign_knowledge_models
from dm_assistant.modules.library import models as library_models
from dm_assistant.modules.preparation import models as preparation_models

assert campaign_knowledge_models.CampaignEntity.__tablename__ == "campaign_entity"
assert library_models.Document.__tablename__ == "document"
assert preparation_models.PreparationArtifact.__tablename__ == "prep_artifact"

config = context.config
if config.config_file_name is not None and config.file_config.has_section("loggers"):
    fileConfig(config.config_file_name)

database_url = load_database_settings().database_url.get_secret_value()
config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without creating an Engine."""
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in one non-pooled operational connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        hide_parameters=True,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
