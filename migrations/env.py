from alembic import context

from local_ai_notes.db import database_engine

engine = database_engine()
with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=None, transaction_per_migration=True)
    with context.begin_transaction():
        context.run_migrations()
engine.dispose()
