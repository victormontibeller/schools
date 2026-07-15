"""Operações de grupos de atividades."""

from decimal import Decimal

from django.db import transaction

from activities.services.activity import _ActivityRepo
from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError


class ActivityGroupMixin:
    """Comportamentos de composição e lançamento coletivo."""

    @transaction.atomic
    def save_group(self, activity_id, data: dict, group_id=None):
        """Cria ou edita um grupo e substitui sua composição de integrantes."""
        from activities.models import ActivityGroup, ActivityGroupMember
        from classes.contracts import Enrollment

        activity = _ActivityRepo().get_by_id(activity_id)
        self._assert_activity_actor(activity)
        if activity.modality != activity.Modality.GROUP:
            raise BusinessRuleViolationError("A atividade não está configurada como grupo.")
        self.validate_required(data, ["name", "student_ids"])
        student_ids = {str(student_id) for student_id in data["student_ids"]}
        active_ids = {
            str(student_id)
            for student_id in Enrollment.objects.filter(
                class_obj=activity.class_obj, status=Enrollment.Status.ACTIVE
            ).values_list("student_id", flat=True)
        }
        if not student_ids or not student_ids.issubset(active_ids):
            raise ValidationError(errors={"students": ["Selecione apenas alunos ativos da turma."]})
        duplicate = ActivityGroupMember.objects.filter(
            activity=activity, student_id__in=student_ids
        )
        if group_id:
            duplicate = duplicate.exclude(group_id=group_id)
        if duplicate.exists():
            raise BusinessRuleViolationError(
                "Um ou mais alunos já pertencem a outro grupo desta atividade."
            )
        name = data["name"].strip()
        same_name = ActivityGroup.objects.filter(activity=activity, name__iexact=name)
        if group_id:
            same_name = same_name.exclude(pk=group_id)
        if same_name.exists():
            raise ValidationError(errors={"name": ["Já existe um grupo com este nome."]})

        if group_id:
            try:
                group = ActivityGroup.objects.get(pk=group_id, activity=activity)
            except ActivityGroup.DoesNotExist:
                raise ObjectNotFoundError("ActivityGroup", str(group_id)) from None
            old = self._snapshot(group, ["name"])
            group.name = name
            group.updated_by = self.user
            group.save(update_fields=["name", "updated_by", "updated_at"])
            self._record_audit("UPDATE", group, old_values=old)
            for membership in group.memberships.all():
                membership.soft_delete(user=self.user)
                self._record_audit("DELETE", membership)
        else:
            group = ActivityGroup.objects.create(
                activity=activity,
                name=name,
                created_by=self.user,
                updated_by=self.user,
            )
            self._record_audit("INSERT", group)

        for student_id in student_ids:
            membership = ActivityGroupMember.objects.create(
                activity=activity,
                group=group,
                student_id=student_id,
                created_by=self.user,
                updated_by=self.user,
            )
            self._record_audit("INSERT", membership)
        self._log(
            "grupo_atividade_salvo",
            activity_id=str(activity.pk),
            group_id=str(group.pk),
            member_count=len(student_ids),
        )
        return group

    @transaction.atomic
    def apply_group_result(self, activity_id, group_id, score, feedback: str = ""):
        """Salva o resultado coletivo e o reaplica explicitamente aos integrantes."""
        from activities.models import ActivityGroup

        activity = _ActivityRepo().get_by_id(activity_id)
        self._assert_activity_actor(activity)
        try:
            group = ActivityGroup.objects.get(pk=group_id, activity=activity)
        except ActivityGroup.DoesNotExist:
            raise ObjectNotFoundError("ActivityGroup", str(group_id)) from None
        try:
            score_decimal = Decimal(str(score))
        except (ValueError, TypeError, ArithmeticError) as exc:
            raise ValidationError(errors={"score": ["Nota inválida."]}) from exc
        if score_decimal < 0 or score_decimal > activity.max_score:
            raise ValidationError(
                errors={"score": [f"Nota deve estar entre 0 e {activity.max_score}."]}
            )
        old = self._snapshot(group, ["score", "feedback"])
        group.score = score_decimal
        group.feedback = (feedback or "").strip()
        group.updated_by = self.user
        group.save(update_fields=["score", "feedback", "updated_by", "updated_at"])
        self._record_audit("UPDATE", group, old_values=old)
        for student_id in group.memberships.values_list("student_id", flat=True):
            self.record_score(activity.pk, student_id, score_decimal, group.feedback)
        self._log(
            "resultado_grupo_aplicado",
            activity_id=str(activity.pk),
            group_id=str(group.pk),
            member_count=group.memberships.count(),
        )
        return group

    def deactivate_group(self, activity_id, group_id):
        """Desativa um grupo e suas associações sem apagar notas individuais."""
        from activities.models import ActivityGroup

        activity = _ActivityRepo().get_by_id(activity_id)
        self._assert_activity_actor(activity)
        try:
            group = ActivityGroup.objects.get(pk=group_id, activity=activity)
        except ActivityGroup.DoesNotExist:
            raise ObjectNotFoundError("ActivityGroup", str(group_id)) from None
        for membership in group.memberships.all():
            membership.soft_delete(user=self.user)
            self._record_audit("DELETE", membership)
        group.soft_delete(user=self.user)
        self._record_audit("DELETE", group)
        self._log(
            "grupo_atividade_desativado",
            activity_id=str(activity.pk),
            group_id=str(group.pk),
        )
        return group

    def _deactivate_activity_groups(self, activity) -> None:
        """Desativa grupos quando a atividade volta a ser individual."""
        for group in activity.groups.all():
            self.deactivate_group(activity.pk, group.pk)
