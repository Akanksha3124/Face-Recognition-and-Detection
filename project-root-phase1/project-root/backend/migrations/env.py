"""
Alembic migration environment.
Actual model metadata is wired in once app/models/* exist (Phase 2).
"""
from logging.config import fileConfig
from alembic import context

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None  # set to Base.metadata in Phase 2


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    raise NotImplementedError("Wired up in Phase 2 with the real engine")


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
