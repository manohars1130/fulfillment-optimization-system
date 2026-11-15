
from django.urls import path

from .views import (
    DashboardSummaryAPIView,
    ValidationReportAPIView,
)

urlpatterns = [
    path(
        "dashboard/summary/",
        DashboardSummaryAPIView.as_view(),
        name="dashboard-summary"
    ),
    path(
        "validation/report/",
        ValidationReportAPIView.as_view(),
        name="validation-report"
    ),
]
