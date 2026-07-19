"""Consultas somente-leitura da Agenda escolar."""

from __future__ import annotations

from datetime import date

from django.db.models import Count, Prefetch, Q

from base.exceptions import ObjectNotFoundError
from base.selectors import BaseSelector, PageResult


class StudentDiarySelector(BaseSelector):
    """Consulta configurações, folhas diárias e históricos."""

    @property
    def model_class(self):
        """Retorna o modelo principal do selector."""
        from student_diary.models import DailyDiary

        return DailyDiary

    def list_categories(self):
        """Lista aspectos disponíveis com suas opções disponíveis."""
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
            .order_by("display_order", "name")
        )

    @staticmethod
    def publication_enabled() -> bool:
        """Indica se o workflow está liberado para a escola atual."""
        from django.conf import settings

        from tenancy.selectors import SchoolSelector

        if settings.TESTING:
            return True
        school = SchoolSelector().get_current_school()
        return bool(
            school and school.settings.get("student_diary", {}).get("interactive_enabled", False)
        )

    def list_categories_page(
        self, search="", order_by="display_order", page=1, page_size=20
    ) -> PageResult:
        """Lista o catálogo configurável para a tela administrativa."""
        from student_diary.models import DiaryCategory

        queryset = DiaryCategory.objects.prefetch_related("options")
        if search:
            queryset = queryset.filter(name__icontains=search)
        queryset = queryset.order_by(order_by, "name")
        total = queryset.count()
        page = max(1, page)
        offset = (page - 1) * page_size
        return PageResult(
            items=list(queryset[offset : offset + page_size]),
            total=total,
            page=page,
            page_size=page_size,
        )

    def next_category_display_order(self) -> int:
        """Sugere a próxima ordem sem impedir empates configurados pela escola."""
        from django.db.models import Max

        from student_diary.models import DiaryCategory

        maximum = DiaryCategory.objects.aggregate(value=Max("display_order"))["value"]
        return (maximum or 0) + 1

    def get_category(self, category_id):
        """Retorna um aspecto configurável ativo no catálogo."""
        from student_diary.models import DiaryCategory

        try:
            return DiaryCategory.objects.get(pk=category_id)
        except DiaryCategory.DoesNotExist:
            raise ObjectNotFoundError("DiaryCategory", str(category_id)) from None

    def get_category_with_options(self, category_id):
        """Retorna um aspecto configurável com suas opções ordenadas."""
        from student_diary.models import DiaryCategory

        try:
            return DiaryCategory.objects.prefetch_related("options").get(pk=category_id)
        except DiaryCategory.DoesNotExist:
            raise ObjectNotFoundError("DiaryCategory", str(category_id)) from None

    def list_eligible_classes(self, user):
        """Lista turmas infantis acessíveis ao usuário."""
        from classes.contracts import Class
        from core.permissions import role_name

        qs = Class.objects.filter(
            education_stage=Class.EducationStage.EARLY_CHILDHOOD,
            shift__in=[Class.Shift.MORNING, Class.Shift.AFTERNOON, Class.Shift.FULL],
        )
        if role_name(user) == "TEACHER":
            qs = qs.filter(
                Q(class_teacher__user_id=user.pk) | Q(schedules__teacher__user_id=user.pk)
            ).distinct()
        return qs.order_by("name")

    def get_class(self, class_id):
        """Busca uma turma para a folha diária."""
        from base.exceptions import ObjectNotFoundError
        from classes.contracts import Class

        try:
            return Class.objects.get(pk=class_id)
        except Class.DoesNotExist:
            raise ObjectNotFoundError("Class", str(class_id)) from None

    def build_daily_sheet(self, class_id, diary_date: date, meal_types: tuple[str, ...]) -> dict:
        """Monta a folha com alunos, respostas e refeições pré-carregadas."""
        from classes.contracts import Enrollment
        from student_diary.models import DailyDiary, DiaryCategory, DiaryOption

        class_obj = self.get_class(class_id)
        from student_diary.models import DiarySheet

        workflow = DiarySheet.objects.filter(class_obj=class_obj, date=diary_date).first()
        enrollments = Enrollment.objects.filter(
            class_obj=class_obj, status=Enrollment.Status.ACTIVE
        ).select_related("student")
        diaries = {
            diary.student_id: diary
            for diary in DailyDiary.objects.filter(
                class_obj=class_obj, date=diary_date
            ).prefetch_related("answers__category", "answers__option", "meals")
        }
        persisted_answers = [answer for diary in diaries.values() for answer in diary.answers.all()]
        persisted_category_ids = {answer.category_id for answer in persisted_answers}
        persisted_option_ids = {answer.option_id for answer in persisted_answers}
        categories = list(
            DiaryCategory.objects.filter(Q(is_enabled=True) | Q(pk__in=persisted_category_ids))
            .prefetch_related(
                Prefetch(
                    "options",
                    queryset=DiaryOption.objects.filter(
                        Q(is_enabled=True) | Q(pk__in=persisted_option_ids)
                    ).order_by("display_order", "label"),
                )
            )
            .order_by("display_order", "name")
        )
        rows = []
        for enrollment in enrollments:
            diary = diaries.get(enrollment.student_id)
            answer_map = (
                {answer.category_id: answer.option_id for answer in diary.answers.all()}
                if diary
                else {}
            )
            meal_map = (
                {
                    meal.meal_type: meal.status
                    for meal in diary.meals.all()
                    if meal.meal_type in meal_types
                }
                if diary
                else {}
            )
            is_complete = (
                bool(diary)
                and all(
                    not category.is_enabled
                    or not category.is_required
                    or answer_map.get(category.pk)
                    for category in categories
                )
                and all(meal_map.get(meal_type) for meal_type in meal_types)
            )
            rows.append(
                {
                    "student": enrollment.student,
                    "notes": diary.notes if diary else "",
                    "diary": diary,
                    "is_complete": is_complete,
                    "initial_payload": {
                        "answers": {
                            str(category_id): str(option_id)
                            for category_id, option_id in answer_map.items()
                        },
                        "meals": {str(key): value for key, value in meal_map.items()},
                        "notes": diary.notes if diary else "",
                    },
                }
            )
        return {
            "class_obj": class_obj,
            "date": diary_date,
            "workflow": workflow,
            "categories": categories,
            "meal_types": meal_types,
            "rows": rows,
        }

    def get_sheet(self, sheet_id):
        """Busca uma folha com dados necessários ao workflow."""
        from student_diary.models import DiarySheet

        try:
            return DiarySheet.objects.select_related("class_obj").get(pk=sheet_id)
        except DiarySheet.DoesNotExist:
            raise ObjectNotFoundError("DiarySheet", str(sheet_id)) from None

    def list_active_reviewers(self):
        """Lista usuários ativos capazes de publicar ou devolver agendas."""
        from core.access.selectors import AccessConfigurationSelector
        from core.contracts import Role

        return (
            AccessConfigurationSelector.users_with_permission("student_diary", "edit")
            .filter(is_active=True)
            .filter(
                Q(is_superuser=True) | Q(role__name__in=[Role.Name.ADMIN, Role.Name.COORDINATOR])
            )
            .order_by("pk")
        )

    def list_pending_reviews(self, *, limit: int = 10):
        """Lista as pendências mais recentes para o dashboard de revisores."""
        from student_diary.models import DiarySheet

        return list(
            DiarySheet.objects.filter(status=DiarySheet.Status.PENDING_REVIEW)
            .select_related("class_obj", "submitted_by")
            .order_by("-submitted_at", "-date")[:limit]
        )

    def list_publication_delivery_summaries(self, sheet_id) -> list[dict]:
        """Resume entregas de e-mail por revisão sem expor destinatários."""
        from notifications.contracts import MessageLog
        from student_diary.models import DiaryPublication

        publications = DiaryPublication.objects.filter(sheet_id=sheet_id).annotate(
            email_sent=Count(
                "message_logs",
                filter=Q(
                    message_logs__channel=MessageLog.Channel.EMAIL,
                    message_logs__status__in=[
                        MessageLog.Status.SENT,
                        MessageLog.Status.DELIVERED,
                        MessageLog.Status.DELAYED,
                        MessageLog.Status.BOUNCED,
                        MessageLog.Status.COMPLAINED,
                    ],
                ),
            ),
            email_delivered=Count(
                "message_logs",
                filter=Q(
                    message_logs__channel=MessageLog.Channel.EMAIL,
                    message_logs__status=MessageLog.Status.DELIVERED,
                ),
            ),
            email_delayed=Count(
                "message_logs",
                filter=Q(
                    message_logs__channel=MessageLog.Channel.EMAIL,
                    message_logs__status=MessageLog.Status.DELAYED,
                ),
            ),
            email_failed=Count(
                "message_logs",
                filter=Q(
                    message_logs__channel=MessageLog.Channel.EMAIL,
                    message_logs__status__in=[
                        MessageLog.Status.BOUNCED,
                        MessageLog.Status.SUPPRESSED,
                        MessageLog.Status.COMPLAINED,
                        MessageLog.Status.FAILED,
                    ],
                ),
            ),
        )
        return [
            {
                "revision_number": item.revision_number,
                "published_at": item.published_at,
                "sent": item.email_sent,
                "delivered": item.email_delivered,
                "delayed": item.email_delayed,
                "failed": item.email_failed,
            }
            for item in publications.order_by("-revision_number")
        ]

    def build_publication_payloads(self, sheet) -> list[dict]:
        """Serializa o estado editável que será copiado para uma revisão imutável."""
        from student_diary.models import DailyDiary

        diaries = (
            DailyDiary.objects.filter(class_obj=sheet.class_obj, date=sheet.date)
            .select_related("student")
            .prefetch_related("answers__category", "answers__option", "meals")
        )
        return [
            {
                "student_id": diary.student_id,
                "notes": diary.notes,
                "routine_snapshot": [
                    {
                        "category": answer.category.name,
                        "category_code": answer.category.code,
                        "option": answer.option.label,
                        "option_code": answer.option.code,
                    }
                    for answer in diary.answers.all()
                ],
                "meals_snapshot": [
                    {
                        "meal_type": meal.meal_type,
                        "meal_label": meal.get_meal_type_display(),
                        "status": meal.status,
                        "status_label": meal.get_status_display(),
                    }
                    for meal in diary.meals.all()
                ],
            }
            for diary in diaries
        ]

    def list_custodial_guardians(self, student_ids):
        """Lista destinatários ativos com conta e guarda no momento da publicação."""
        from guardians.contracts import StudentGuardian

        return StudentGuardian.objects.filter(
            student_id__in=student_ids,
            has_custody=True,
            guardian__is_active=True,
            guardian__deleted_at__isnull=True,
            guardian__user__is_active=True,
        ).select_related("guardian__user", "student")

    def get_published_entry_for_guardian(self, entry_id, user_id):
        """Retorna uma publicação somente quando guarda e destinatário continuam válidos."""
        from student_diary.models import DiaryPublishedEntry

        try:
            return (
                DiaryPublishedEntry.objects.select_related(
                    "student", "publication__sheet__class_obj"
                )
                .prefetch_related("view_receipts")
                .get(
                    pk=entry_id,
                    view_receipts__guardian__user_id=user_id,
                    view_receipts__guardian__is_active=True,
                    student__guardians__guardian__user_id=user_id,
                    student__guardians__guardian__is_active=True,
                    student__guardians__has_custody=True,
                )
            )
        except DiaryPublishedEntry.DoesNotExist:
            raise ObjectNotFoundError("DiaryPublishedEntry", str(entry_id)) from None

    def list_published_student_history(self, student_id, *, guardian_user_id=None):
        """Lista somente revisões efetivamente publicadas para a família."""
        from student_diary.models import DiaryPublishedEntry

        queryset = DiaryPublishedEntry.objects.filter(student_id=student_id).select_related(
            "student", "publication__sheet__class_obj"
        )
        if guardian_user_id:
            queryset = queryset.filter(
                view_receipts__guardian__user_id=guardian_user_id,
                view_receipts__guardian__is_active=True,
                student__guardians__guardian__user_id=guardian_user_id,
                student__guardians__guardian__is_active=True,
                student__guardians__has_custody=True,
            )
        return queryset.distinct().order_by("-publication__published_at")

    def list_student_history(self, student_id):
        """Lista o histórico completo de agenda de um aluno."""
        from student_diary.models import DailyDiary

        return (
            DailyDiary.objects.filter(student_id=student_id)
            .select_related("student", "class_obj", "teacher__user", "updated_by")
            .prefetch_related("answers__category", "answers__option", "meals")
            .order_by("-date")
        )
