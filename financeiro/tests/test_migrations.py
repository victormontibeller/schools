"""Validação da instalação limpa do schema financeiro."""

import pytest
from django.db import connection, migrations
from django.db.migrations.executor import MigrationExecutor


@pytest.mark.django_db(transaction=True)
def test_initial_migration_installs_final_schema_from_zero():
    executor = MigrationExecutor(connection)
    leaf = executor.loader.graph.leaf_nodes("financeiro")

    assert leaf == [("financeiro", "0001_initial")]
    migration = executor.loader.get_migration(*leaf[0])
    assert not any(
        isinstance(operation, migrations.RunPython) for operation in migration.operations
    )

    executor.migrate([("financeiro", None)])
    executor = MigrationExecutor(connection)
    executor.migrate(leaf)

    tables = set(connection.introspection.table_names())
    assert "financeiro_studentfinancialcontract" in tables
    assert "financeiro_billingentry" in tables
    assert "financeiro_paymentrecord" in tables

    state = executor.loader.project_state(leaf).apps
    billing = state.get_model("financeiro", "BillingEntry")
    payment = state.get_model("financeiro", "PaymentRecord")
    assert {field.name for field in billing._meta.fields} >= {
        "contract",
        "principal_value",
        "status",
    }
    assert "billing" not in {field.name for field in payment._meta.fields}
