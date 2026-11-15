
from django.urls import path
from .views import OrderAllocationAPIView

urlpatterns = [
    path(
        "orders/<str:order_id>/allocate/",
        OrderAllocationAPIView.as_view(),
        name="allocate-order"
    ),
]

