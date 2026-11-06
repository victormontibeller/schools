"""Consultas restritas ao ensaio fictício; não oferecem impersonação em produção."""

from core.fictitious import require_fictitious


class FictitiousSelector:
    @staticmethod
    def invitation(user_id):
        from notifications.contracts import MessageLog

        require_fictitious()
        return (
            MessageLog.objects.filter(source_type="account_invitation", recipient_id=user_id)
            .latest("created_at")
            .payload["scope"]["invitation_token"]
        )

    @staticmethod
    def imported_objects(batch, model_label):
        from django.apps import apps

        require_fictitious()
        model = apps.get_model(model_label)
        return {
            entry["source_id"]: model.objects.get(pk=entry["object_id"])
            for entry in batch.manifest
            if entry["model"] == model_label
        }

    @staticmethod
    def diary_payload(class_obj):
        from classes.contracts import Enrollment
        from student_diary.selectors import StudentDiarySelector

        require_fictitious()
        categories = StudentDiarySelector().list_sheet_categories(class_obj.shift)
        answers = {
            str(category.pk): str(category.options.filter(is_enabled=True).first().pk)
            for category in categories
            if category.is_enabled
        }
        return {
            str(student_id): {"answers": answers, "notes": "Registro exclusivamente fictício."}
            for student_id in Enrollment.objects.filter(
                class_obj=class_obj, status="ACTIVE"
            ).values_list("student_id", flat=True)
        }
