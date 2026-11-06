"""Conflitos e dependências dos lotes de implantação."""

from base.exceptions import BusinessRuleViolationError, ValidationError
from base.selectors import BaseSelector
from students.models import AssistedImportBatch, Student


class AssistedImportSelector(BaseSelector):
    model_class = AssistedImportBatch

    @staticmethod
    def validate_existing(rows):
        from guardians.contracts import Guardian

        errors = []
        for kind, model in [("students", Student), ("guardians", Guardian)]:
            for row in rows[kind]:
                if row["cpf"] and model.all_objects.filter(cpf=row["cpf"]).exists():
                    errors.append(
                        f"{kind}, linha {row['_row']}: CPF já cadastrado. Reconcilie a carga."
                    )
                if row["email"] and model.all_objects.filter(email__iexact=row["email"]).exists():
                    errors.append(
                        f"{kind}, linha {row['_row']}: e-mail já cadastrado. Reconcilie a carga."
                    )
        if errors:
            raise ValidationError(errors={"files": errors})

    @staticmethod
    def require_unused(objects, manifest):
        """Recusa qualquer dependência fora do manifesto, inclusive já desativada."""
        owned = {(item["model"], item["object_id"]) for item in manifest}
        for obj in objects:
            if getattr(obj, "user_id", None):
                raise BusinessRuleViolationError(
                    "Lote já possui conta de acesso; aplique correção auditada."
                )
            for relation in obj._meta.related_objects:
                model = relation.related_model
                manager = getattr(model, "all_objects", model._default_manager)
                for pk in manager.filter(**{relation.field.name: obj.pk}).values_list(
                    "pk", flat=True
                ):
                    if (model._meta.label, str(pk)) not in owned:
                        raise BusinessRuleViolationError(
                            "Lote já possui registros dependentes; aplique correção auditada."
                        )

    @staticmethod
    def require_uncontested_identities(objects):
        """Recuperação nunca reativa uma identidade já substituída por outro cadastro."""
        from django.db.models import Q

        for obj in objects:
            query = Q(pk__isnull=True)
            if getattr(obj, "cpf", ""):
                query |= Q(cpf=obj.cpf)
            if getattr(obj, "email", ""):
                query |= Q(email__iexact=obj.email)
            if type(obj).objects.filter(query).exclude(pk=obj.pk).exists():
                raise BusinessRuleViolationError(
                    "Há um cadastro substituto com a mesma identidade. "
                    "Reconcilie os dados antes de recuperar o lote."
                )
