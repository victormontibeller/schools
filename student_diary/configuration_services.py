"""Regras de configuração do catálogo de itens da Agenda."""

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError


class RoutineConfigurationServiceMixin:
    """Comandos de catálogo expostos pelo ``StudentDiaryService``."""

    def create_routine_aspect(self, data: dict):
        """Cria um item personalizado inicialmente indisponível na Agenda."""
        from student_diary.models import DiaryCategory

        self.validate_required(data, ["name", "display_order"])
        name = str(data["name"]).strip()
        section = str(data.get("section", DiaryCategory.Section.ROUTINE))
        if section not in DiaryCategory.Section.values:
            raise ValidationError(errors={"section": ["Selecione uma seção válida."]})
        shifts = self._category_shift_values(data)
        if DiaryCategory.objects.filter(name=name).exists():
            raise ValidationError(errors={"name": ["Já existe um item com este nome."]})
        category = DiaryCategory.objects.create(
            name=name,
            section=section,
            display_order=int(data["display_order"]),
            is_required=bool(data.get("is_required", True)),
            is_enabled=False,
            **shifts,
            created_by=self.user,
            updated_by=self.user,
        )
        self._record_audit("INSERT", category)
        self._log("item_agenda_criado", category_id=str(category.pk))
        return category

    def update_routine_aspect(self, category_id, data: dict):
        """Atualiza os campos configuráveis de um item."""
        from student_diary.models import DiaryCategory

        category = self._get_category(category_id)
        self._assert_expected_version(category, data.get("version"))
        name = str(data.get("name", category.name)).strip()
        if DiaryCategory.objects.filter(name=name).exclude(pk=category.pk).exists():
            raise ValidationError(errors={"name": ["Já existe um item com este nome."]})
        section = str(data.get("section", category.section))
        if section not in DiaryCategory.Section.values:
            raise ValidationError(errors={"section": ["Selecione uma seção válida."]})
        shifts = self._category_shift_values(data, category=category)
        old = self._snapshot(
            category,
            [
                "name",
                "section",
                "display_order",
                "is_required",
                "applies_morning",
                "applies_afternoon",
                "applies_full",
            ],
        )
        category.name = name
        category.section = section
        category.display_order = int(data.get("display_order", category.display_order))
        category.is_required = bool(data.get("is_required", False))
        for field, value in shifts.items():
            setattr(category, field, value)
        category.updated_by = self.user
        category.save(
            update_fields=[
                "name",
                "section",
                "display_order",
                "is_required",
                "applies_morning",
                "applies_afternoon",
                "applies_full",
                "updated_by",
                "updated_at",
            ]
        )
        self._record_audit("UPDATE", category, old_values=old)
        self._log("item_agenda_atualizado", category_id=str(category.pk))
        return category

    def set_routine_aspect_enabled(
        self, category_id, enabled: bool, expected_version: int | None = None
    ):
        """Ativa ou desativa um item configurável."""
        from student_diary.models import DiaryOption

        category = self._get_category(category_id)
        self._assert_expected_version(category, expected_version)
        if enabled and not any(
            (category.applies_morning, category.applies_afternoon, category.applies_full)
        ):
            raise BusinessRuleViolationError("Selecione ao menos um turno antes de ativar o item.")
        if enabled and not DiaryOption.objects.filter(category=category, is_enabled=True).exists():
            raise BusinessRuleViolationError(
                "Cadastre ao menos uma opção disponível antes de ativar o item."
            )
        old = self._snapshot(category, ["is_enabled"])
        category.is_enabled = bool(enabled)
        category.updated_by = self.user
        category.save(update_fields=["is_enabled", "updated_by", "updated_at"])
        self._record_audit("UPDATE", category, old_values=old)
        self._log(
            "item_agenda_alterado",
            category_id=str(category.pk),
            enabled=category.is_enabled,
        )
        return category

    def create_routine_option(self, category_id, data: dict):
        """Cria uma opção disponível para um item."""
        from student_diary.models import DiaryOption

        category = self._get_category(category_id)
        self.validate_required(data, ["label", "display_order"])
        label = str(data["label"]).strip()
        if DiaryOption.objects.filter(category=category, label=label).exists():
            raise ValidationError(errors={"label": ["Esta opção já existe no item."]})
        option = DiaryOption.objects.create(
            category=category,
            label=label,
            display_order=int(data["display_order"]),
            is_enabled=True,
            created_by=self.user,
            updated_by=self.user,
        )
        self._record_audit("INSERT", option)
        self._log(
            "opcao_rotina_criada",
            category_id=str(category.pk),
            option_id=str(option.pk),
        )
        return option

    @staticmethod
    def _category_shift_values(data: dict, *, category=None) -> dict[str, bool]:
        """Normaliza e valida os turnos selecionados para um item da Agenda."""
        defaults = {
            "applies_morning": getattr(category, "applies_morning", True),
            "applies_afternoon": getattr(category, "applies_afternoon", True),
            "applies_full": getattr(category, "applies_full", True),
        }
        values = {field: bool(data.get(field, default)) for field, default in defaults.items()}
        if not any(values.values()):
            raise ValidationError(errors={"shifts": ["Selecione ao menos um turno."]})
        return values

    def update_routine_option(self, category_id, option_id, data: dict):
        """Atualiza o rótulo e a ordem de uma opção."""
        from student_diary.models import DiaryOption

        option = self._get_option(category_id, option_id)
        self._assert_expected_version(option, data.get("version"))
        label = str(data.get("label", option.label)).strip()
        if (
            DiaryOption.objects.filter(category_id=category_id, label=label)
            .exclude(pk=option.pk)
            .exists()
        ):
            raise ValidationError(errors={"label": ["Esta opção já existe no item."]})
        old = self._snapshot(option, ["label", "display_order"])
        option.label = label
        option.display_order = int(data.get("display_order", option.display_order))
        option.updated_by = self.user
        option.save(update_fields=["label", "display_order", "updated_by", "updated_at"])
        self._record_audit("UPDATE", option, old_values=old)
        self._log("opcao_rotina_atualizada", option_id=str(option.pk))
        return option

    def set_routine_option_enabled(
        self,
        category_id,
        option_id,
        enabled: bool,
        expected_version: int | None = None,
    ):
        """Altera reversivelmente a disponibilidade de uma opção."""
        from student_diary.models import DiaryOption

        option = self._get_option(category_id, option_id)
        self._assert_expected_version(option, expected_version)
        if (
            not enabled
            and option.category.is_enabled
            and not DiaryOption.objects.filter(category=option.category, is_enabled=True)
            .exclude(pk=option.pk)
            .exists()
        ):
            raise BusinessRuleViolationError(
                "Um item ativo precisa manter ao menos uma opção disponível."
            )
        old = self._snapshot(option, ["is_enabled"])
        option.is_enabled = bool(enabled)
        option.updated_by = self.user
        option.save(update_fields=["is_enabled", "updated_by", "updated_at"])
        self._record_audit("UPDATE", option, old_values=old)
        self._log("opcao_rotina_alterada", option_id=str(option.pk), enabled=option.is_enabled)
        return option

    @staticmethod
    def _assert_expected_version(instance, expected_version) -> None:
        """Recusa uma edição iniciada sobre uma versão já substituída."""
        if expected_version is not None and int(expected_version) != instance.version:
            raise BusinessRuleViolationError(
                "Este registro foi alterado por outra pessoa. "
                "Recarregue os dados e tente novamente."
            )

    @staticmethod
    def _get_category(category_id):
        from student_diary.models import DiaryCategory

        try:
            return DiaryCategory.objects.get(pk=category_id)
        except DiaryCategory.DoesNotExist:
            raise ObjectNotFoundError("DiaryCategory", str(category_id)) from None

    @staticmethod
    def _get_option(category_id, option_id):
        from student_diary.models import DiaryOption

        try:
            return DiaryOption.objects.select_related("category").get(
                pk=option_id, category_id=category_id
            )
        except DiaryOption.DoesNotExist:
            raise ObjectNotFoundError("DiaryOption", str(option_id)) from None
