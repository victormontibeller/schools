"""Consultas otimizadas e projeções tipadas do workflow de matrículas."""

from dataclasses import dataclass

from django.db.models import Count, Q

from base.exceptions import ObjectNotFoundError
from base.selectors import BaseSelector, PageResult


@dataclass(frozen=True, slots=True)
class ClassCapacity:
    """Capacidade comprometida e reservada da turma de destino."""

    committed: int
    reserved: int
    maximum: int
    available: int


@dataclass(frozen=True, slots=True)
class ApplicationDetail:
    """Projeção materializada consumida pela ficha e por seus fragmentos HTMX."""

    application: object
    documents: tuple[object, ...]
    transitions: tuple[object, ...]
    capacity: ClassCapacity | None
    has_pending_required_documents: bool


class EnrollmentApplicationSelector(BaseSelector):
    """Leituras da fila, ficha, documentos e rematrícula."""

    @property
    def model_class(self):
        from enrollments.models import EnrollmentApplication

        return EnrollmentApplication

    def list_applications(
        self,
        *,
        statuses: list[str],
        search: str = "",
        academic_year: int | None = None,
        class_id=None,
        application_type: str = "",
        document_status: str = "",
        page: int = 1,
        page_size: int = 20,
    ) -> PageResult:
        """Lista solicitações com filtros persistíveis na query string."""
        queryset = self.model_class.objects.filter(status__in=statuses).select_related(
            "student", "target_class", "source_enrollment__class_obj", "result_enrollment"
        )
        if search:
            queryset = queryset.filter(
                Q(student__first_name__icontains=search)
                | Q(student__last_name__icontains=search)
                | Q(student__enrollment_number__icontains=search)
                | Q(application_number__icontains=search)
                | Q(student__guardians__guardian__first_name__icontains=search)
                | Q(student__guardians__guardian__last_name__icontains=search)
            ).distinct()
        if academic_year:
            queryset = queryset.filter(academic_year=academic_year)
        if class_id:
            queryset = queryset.filter(target_class_id=class_id)
        if application_type:
            queryset = queryset.filter(application_type=application_type)
        if document_status:
            queryset = queryset.filter(documents__status=document_status).distinct()
        if statuses == [self.model_class.Status.WAITLISTED]:
            queryset = queryset.order_by("-priority", "waitlisted_at", "created_at")
        else:
            queryset = queryset.order_by("-created_at")
        return self._paginate(queryset, page=page, page_size=page_size)

    def status_counts(self) -> dict[str, int]:
        """Retorna contadores de todas as etapas em uma única consulta."""
        return {
            row["status"]: row["total"]
            for row in self.model_class.objects.values("status").annotate(total=Count("id"))
        }

    def get_application_by_id(self, application_id):
        """Carrega a ficha completa sem N+1."""
        try:
            return (
                self.model_class.objects.select_related(
                    "student",
                    "target_class",
                    "source_enrollment__class_obj",
                    "result_enrollment__class_obj",
                    "reviewed_by",
                )
                .prefetch_related("documents", "transitions__actor")
                .get(pk=application_id)
            )
        except self.model_class.DoesNotExist:
            raise ObjectNotFoundError("EnrollmentApplication", str(application_id)) from None

    def get_application_detail(self, application_id) -> ApplicationDetail:
        """Materializa ficha, capacidade, documentos e transições fora da camada HTTP."""
        from classes.contracts import Enrollment
        from enrollments.models import EnrollmentApplication, StudentDocument

        application = self.get_application_by_id(application_id)
        documents = tuple(application.documents.all())
        transitions = tuple(application.transitions.all())
        capacity = None
        if application.target_class_id:
            committed = Enrollment.objects.filter(
                class_obj_id=application.target_class_id,
                status=Enrollment.Status.ACTIVE,
            ).count()
            reserved = EnrollmentApplication.objects.filter(
                target_class_id=application.target_class_id,
                status=EnrollmentApplication.Status.APPROVED,
            ).count()
            maximum = application.target_class.max_students
            capacity = ClassCapacity(
                committed=committed,
                reserved=reserved,
                maximum=maximum,
                available=max(maximum - committed - reserved, 0),
            )
        pending_statuses = {
            StudentDocument.Status.VERIFIED,
            StudentDocument.Status.WAIVED,
        }
        return ApplicationDetail(
            application=application,
            documents=documents,
            transitions=transitions,
            capacity=capacity,
            has_pending_required_documents=any(
                document.is_required and document.status not in pending_statuses
                for document in documents
            ),
        )

    def get_documents(self, application_id):
        """Retorna o snapshot documental da solicitação."""
        from enrollments.models import StudentDocument

        return StudentDocument.objects.filter(application_id=application_id).order_by(
            "requirement_label"
        )

    def get_document_by_id(self, document_id):
        """Carrega item documental para ação ou download privado."""
        from enrollments.models import StudentDocument

        try:
            return StudentDocument.objects.select_related("application__student").get(
                pk=document_id
            )
        except StudentDocument.DoesNotExist:
            raise ObjectNotFoundError("StudentDocument", str(document_id)) from None

    def list_document_requirements(
        self,
        *,
        search: str = "",
        page: int = 1,
        page_size: int = 20,
    ) -> PageResult:
        """Lista requisitos futuros configuráveis pelo Administrador."""
        from enrollments.models import DocumentRequirement

        queryset = DocumentRequirement.objects.all()
        if search:
            queryset = queryset.filter(Q(label__icontains=search) | Q(code__icontains=search))
        return self._paginate(
            queryset.order_by("application_type", "display_order", "label"),
            page=page,
            page_size=page_size,
        )

    def get_document_requirement_by_id(self, requirement_id):
        """Obtém requisito ativo para edição administrativa."""
        from enrollments.models import DocumentRequirement

        try:
            return DocumentRequirement.objects.get(pk=requirement_id)
        except DocumentRequirement.DoesNotExist:
            raise ObjectNotFoundError("DocumentRequirement", str(requirement_id)) from None

    def reminder_recipient_ids(self, application_id) -> list:
        """Resolve responsável principal com guarda e aluno, ambos consentidos."""
        application = self.get_application_by_id(application_id)
        from guardians.contracts import StudentGuardian

        recipient_ids = list(
            StudentGuardian.objects.filter(
                student_id=application.student_id,
                is_active=True,
                deleted_at__isnull=True,
                is_primary=True,
                has_custody=True,
                guardian__is_active=True,
                guardian__deleted_at__isnull=True,
                guardian__user__isnull=False,
                guardian__user__is_active=True,
                guardian__accepts_email_notifications=True,
            ).values_list("guardian__user_id", flat=True)
        )
        student = application.student
        if (
            student.is_active
            and not student.is_deleted
            and student.user_id
            and student.accepts_email_notifications
            and student.user.is_active
        ):
            recipient_ids.append(student.user_id)
        return list(dict.fromkeys(recipient_ids))

    def is_reminder_recipient_eligible(self, application_id, recipient_id) -> bool:
        """Revalida guarda, atividade e consentimento imediatamente antes da entrega."""
        return recipient_id in self.reminder_recipient_ids(application_id)

    def reenrollment_candidates(self, source_class_id):
        """Lista matrículas ativas e destinos pedagógicos do ano seguinte."""
        from classes.contracts import GRADE_PEDAGOGICAL_ORDER, Class, Enrollment

        try:
            source_class = Class.objects.get(pk=source_class_id)
        except Class.DoesNotExist:
            raise ObjectNotFoundError("Class", str(source_class_id)) from None
        next_grade = None
        try:
            next_grade = GRADE_PEDAGOGICAL_ORDER[
                GRADE_PEDAGOGICAL_ORDER.index(source_class.grade) + 1
            ]
        except (ValueError, IndexError):
            pass
        from enrollments.models import EnrollmentApplication

        destinations = (
            Class.objects.filter(
                academic_year=source_class.academic_year + 1,
            )
            .annotate(
                active_enrollment_count=Count(
                    "enrollments",
                    filter=Q(enrollments__status=Enrollment.Status.ACTIVE),
                    distinct=True,
                ),
                approved_reservation_count=Count(
                    "enrollment_applications",
                    filter=Q(enrollment_applications__status=EnrollmentApplication.Status.APPROVED),
                    distinct=True,
                ),
            )
            .order_by("shift", "grade", "name")
        )
        destinations = list(destinations)
        suggested = []
        for destination in destinations:
            destination.projected_enrollment_count = (
                destination.active_enrollment_count + destination.approved_reservation_count
            )
            destination.is_pedagogical_suggestion = bool(
                next_grade
                and destination.grade == next_grade
                and destination.shift == source_class.shift
            )
            destination.is_repetition = destination.grade == source_class.grade
            destination.is_exception = not destination.is_pedagogical_suggestion
            if destination.is_pedagogical_suggestion:
                suggested.append(destination)
        if len(suggested) == 1:
            suggested[0].is_preselected = True
        candidates = Enrollment.objects.filter(
            class_obj=source_class, status=Enrollment.Status.ACTIVE
        ).select_related("student", "class_obj")
        return source_class, candidates, destinations, next_grade

    def get_reminder_by_id(self, reminder_id):
        """Carrega lembrete e destinatário para task idempotente."""
        from enrollments.models import EnrollmentReminder

        try:
            return EnrollmentReminder.objects.select_related("recipient", "application").get(
                pk=reminder_id
            )
        except EnrollmentReminder.DoesNotExist:
            raise ObjectNotFoundError("EnrollmentReminder", str(reminder_id)) from None

    def active_enrollments(self, *, student_id=None):
        """Lista vínculos ativos selecionáveis como origem."""
        from classes.contracts import Enrollment

        queryset = Enrollment.objects.filter(status=Enrollment.Status.ACTIVE).select_related(
            "student", "class_obj"
        )
        if student_id:
            queryset = queryset.filter(student_id=student_id)
        return queryset.order_by("student__first_name", "-academic_year")
