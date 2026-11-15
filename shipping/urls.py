
from django.urls import path
from .views import ShipmentDetailAPIView
from .views import (
    CreateShipmentAPIView,
    TrackingEventAPIView,
)

urlpatterns = [
    path(
        "orders/<str:order_id>/create-shipments/",
        CreateShipmentAPIView.as_view(),
        name="create-shipments"
    ),

    path(
        "shipments/<str:shipment_id>/tracking/",
        TrackingEventAPIView.as_view(),
        name="shipment-tracking"
    ),
path(
    "shipments/<str:shipment_id>/",
    ShipmentDetailAPIView.as_view(),
    name="shipment-detail"
),

]
