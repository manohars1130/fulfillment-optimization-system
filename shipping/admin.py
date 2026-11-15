from django.contrib import admin
from .models import (
    Shipment,
    ShipmentLine,
    ShipmentCounter,
    TrackingEvent,
    DeliveryPromise,
    Carrier,
    ServiceLevel,
    CarrierZone,
    CarrierCalendar,
)


admin.site.register(Carrier)
admin.site.register(ServiceLevel)
admin.site.register(CarrierZone)
admin.site.register(CarrierCalendar)

admin.site.register(Shipment)
admin.site.register(ShipmentLine)
admin.site.register(ShipmentCounter)
admin.site.register(TrackingEvent)
admin.site.register(DeliveryPromise)