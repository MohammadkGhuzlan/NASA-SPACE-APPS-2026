from alembic import context
from backend.database import engine, Base
from backend import models  # noqa: F401

target_metadata = Base.metadata
with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()
