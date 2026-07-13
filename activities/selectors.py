"""ActivitySelector: consultas de atividades e entregas."""

from base.selectors import BaseSelector, PageResult


class ActivitySelector(BaseSelector):
    """Selector para a entidade Activity — lista paginada por turma/professor."""

    @property
    def model_class(self):
        from activities.models import Activity

        return Activity

    def list_activities(
        self, filters=None, order_by="-due_date", page=1, page_size=20
    ) -> PageResult:
        """Lista atividades paginadas, com filtros opcionais."""
        return self.list(filters=filters, order_by=order_by, page=page, page_size=page_size)

    def get_activity_by_id(self, activity_id):
        """Retorna a atividade pelo ID."""
        return self.get_by_id(activity_id)

    def list_submissions(self, activity_id):
        """Retorna entregas de uma atividade."""
        from activities.models import ActivitySubmission

        return ActivitySubmission.objects.filter(activity_id=activity_id).select_related("student")

    def list_groups(self, activity_id):
        """Lista grupos ativos com seus integrantes."""
        from activities.models import ActivityGroup

        return ActivityGroup.objects.filter(activity_id=activity_id).prefetch_related(
            "memberships__student"
        )

    def get_group(self, activity_id, group_id):
        """Retorna um grupo ativo da atividade com seus integrantes."""
        from activities.models import ActivityGroup
        from base.exceptions import ObjectNotFoundError

        try:
            return ActivityGroup.objects.prefetch_related("memberships__student").get(
                pk=group_id, activity_id=activity_id
            )
        except ActivityGroup.DoesNotExist:
            raise ObjectNotFoundError("ActivityGroup", str(group_id)) from None


class ActivitySubmissionSelector(BaseSelector):
    """Selector para entregas — consultas paginadas."""

    @property
    def model_class(self):
        from activities.models import ActivitySubmission

        return ActivitySubmission

    def list_submissions(self, filters=None, page=1, page_size=50) -> PageResult:
        """Lista entregas paginadas, com filtros opcionais."""
        return self.list(filters=filters, page=page, page_size=page_size)
