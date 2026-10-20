from django.urls import path
from . import views

urlpatterns = [
    path("", views.plant_list, name="plant_list"),
    path("scan/", views.scan, name="scan"),
    path("plant/<int:pk>/", views.plant_detail, name="plant_detail"),
    path("today/", views.today, name="today"),
    path("done/<int:pk>/", views.done, name="done"),
]
