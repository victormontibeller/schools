from django import forms

from dashboard.models import DashboardWidget


class DashboardWidgetForm(forms.ModelForm):
    class Meta:
        model = DashboardWidget
        fields = [
            "name",
            "widget_type",
            "datasource",
            "refresh_interval",
            "position",
            "size",
            "is_visible",
            "config",
        ]
