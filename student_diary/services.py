"""Regras de negócio da agenda diária da Educação Infantil."""

from __future__ import annotations

from datetime import date

from django.db import transaction

from base.exceptions import (
    BusinessRuleViolationError,
    ObjectNotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from base.services import BaseService
from student_diary.configuration_services import RoutineConfigurationServiceMixin


class StudentDiaryService(RoutineConfigurationServiceMixin, BaseService):
    """Gerencia configurações e registros diários infantis."""

    @staticmethod
    def meals_for_shift(shift: str) -> tuple[str, ...]:
        """Retorna as refeições obrigatórias para o turno informado."""
        from classes.contracts import Class
        from student_diary.models import DiaryMeal

        mapping = {
            Class.Shift.MORNING: (
                DiaryMeal.MealType.MORNING_SNACK,
                DiaryMeal.MealType.LUNCH,
            ),
            Class.Shift.AFTERNOON: (
                DiaryMeal.MealType.LUNCH,
                DiaryMeal.MealType.AFTERNOON_SNACK,
            ),
            Class.Shift.FULL: (
                DiaryMeal.MealType.MORNING_SNACK,
                DiaryMeal.MealType.LUNCH,
                DiaryMeal.MealType.AFTERNOON_SNACK,
            ),
        }
        if shift not in mapping:
            raise BusinessRuleViolationError("A Agenda não está disponível para este turno.")
        return mapping[shift]

    @transaction.atomic
    def save_daily_diaries(self, class_id, diary_date: date, entries_data: dict):
        """Salva atomicamente a agenda de todos os alunos ativos da turma."""
        from django.db.models import Q

        from classes.contracts import Class, Enrollment
        from student_diary.models import (
            DiaryAnswer,
            DiaryCategory,
            DiaryOption,
            DiarySheet,
        )

        try:
            class_obj = Class.objects.get(pk=class_id)
        except Class.DoesNotExist:
            raise ObjectNotFoundError("Class", str(class_id)) from None
        self._assert_eligible_class(class_obj)
        teacher = self._get_authorized_teacher(class_obj)
        sheet = (
            DiarySheet.objects.select_for_update()
            .filter(class_obj=class_obj, date=diary_date)
            .first()
        )
        if sheet and sheet.status in {
            DiarySheet.Status.PENDING_REVIEW,
            DiarySheet.Status.PUBLISHED,
        }:
            raise BusinessRuleViolationError(
                "A agenda precisa ser devolvida ou reaberta antes de ser editada."
            )
        if sheet is None:
            sheet = DiarySheet.objects.create(
                class_obj=class_obj,
                date=diary_date,
                created_by=self.user,
                updated_by=self.user,
            )
            self._record_audit("INSERT", sheet)

        active_ids = {
            str(student_id)
            for student_id in Enrollment.objects.filter(
                class_obj=class_obj, status=Enrollment.Status.ACTIVE
            ).values_list("student_id", flat=True)
        }
        if set(entries_data) != active_ids:
            raise ValidationError(
                errors={"students": ["A agenda deve contemplar todos os alunos ativos da turma."]}
            )

        existing_answers = {
            (str(student_id), str(category_id)): str(option_id)
            for student_id, category_id, option_id in DiaryAnswer.objects.filter(
                diary__class_obj=class_obj,
                diary__date=diary_date,
            ).values_list("diary__student_id", "category_id", "option_id")
        }
        existing_category_ids = {category_id for _, category_id in existing_answers}
        existing_option_ids = set(existing_answers.values())
        categories = list(
            DiaryCategory.objects.filter(Q(is_enabled=True) | Q(pk__in=existing_category_ids))
        )
        category_map = {str(category.pk): category for category in categories}
        option_pairs = {
            (str(option.category_id), str(option.pk)): option
            for option in DiaryOption.objects.filter(category__in=categories).filter(
                Q(is_enabled=True) | Q(pk__in=existing_option_ids)
            )
        }
        meal_types = self.meals_for_shift(class_obj.shift)
        for student_id, payload in entries_data.items():
            current_answers = {
                category_id: option_id
                for (answer_student_id, category_id), option_id in existing_answers.items()
                if answer_student_id == student_id
            }
            self._validate_daily_payload(
                payload, category_map, option_pairs, meal_types, current_answers
            )
            self._save_student_diary(
                class_obj,
                teacher,
                diary_date,
                student_id,
                payload,
                category_map,
                option_pairs,
                meal_types,
            )
        self._log(
            "agendas_infantis_salvas",
            class_id=str(class_obj.pk),
            diary_date=diary_date.isoformat(),
            student_count=len(entries_data),
        )
        return len(entries_data)

    @staticmethod
    def _assert_eligible_class(class_obj) -> None:
        """Garante etapa e turno compatíveis com a Agenda."""
        if class_obj.education_stage != class_obj.EducationStage.EARLY_CHILDHOOD:
            raise BusinessRuleViolationError(
                "A agenda diária é exclusiva de turmas da Educação Infantil."
            )
        StudentDiaryService.meals_for_shift(class_obj.shift)

    def _get_authorized_teacher(self, class_obj):
        """Resolve o responsável pedagógico e valida o escopo de preenchimento."""
        from core.access_selectors import ObjectAccessSelector
        from core.permissions import can_edit_student_diary, role_name

        if not can_edit_student_diary(self.user):
            raise PermissionDeniedError("Sem permissão para preencher a Agenda.")
        teacher = getattr(self.user, "teacher_profile", None)
        if role_name(self.user) == "TEACHER":
            if teacher is None or not ObjectAccessSelector.teacher_can_access_class(
                self.user.pk, class_obj.pk
            ):
                raise PermissionDeniedError("Professor não autorizado para esta turma.")
            return teacher
        return class_obj.class_teacher

    @staticmethod
    def _validate_daily_payload(
        payload, categories, option_pairs, meal_types, current_answers=None
    ) -> None:
        """Valida respostas e refeições de um aluno."""
        errors: dict[str, list[str]] = {}
        answers = payload.get("answers", {})
        current_answers = current_answers or {}
        if set(answers) - set(categories):
            errors.setdefault("answers", []).append(
                "Um dos aspectos informados não está disponível."
            )
        for category_id, category in categories.items():
            option_id = str(answers.get(category_id, ""))
            if category.is_enabled and category.is_required and not option_id:
                errors.setdefault("answers", []).append(f"O aspecto {category.name} é obrigatório.")
            option = option_pairs.get((category_id, option_id)) if option_id else None
            if option_id and (
                option is None
                or (not category.is_enabled and current_answers.get(category_id) != option_id)
                or (not option.is_enabled and current_answers.get(category_id) != option_id)
            ):
                errors.setdefault("answers", []).append("Resposta inválida para o aspecto.")
        from student_diary.models import DiaryMeal

        valid_statuses = set(DiaryMeal.Status.values)
        meals = payload.get("meals", {})
        if set(meals) != set(meal_types) or any(
            value not in valid_statuses for value in meals.values()
        ):
            errors["meals"] = ["Informe todas as refeições previstas para o turno."]
        if errors:
            raise ValidationError(errors=errors)

    def _save_student_diary(
        self,
        class_obj,
        teacher,
        diary_date,
        student_id,
        payload,
        categories,
        option_pairs,
        meal_types,
    ) -> None:
        """Persiste um registro individual e suas respostas relacionadas."""
        from student_diary.models import DailyDiary, DiaryAnswer, DiaryMeal

        diary = DailyDiary.objects.filter(
            class_obj=class_obj, student_id=student_id, date=diary_date
        ).first()
        if diary:
            old = self._snapshot(diary, ["teacher_id", "notes"])
            diary.teacher = teacher
            diary.notes = (payload.get("notes") or "").strip()
            diary.updated_by = self.user
            diary.save(update_fields=["teacher", "notes", "updated_by", "updated_at"])
            self._record_audit("UPDATE", diary, old_values=old)
        else:
            diary = DailyDiary.objects.create(
                class_obj=class_obj,
                student_id=student_id,
                teacher=teacher,
                date=diary_date,
                notes=(payload.get("notes") or "").strip(),
                created_by=self.user,
                updated_by=self.user,
            )
            self._record_audit("INSERT", diary)

        answers = payload.get("answers", {})
        for category_id, category in categories.items():
            option_id = str(answers.get(category_id, ""))
            current = DiaryAnswer.objects.filter(diary=diary, category=category).first()
            if not option_id:
                if current:
                    current.soft_delete(user=self.user)
                    self._record_audit("DELETE", current)
                continue
            option = option_pairs[(category_id, option_id)]
            if current:
                old = self._snapshot(current, ["option_id"])
                current.option = option
                current.updated_by = self.user
                current.save(update_fields=["option", "updated_by", "updated_at"])
                self._record_audit("UPDATE", current, old_values=old)
            else:
                answer = DiaryAnswer.objects.create(
                    diary=diary,
                    category=category,
                    option=option,
                    created_by=self.user,
                    updated_by=self.user,
                )
                self._record_audit("INSERT", answer)

        for meal_type in meal_types:
            current = DiaryMeal.objects.filter(diary=diary, meal_type=meal_type).first()
            status = payload["meals"][meal_type]
            if current:
                old = self._snapshot(current, ["status"])
                current.status = status
                current.updated_by = self.user
                current.save(update_fields=["status", "updated_by", "updated_at"])
                self._record_audit("UPDATE", current, old_values=old)
            else:
                meal = DiaryMeal.objects.create(
                    diary=diary,
                    meal_type=meal_type,
                    status=status,
                    created_by=self.user,
                    updated_by=self.user,
                )
                self._record_audit("INSERT", meal)
