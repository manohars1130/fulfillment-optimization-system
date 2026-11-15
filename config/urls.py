
from config.views import analytics_dashboard
from config.views import warehouse_allocation_page
from django.contrib import admin
from django.urls import path, include
from config.views import dashboard, create_order_page
from config.views import shipment_management_page


urlpatterns = [
    path("", dashboard, name="dashboard"),

    path("admin/", admin.site.urls),

    path("api/orders/", include("orders.urls")),

    path("api/", include("fulfillment.urls")),

    path("api/", include("shipping.urls")),
    path("orders/create/", create_order_page, name="create-order-page"),
    path(
    "warehouse/allocate/",
    warehouse_allocation_page,
    name="warehouse-allocation-page"
    ),
    path(
    "shipments/manage/",
    shipment_management_page,
    name="shipment-management"),
    path("api/", include("analytics.urls")),
    path(
    "analytics/",
    analytics_dashboard,
    name="analytics-dashboard"
),

]
