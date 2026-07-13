"""Consultas somente-leitura da Agenda escolar."""

from __future__ import annotations

from datetime import date

from django.db.models import Q

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
        """Lista aspectos predefinidos habilitados com opções ordenadas."""
        from student_diary.models import DiaryCategory

        return (
            DiaryCategory.objects.filter(code__isnull=False, is_enabled=True)
            .prefetch_related("options")
            .order_by("display_order", "name")
        )

    def list_categories_page(
        self, search="", order_by="display_order", page=1, page_size=20
    ) -> PageResult:
        """Lista aspectos fixos para a tela administrativa com paginação."""
        from student_diary.models import DiaryCategory

        queryset = DiaryCategory.objects.filter(code__isnull=False).prefetch_related("options")
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

    def get_category(self, category_id):
        """Retorna um aspecto predefinido ativo."""
        from student_diary.models import DiaryCategory

        try:
            return DiaryCategory.objects.get(pk=category_id, code__isnull=False)
        except DiaryCategory.DoesNotExist:
            raise ObjectNotFoundError("DiaryCategory", str(category_id)) from None

    def get_category_with_options(self, category_id):
        """Retorna um aspecto predefinido com suas opções ordenadas."""
        from student_diary.models import DiaryCategory

        try:
            return DiaryCategory.objects.prefetch_related("options").get(
                pk=category_id, code__isnull=False
            )
        except DiaryCategory.DoesNotExist:
            raise ObjectNotFoundError("DiaryCategory", str(category_id)) from None

    def list_eligible_classes(self, user):
        """Lista turmas infantis acessíveis ao usuário."""
        from classes.models import Class
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
        from classes.models import Class

        try:
            return Class.objects.get(pk=class_id)
        except Class.DoesNotExist:
            raise ObjectNotFoundError("Class", str(class_id)) from None

    def build_daily_sheet(self, class_id, diary_date: date, meal_types: tuple[str, ...]) -> dict:
        """Monta a folha com alunos, respostas e refeições pré-carregadas."""
        from classes.models import Enrollment
        from student_diary.models import DailyDiary, DiaryMeal

        class_obj = self.get_class(class_id)
        categories = list(self.list_categories())
        enrollments = Enrollment.objects.filter(
            class_obj=class_obj, status=Enrollment.Status.ACTIVE
        ).select_related("student")
        diaries = {
            diary.student_id: diary
            for diary in DailyDiary.objects.filter(
                class_obj=class_obj, date=diary_date
            ).prefetch_related("answers__option", "meals")
        }
        meal_labels = dict(DiaryMeal.MealType.choices)
        active_category_ids = {category.pk for category in categories}
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
                and all(answer_map.get(category.pk) for category in categories)
                and all(meal_map.get(meal_type) for meal_type in meal_types)
            )
            rows.append(
                {
                    "student": enrollment.student,
                    "notes": diary.notes if diary else "",
                    "diary": diary,
                    "is_complete": is_complete,
                    "meal_summary": (
                        f"{len(meal_map)}/{len(meal_types)} refeições" if meal_map else "—"
                    ),
                    "routine_summary": (
                        ", ".join(
                            answer.option.label
                            for answer in diary.answers.all()
                            if answer.category_id in active_category_ids
                        )
                        if diary
                        else "—"
                    ),
                    "initial_payload": {
                        "answers": {
                            str(category_id): str(option_id)
                            for category_id, option_id in answer_map.items()
                        },
                        "meals": {str(key): value for key, value in meal_map.items()},
                        "notes": diary.notes if diary else "",
                    },
                    "category_cells": [
                        {
                            "category": category,
                            "options": category.options.all(),
                            "selected": answer_map.get(category.pk),
                        }
                        for category in categories
                    ],
                    "meal_cells": [
                        {
                            "meal_type": meal_type,
                            "label": meal_labels[meal_type],
                            "selected": meal_map.get(meal_type),
                        }
                        for meal_type in meal_types
                    ],
                }
            )
        return {
            "class_obj": class_obj,
            "date": diary_date,
            "categories": categories,
            "meal_types": meal_types,
            "rows": rows,
        }

    def list_student_history(self, student_id):
        """Lista o histórico completo de agenda de um aluno."""
        from student_diary.models import DailyDiary

        return (
            DailyDiary.objects.filter(student_id=student_id)
            .select_related("student", "class_obj", "teacher__user", "updated_by")
            .prefetch_related("answers__category", "answers__option", "meals")
            .order_by("-date")
        )
