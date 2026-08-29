from django.urls import path
from . import views

urlpatterns = [
    path('', views.override_list),
]
