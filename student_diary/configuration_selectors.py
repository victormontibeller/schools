"""Consultas do catálogo configurável da Agenda."""

from django.db.models import Max, Prefetch, Q

from base.exceptions import ObjectNotFoundError
from base.selectors import PageResult


class DiaryConfigurationSelectorMixin:
    """Consultas de categorias e opções usadas na configuração e na folha."""

    def list_categories(self):
        """Lista itens disponíveis com suas opções disponíveis."""
        from student_diary.models import DiaryCategory, DiaryOption

        return (
            DiaryCategory.objects.filter(is_enabled=True)
            .prefetch_related(
                Prefetch(
                    "options",
                    queryset=DiaryOption.objects.filter(is_enabled=True).order_by(
                        "display_order", "label"
                    ),
                )
            )
            .order_by("section", "display_order", "name")
        )

    @staticmethod
    def category_applies_to_shift(category, shift: str) -> bool:
        """Indica se um item está disponível para novas respostas no turno."""
        from classes.contracts import Class

        field_by_shift = {
            Class.Shift.MORNING: "applies_morning",
            Class.Shift.AFTERNOON: "applies_afternoon",
            Class.Shift.FULL: "applies_full",
        }
        field = field_by_shift.get(shift)
        return bool(field and category.is_enabled and getattr(category, field))

    def list_sheet_categories(
        self,
        shift: str,
        *,
        persisted_category_ids=(),
        persisted_option_ids=(),
    ):
        """Lista itens aplicáveis ao turno e itens já persistidos na folha."""
        from classes.contracts import Class
        from student_diary.models import DiaryCategory, DiaryOption

        field_by_shift = {
            Class.Shift.MORNING: "applies_morning",
            Class.Shift.AFTERNOON: "applies_afternoon",
            Class.Shift.FULL: "applies_full",
        }
        field = field_by_shift.get(shift)
        available = Q(pk__in=()) if field is None else Q(is_enabled=True, **{field: True})
        return (
            DiaryCategory.objects.filter(available | Q(pk__in=persisted_category_ids))
            .prefetch_related(
                Prefetch(
                    "options",
                    queryset=DiaryOption.objects.filter(
                        Q(is_enabled=True) | Q(pk__in=persisted_option_ids)
                    ).order_by("display_order", "label"),
                )
            )
            .order_by("section", "display_order", "name")
        )

    def list_categories_page(
        self, search="", order_by="display_order", page=1, page_size=20
    ) -> PageResult:
        """Lista o catálogo configurável para a tela administrativa."""
        from student_diary.models import DiaryCategory

        queryset = DiaryCategory.objects.prefetch_related("options")
        if search:
            queryset = queryset.filter(name__icontains=search)
        field = order_by.removeprefix("-")
        if field == "section":
            queryset = queryset.order_by(order_by, "display_order", "name")
        elif field == "display_order":
            queryset = queryset.order_by("section", order_by, "name")
        else:
            queryset = queryset.order_by(order_by, "section", "display_order", "name")
        total = queryset.count()
        page = max(1, page)
        offset = (page - 1) * page_size
        return PageResult(
            items=list(queryset[offset : offset + page_size]),
            total=total,
            page=page,
            page_size=page_size,
        )

    @staticmethod
    def default_category_section() -> str:
        """Retorna a seção inicial de novos itens."""
        from student_diary.models import DiaryCategory

        return DiaryCategory.Section.ROUTINE

    def next_category_display_order(self, section=None) -> int:
        """Sugere a próxima ordem na seção sem impedir empates configurados."""
        from student_diary.models import DiaryCategory

        section = section or DiaryCategory.Section.ROUTINE
        maximum = DiaryCategory.objects.filter(section=section).aggregate(
            value=Max("display_order")
        )["value"]
        return (maximum or 0) + 1

    def get_category(self, category_id):
        """Retorna um item configurável ativo no catálogo."""
        from student_diary.models import DiaryCategory

        try:
            return DiaryCategory.objects.get(pk=category_id)
        except DiaryCategory.DoesNotExist:
            raise ObjectNotFoundError("DiaryCategory", str(category_id)) from None

    def get_category_with_options(self, category_id):
        """Retorna um item configurável com suas opções ordenadas."""
        from student_diary.models import DiaryCategory

        try:
            return DiaryCategory.objects.prefetch_related("options").get(pk=category_id)
        except DiaryCategory.DoesNotExist:
            raise ObjectNotFoundError("DiaryCategory", str(category_id)) from None
