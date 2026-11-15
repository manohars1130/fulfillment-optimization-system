from django.contrib import admin
from .models import Order, OrderLine


class OrderLineInline(admin.TabularInline):
    model = OrderLine
    extra = 1


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_id",
        "customer_name",
        "destination_city",
        "status",
        "order_time",
    )

    inlines = [OrderLineInline]