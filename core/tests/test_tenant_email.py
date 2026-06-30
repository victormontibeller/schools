"""Testes do resolvedor de e-mail por tenant."""


class TestTenantEmail:
    def test_get_tenant_from_email_fallback(self):
        from core.tenant_email import get_tenant_from_email

        result = get_tenant_from_email()
        assert "@" in result

    def test_get_tenant_email_display(self):
        from core.tenant_email import get_tenant_email_display

        result = get_tenant_email_display()
        assert "@" in result
