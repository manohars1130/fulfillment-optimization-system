from django.contrib import admin
from .models import Allocation, OrderStatusEvent

from .models import (
    FulfillmentNode,
    Inventory,
    WarehouseCapacity
)

admin.site.register(FulfillmentNode)
admin.site.register(Inventory)
admin.site.register(WarehouseCapacity)



admin.site.register(Allocation)
admin.site.register(OrderStatusEvent)