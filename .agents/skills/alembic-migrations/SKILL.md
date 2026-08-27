---
name: alembic-migrations
description: How to run, check, downgrade, and write Alembic migrations for the fastapi_webapi database (including foreign key changes). Use whenever creating, applying, or reviewing a migration in migrations/versions.
---

# Alembic Migrations (fastapi_webapi)

All commands run from the `fastapi_webapi` directory, using `uv run` so the project's virtualenv is used.

```
cd fastapi_webapi
```

## Run a migration (upgrade to latest)

```
uv run alembic upgrade head
```

To upgrade by a relative number of revisions instead of jumping to head:

```
uv run alembic upgrade +1
```

To upgrade to a specific revision:

```
uv run alembic upgrade <revision_id>
```

## Check current version

```
uv run alembic current
```

Show full migration history (and where `current` sits in it):

```
uv run alembic history --verbose
```

## Downgrade

Downgrade one revision:

```
uv run alembic downgrade -1
```

Downgrade to a specific revision:

```
uv run alembic downgrade <revision_id>
```

Downgrade all the way (empty schema):

```
uv run alembic downgrade base
```

Every migration in this repo implements a real `downgrade()` that reverses `upgrade()` — never leave it as `pass`.

## Creating a new migration

Generate a revision file (edit it by hand afterward — this repo does not rely on autogenerate):

```
uv run alembic revision -m "short description"
```

Conventions used in `migrations/versions/`:

- Filename: `YYYYMMDD_NN_short_description.py` (date of authoring + sequence number for that day).
- `revision` matches the filename's `YYYYMMDD_NN` id; `down_revision` points at the previous revision in the chain (check `uv run alembic history` or the latest file in `migrations/versions/` if unsure).
- Docstring at the top of the file: one-line summary, blank line, then Revision/Revises/Create Date, then (optional but preferred) a short paragraph explaining *why* the change is needed — not just what it does. See [20260817_02_create_fct_document_first_action.py](../../../fastapi_webapi/migrations/versions/20260817_02_create_fct_document_first_action.py) and [20260818_01_add_process_message_id.py](../../../fastapi_webapi/migrations/versions/20260818_01_add_process_message_id.py) for examples.
- Every `upgrade()` must have a matching `downgrade()` that fully reverses it, applied in opposite order of operations.

## Changing a foreign key

Postgres cannot `ALTER` a foreign key's target/columns/delete-rule in place — drop the constraint and recreate it. Pattern (from [20260818_01_add_process_message_id.py](../../../fastapi_webapi/migrations/versions/20260818_01_add_process_message_id.py)):

```python
def upgrade() -> None:
    op.drop_constraint("fct_documents_process_id_fkey", "fct_documents", type_="foreignkey")
    op.create_foreign_key(
        "fct_documents_process_id_fkey",
        "fct_documents",       # source table
        "fct_processes",       # target table
        ["process_id"],        # local column(s)
        ["process_id"],        # remote column(s)
        ondelete="CASCADE",    # optional
    )


def downgrade() -> None:
    op.drop_constraint("fct_documents_process_id_fkey", "fct_documents", type_="foreignkey")
    op.create_foreign_key(
        "fct_documents_process_id_fkey",
        "fct_documents",
        "fct_processes",
        ["process_id"],
        ["process_id"],
        # no ondelete: restores original (RESTRICT) behavior
    )
```

Notes:
- Constraint names follow Postgres's default convention: `<table>_<column>_fkey`.
- If several FKs are being changed together, drop/recreate each one individually in `upgrade()`, and reverse them in the **opposite order** in `downgrade()`.
- When multiple tables reference the same parent (e.g. cascading deletes across a hierarchy), update each child FK separately — see the three FK blocks in [20260818_01_add_process_message_id.py](../../../fastapi_webapi/migrations/versions/20260818_01_add_process_message_id.py).

## General tips

- Never edit a migration that has already been applied anywhere outside local dev — create a new one instead.
- `uv run alembic history` is the source of truth for the current revision chain if `down_revision` is unclear.
