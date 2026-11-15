
from django.urls import path
from .views import (
    OrderListCreateAPIView,
    OrderDetailAPIView,
)

urlpatterns = [
    path(
        "",
        OrderListCreateAPIView.as_view(),
        name="order-list-create"
    ),
    path(
        "<str:order_id>/",
        OrderDetailAPIView.as_view(),
        name="order-detail"
    ),
]
