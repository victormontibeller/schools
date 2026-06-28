from django.urls import path

from guardians import views

urlpatterns = [
    path("guardians/", views.guardians_list, name="guardians_list"),
    path("guardians/<uuid:pk>/", views.guardian_detail, name="guardian_detail"),
]
