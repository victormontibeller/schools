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


class ActivitySubmissionSelector(BaseSelector):
    """Selector para entregas — consultas paginadas."""

    @property
    def model_class(self):
        from activities.models import ActivitySubmission

        return ActivitySubmission

    def list_submissions(self, filters=None, page=1, page_size=50) -> PageResult:
        """Lista entregas paginadas, com filtros opcionais."""
        return self.list(filters=filters, page=page, page_size=page_size)
