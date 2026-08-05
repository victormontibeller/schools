"""Regressões da reconciliação institucional do seed DEMO."""

import pytest


@pytest.mark.django_db
def test_populate_core_reloads_stale_school_before_reconciliation(monkeypatch):
    """O seed usa as configurações e a versão mais recentes da escola."""
    from core.demo_seed import DemoSeedService
    from core.demo_seed.core_data import CoreDemoSeedMixin
    from tenancy.models import School

    school = School.objects.create(schema_name="demo", name="Escola Demonstração")
    stale_school = School.objects.get(pk=school.pk)
    school.settings = {"existing_setting": True}
    school.save(update_fields=["settings"])

    class StopSeedError(Exception):
        """Interrompe o seed após validar a reconciliação institucional."""

    def stop_after_school_ensure(self, model, lookup, values):
        assert model is School
        assert lookup == {"pk": school.pk}
        assert values["settings"]["existing_setting"] is True
        raise StopSeedError

    monkeypatch.setattr(CoreDemoSeedMixin, "_ensure", stop_after_school_ensure)

    with pytest.raises(StopSeedError):
        DemoSeedService().populate_core(stale_school)
