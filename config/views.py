
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.csrf import ensure_csrf_cookie

@login_required
def dashboard(request):
    return render(request, "dashboard.html")



@login_required
def create_order_page(request):
    return render(request, "orders/create_order.html")

@staff_member_required
@ensure_csrf_cookie
def warehouse_allocation_page(request):
    return render(
        request,
        "fulfillment/allocate.html"
    )


@staff_member_required
@ensure_csrf_cookie
def shipment_management_page(request):
    return render(
        request,
        "shipping/shipments.html"
    )


@staff_member_required
def analytics_dashboard(request):
    return render(request, "analytics/dashboard.html")