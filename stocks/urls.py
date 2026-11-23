"""
URL configuration for stock_rspi project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.urls import path
from . import views

# from django.urls import path, include

urlpatterns = [
    path("", views.stock_list, name="stock_list"),
    path("create/", views.stock_create, name="stock_create"),
    path("edit/<str:code>/", views.stock_edit, name="stock_edit"),
    path("update/<str:code>/", views.stock_update, name="stock_update"),
    path("delete/<str:code>/", views.stock_delete, name="stock_delete"),
    path("settings/", views.score_settings, name="score_settings"),
]
