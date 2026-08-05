"""GuardianSelector: consultas somente-leitura para responsáveis."""

from django.db.models import Q

from base.selectors import BaseSelector, PageResult


class GuardianSelector(BaseSelector):
    """Consultas somente-leitura para responsáveis."""

    @property
    def model_class(self):
        """Modelo alvo das consultas deste seletor."""
        from guardians.models import Guardian

        return Guardian

    def list_guardians(
        self, search="", filters=None, order_by="first_name", page=1, page_size=20
    ) -> PageResult:
        """Lista responsáveis com busca por nome e paginação."""
        qs = self.model_class.objects.select_related("user").prefetch_related("students__student")
        if filters:
            qs = qs.filter(**filters)
        if search:
            qs = qs.filter(
                Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(email__icontains=search)
                | Q(cpf__icontains=search)
            )
        qs = qs.order_by(order_by, "last_name")
        return self._paginate(qs, page=page, page_size=page_size)

    def get_guardian_students(self, guardian_id):
        """Retorna alunos vinculados ao responsavel, com dados do aluno."""
        guardian = self.get_by_id(guardian_id)
        return guardian.students.select_related("student").all()

    def custodial_links_for_user(self, user_id):
        """Retorna vínculos de guarda válidos para o responsável autenticado."""
        from guardians.models import StudentGuardian

        return StudentGuardian.objects.filter(
            guardian__user_id=user_id,
            guardian__user__is_active=True,
            guardian__user__deleted_at__isnull=True,
            guardian__is_active=True,
            guardian__deleted_at__isnull=True,
            student__is_active=True,
            student__deleted_at__isnull=True,
            has_custody=True,
            is_active=True,
            deleted_at__isnull=True,
        )

    def custodial_student_ids_for_user(self, user_id):
        """Retorna IDs de alunos ativos sob guarda válida do responsável."""
        return self.custodial_links_for_user(user_id).values_list("student_id", flat=True)

    def custodial_links_for_students(self, student_ids):
        """Retorna destinatários de guarda válidos para um conjunto de alunos."""
        from guardians.models import StudentGuardian

        return StudentGuardian.objects.filter(
            student_id__in=student_ids,
            guardian__user__is_active=True,
            guardian__user__deleted_at__isnull=True,
            guardian__is_active=True,
            guardian__deleted_at__isnull=True,
            student__is_active=True,
            student__deleted_at__isnull=True,
            has_custody=True,
            is_active=True,
            deleted_at__isnull=True,
        ).select_related("guardian__user", "student")

    def scope_students_for_user(self, queryset, user_id):
        """Restringe um queryset que possui PK de aluno ao escopo de guarda vigente."""
        return queryset.filter(pk__in=self.custodial_student_ids_for_user(user_id))

    def user_can_access_student(self, user_id, student_id) -> bool:
        """Confirma que o aluno permanece no escopo de guarda vigente."""
        return self.custodial_links_for_user(user_id).filter(student_id=student_id).exists()

    def search_reusable(self, query: str):
        """Busca responsáveis ativos para vinculação a um aluno."""
        if not query:
            return self.model_class.objects.none()
        return self.model_class.objects.filter(
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(email__icontains=query)
            | Q(cpf__icontains=query)
        ).order_by("first_name", "last_name")[:10]

    def search_by_cpf(self, cpf: str):
        """Busca responsavel por CPF."""
        from guardians.models import Guardian

        return Guardian.objects.filter(cpf__icontains=cpf).first()

    def search_by_phone(self, phone: str):
        """Busca responsavel por telefone/celular."""
        from django.db.models import Q

        from guardians.models import Guardian

        return Guardian.objects.filter(
            Q(phone__icontains=phone)
            | Q(phone_whatsapp__icontains=phone)
            | Q(phone_mobile__icontains=phone)
        ).first()

    def search_by_name(self, query: str, page: int = 1) -> PageResult:
        """Busca responsaveis por nome (via user)."""
        from django.db.models import Q

        from guardians.models import Guardian

        qs = Guardian.objects.select_related("user").filter(
            Q(user__first_name__icontains=query) | Q(user__last_name__icontains=query)
        )
        return self._paginate(qs, page=page)
