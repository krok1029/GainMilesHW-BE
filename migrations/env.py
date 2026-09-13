from logging.config import fileConfig

from alembic import context
from flask import current_app

from app.extensions import db

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)


def run_migrations_offline() -> None:
    context.configure(
        url=db.engine.url,
        target_metadata=db.metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with db.engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=db.metadata,
            **current_app.extensions["migrate"].configure_args,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
