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


class StudentDiaryService(BaseService):
    """Gerencia configurações e registros diários infantis."""

    @staticmethod
    def meals_for_shift(shift: str) -> tuple[str, ...]:
        """Retorna as refeições obrigatórias para o turno informado."""
        from classes.models import Class
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

    def set_routine_aspect_enabled(self, category_id, enabled: bool):
        """Ativa ou desativa um aspecto fixo sem alterar seu catálogo."""
        from student_diary.models import DiaryCategory

        self._assert_configuration_actor()
        try:
            category = DiaryCategory.objects.get(pk=category_id)
        except DiaryCategory.DoesNotExist:
            raise ObjectNotFoundError("DiaryCategory", str(category_id)) from None
        if not category.code:
            raise BusinessRuleViolationError("Somente aspectos predefinidos podem ser alterados.")
        old = self._snapshot(category, ["is_enabled"])
        category.is_enabled = bool(enabled)
        category.updated_by = self.user
        category.save(update_fields=["is_enabled", "updated_by", "updated_at"])
        self._record_audit("UPDATE", category, old_values=old)
        self._log(
            "aspecto_rotina_alterado",
            category_id=str(category.pk),
            enabled=category.is_enabled,
        )
        return category

    @transaction.atomic
    def save_daily_diaries(self, class_id, diary_date: date, entries_data: dict):
        """Salva atomicamente a agenda de todos os alunos ativos da turma."""
        from classes.models import Class, Enrollment
        from student_diary.models import DiaryCategory, DiaryOption

        try:
            class_obj = Class.objects.get(pk=class_id)
        except Class.DoesNotExist:
            raise ObjectNotFoundError("Class", str(class_id)) from None
        self._assert_eligible_class(class_obj)
        teacher = self._get_authorized_teacher(class_obj)

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

        categories = list(
            DiaryCategory.objects.filter(code__isnull=False, is_enabled=True).prefetch_related(
                "options"
            )
        )
        category_map = {str(category.pk): category for category in categories}
        option_pairs = {
            (str(option.category_id), str(option.pk)): option
            for option in DiaryOption.objects.filter(category__in=categories)
        }
        meal_types = self.meals_for_shift(class_obj.shift)
        for student_id, payload in entries_data.items():
            self._validate_daily_payload(payload, category_map, option_pairs, meal_types)
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

    def _assert_configuration_actor(self) -> None:
        """Restringe configurações a administração e coordenação."""
        from core.permissions import role_name

        if not getattr(self.user, "is_superuser", False) and role_name(self.user) not in {
            "ADMIN",
            "COORDINATOR",
        }:
            raise PermissionDeniedError("Sem permissão para configurar a Agenda.")

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
    def _validate_daily_payload(payload, categories, option_pairs, meal_types) -> None:
        """Valida respostas e refeições de um aluno."""
        errors: dict[str, list[str]] = {}
        answers = payload.get("answers", {})
        for category_id, category in categories.items():
            option_id = str(answers.get(category_id, ""))
            if category.is_required and not option_id:
                errors.setdefault("answers", []).append(f"O aspecto {category.name} é obrigatório.")
            if option_id and (category_id, option_id) not in option_pairs:
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
