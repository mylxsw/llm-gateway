from pathlib import Path

from app.db.session import _drop_request_logs_provider_fk


class _FakeInspector:
    def __init__(self, foreign_keys):
        self._foreign_keys = foreign_keys

    def get_table_names(self):
        return ["request_logs"]

    def get_foreign_keys(self, table_name):
        assert table_name == "request_logs"
        return self._foreign_keys


class _FakeDialect:
    name = "postgresql"


class _FakeConn:
    def __init__(self):
        self.dialect = _FakeDialect()
        self.statements = []

    def execute(self, statement):
        self.statements.append(str(statement))


def test_drop_request_logs_provider_fk_removes_only_provider_constraint():
    conn = _FakeConn()
    inspector = _FakeInspector(
        [
            {
                "name": "request_logs_provider_id_fkey",
                "constrained_columns": ["provider_id"],
                "referred_table": "service_providers",
            },
            {
                "name": "request_logs_api_key_id_fkey",
                "constrained_columns": ["api_key_id"],
                "referred_table": "api_keys",
            },
        ]
    )

    _drop_request_logs_provider_fk(conn, inspector)

    assert conn.statements == [
        'ALTER TABLE request_logs DROP CONSTRAINT IF EXISTS "request_logs_provider_id_fkey"'
    ]


def test_postgresql_alias_integrity_migration_is_race_safe():
    sql = (
        Path(__file__).parents[3]
        / "migrations"
        / "enforce_model_alias_integrity_postgresql.sql"
    ).read_text()

    assert "pg_advisory_xact_lock" in sql
    assert sql.index("pg_advisory_xact_lock") < sql.index("CREATE INDEX")
    assert "FOR UPDATE" in sql
    assert "FOR KEY SHARE" not in sql
    assert "ERRCODE = '23514'" in sql
