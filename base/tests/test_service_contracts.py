"""Testes do checker de comandos públicos em services."""

from pathlib import Path

from scripts.check_service_contracts import scan


def _write_service(root: Path, source: str) -> None:
    app = root / "sample"
    app.mkdir()
    (app / "services.py").write_text(source, encoding="utf-8")


def test_scan_accepts_prefix_and_explicit_decorators(tmp_path):
    _write_service(
        tmp_path,
        """
class ExampleService(BaseService):
    def create_item(self):
        self._record_audit("INSERT", object())

    @service_command
    def link_item(self):
        self._record_audit("UPDATE", object())

    @system_command
    def process_event(self):
        self._record_audit("UPDATE", object())
""",
    )

    assert scan(tmp_path) == set()


def test_scan_reports_public_mutation_without_command_contract(tmp_path):
    _write_service(
        tmp_path,
        """
class ExampleService(BaseService):
    @transaction.atomic
    def link_item(self):
        instance.save()
        self._record_audit("UPDATE", instance)
""",
    )

    assert scan(tmp_path) == {"sample/services.py:4:link_item:undeclared-command"}


def test_scan_ignores_queries_and_private_helpers(tmp_path):
    _write_service(
        tmp_path,
        """
class ExampleService(BaseService):
    def get_item(self):
        return object()

    def _persist(self):
        instance.save()
""",
    )

    assert scan(tmp_path) == set()


def test_scan_checks_indirect_services_and_their_mixins(tmp_path):
    _write_service(
        tmp_path,
        """
class MutationMixin:
    def publish_item(self):
        records.update(status="published")

class CoreService(BaseService):
    pass

class PublicService(MutationMixin, CoreService):
    pass
""",
    )

    assert scan(tmp_path) == {"sample/services.py:3:publish_item:undeclared-command"}
