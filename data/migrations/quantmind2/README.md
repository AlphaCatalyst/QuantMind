# QuantMind 2.0 Ledger migrations

This directory is the only deployment authority for the `quantmind2`
Implementation Ledger database shape. Migrations are ordered by the explicit
`manifest.json`; directory traversal order is never used.

- Exact file bytes are SHA-256 checked before any database operation.
- Every migration runs in its own transaction under advisory transaction lock
  `4379672674272511630` (`quantmind2-ledger-migrations-v1`).
- `_schema_migrations` is migration infrastructure, not a Ledger domain table
  and not a replacement for Git Implementation Runs.
- `down` is only permitted for the latest applied version and requires
  `--allow-destructive`.
- All objects are schema-qualified. No migration changes `search_path`, grants
  broad privileges, or connects through an application Repository.

Commands (connection flags omitted here; see `--help`):

```text
python3 tools/quantmind2/ledger_migrations.py plan
python3 tools/quantmind2/ledger_migrations.py validate
python3 tools/quantmind2/ledger_migrations.py status ...
python3 tools/quantmind2/ledger_migrations.py up ...
python3 tools/quantmind2/ledger_migrations.py down --allow-destructive ...
```

The runner accepts native `psql` connection arguments or a validated
`--docker-container` name for the existing fresh-install path. Passwords are
accepted only through the normal `PGPASSWORD` environment variable and are
never printed by the runner.
