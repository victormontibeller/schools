"""EnrollmentApplicationSelector: consultas somente-leitura para matriculas."""

from django.db.models import Q

from base.selectors import BaseSelector, PageResult


class EnrollmentApplicationSelector(BaseSelector):
    """Consultas somente-leitura para solicitacoes de matricula."""

    @property
    def model_class(self):
        from enrollments.models import EnrollmentApplication

        return EnrollmentApplication

    def list_by_status(
        self,
        status,
        search: str = "",
        page: int = 1,
        page_size: int = 20,
    ) -> PageResult:
        """Lista solicitacoes filtradas por status, com busca textual."""
        from enrollments.models import EnrollmentApplication

        qs = EnrollmentApplication.objects.filter(status=status).select_related(
            "student", "class_obj"
        )
        if search:
            qs = qs.filter(
                Q(student__first_name__icontains=search)
                | Q(student__last_name__icontains=search)
                | Q(application_number__icontains=search)
                | Q(student__enrollment_number__icontains=search)
            )
        return self._paginate(qs, page=page, page_size=page_size)

    def list_pending_review(
        self,
        search: str = "",
        page: int = 1,
        page_size: int = 20,
    ) -> PageResult:
        """Fila de analise ordenada por prioridade: pre-matricula e em analise."""
        from enrollments.models import EnrollmentApplication

        qs = (
            EnrollmentApplication.objects.filter(
                status__in=[
                    EnrollmentApplication.Status.PRE_ENROLLMENT,
                    EnrollmentApplication.Status.UNDER_REVIEW,
                ]
            )
            .select_related("student", "class_obj")
            .order_by("-priority", "-created_at")
        )
        if search:
            qs = qs.filter(
                Q(student__first_name__icontains=search)
                | Q(student__last_name__icontains=search)
                | Q(application_number__icontains=search)
                | Q(student__enrollment_number__icontains=search)
            )
        return self._paginate(qs, page=page, page_size=page_size)

    def search_by_name(self, query: str, page: int = 1) -> PageResult:
        """Busca rapida por nome, matricula ou protocolo."""
        from enrollments.models import EnrollmentApplication

        qs = EnrollmentApplication.objects.filter(
            Q(student__first_name__icontains=query)
            | Q(student__last_name__icontains=query)
            | Q(application_number__icontains=query)
            | Q(student__enrollment_number__icontains=query)
        ).select_related("student", "class_obj")
        return self._paginate(qs, page=page)

    def get_application_by_id(self, application_id):
        """Retorna a solicitacao pelo id com relacionamentos ou lanca ObjectNotFoundError."""
        from base.exceptions import ObjectNotFoundError

        try:
            return self.model_class.objects.select_related(
                "student", "class_obj", "enrollment", "reviewed_by"
            ).get(pk=application_id)
        except self.model_class.DoesNotExist:
            raise ObjectNotFoundError("EnrollmentApplication", str(application_id)) from None

    def get_documents(self, application_id):
        """Retorna documentos vinculados a uma solicitacao."""
        from enrollments.models import StudentDocument

        return StudentDocument.objects.filter(application_id=application_id).order_by(
            "document_type"
        )

    def get_student_pending_documents(self, student_id):
        """Retorna documentos pendentes de um aluno."""
        from enrollments.models import StudentDocument

        return StudentDocument.objects.filter(
            student_id=student_id, status=StudentDocument.Status.PENDING
        ).order_by("document_type")

    def _paginate(self, qs, page: int = 1, page_size: int = 20) -> PageResult:
        from base.selectors import MAX_PAGE_SIZE

        page_size = min(max(1, page_size), MAX_PAGE_SIZE)
        page = max(1, page)
        total = qs.count()
        offset = (page - 1) * page_size
        return PageResult(
            items=list(qs[offset : offset + page_size]),
            total=total,
            page=page,
            page_size=page_size,
        )
