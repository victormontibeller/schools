"""ClassSelector: consultas somente-leitura para turmas e matrículas."""

from django.db.models import Case, IntegerField, Q, Value, When

from base.selectors import MAX_PAGE_SIZE, BaseSelector, PageResult


class ClassSelector(BaseSelector):
    """Selector para a entidade Class — turmas paginadas e consultas auxiliares."""

    @property
    def model_class(self):
        from classes.models import Class

        return Class

    def list_classes(
        self, filters=None, order_by="-academic_year", page=1, page_size=20
    ) -> PageResult:
        """Lista turmas ativas paginadas, com filtros opcionais."""
        if order_by in {"grade", "-grade"}:
            from classes.models import GRADE_PEDAGOGICAL_ORDER, Class

            ordered_grades = (
                GRADE_PEDAGOGICAL_ORDER
                if order_by == "grade"
                else tuple(reversed(GRADE_PEDAGOGICAL_ORDER))
            )
            page = max(1, page)
            page_size = min(max(1, page_size), MAX_PAGE_SIZE)
            queryset = Class.objects.filter(**(filters or {})).annotate(
                _grade_order=Case(
                    *[
                        When(grade=grade, then=Value(index))
                        for index, grade in enumerate(ordered_grades)
                    ],
                    default=Value(len(ordered_grades)),
                    output_field=IntegerField(),
                )
            )
            total = queryset.count()
            offset = (page - 1) * page_size
            return PageResult(
                items=list(queryset.order_by("_grade_order", "name")[offset : offset + page_size]),
                total=total,
                page=page,
                page_size=page_size,
            )
        return self.list(filters=filters, order_by=order_by, page=page, page_size=page_size)

    def get_class_by_id(self, class_id):
        """Retorna a turma com o ID informado."""
        return self.get_by_id(class_id)

    def get_class_students(self, class_id):
        """Retorna os alunos com matrícula ativa numa turma."""
        from classes.models import Enrollment

        return (
            Enrollment.objects.filter(class_obj_id=class_id)
            .select_related("student")
            .filter(status=Enrollment.Status.ACTIVE)
        )

    def get_available_classes(self, grade: str | None = None, shift: str | None = None):
        """Retorna turmas com vagas abertas, opcionalmente filtradas."""
        from classes.models import Class

        qs = Class.objects.all()
        if grade:
            qs = qs.filter(grade=grade)
        if shift:
            qs = qs.filter(shift=shift)
        # Mantém só turmas com vagas; calcula enrollment_count inline.
        result: list = []
        for cls in qs:
            if cls.has_open_seats:
                result.append(cls)
        return result

    def list_ordered(self):
        """Lista todas as turmas ordenadas por ano letivo (decrescente) e nome."""
        from classes.models import Class

        return Class.objects.all().order_by("-academic_year", "name")

    def get_enrollment_count(self, class_id) -> int:
        """Retorna o total de matrículas ativas na turma."""
        from classes.models import Enrollment

        return Enrollment.objects.filter(
            class_obj_id=class_id, status=Enrollment.Status.ACTIVE
        ).count()

    def search_enrollable_students(self, class_id, query: str, limit: int = 10):
        """Busca alunos por nome/matrícula, excluindo os já matriculados."""
        from students.models import Student

        if not query.strip():
            return Student.objects.none()
        return (
            Student.objects.filter(
                Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
                | Q(enrollment_number__icontains=query)
            )
            .exclude(enrollments__class_obj_id=class_id, enrollments__status="ACTIVE")
            .order_by("first_name", "last_name")[:limit]
        )
