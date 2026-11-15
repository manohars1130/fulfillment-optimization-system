
from django.db import models


class SKU(models.Model):
    sku_id = models.CharField(
        max_length=30,
        primary_key=True
    )

    name = models.CharField(max_length=150)

    category = models.CharField(max_length=100)

    unit_weight_kg = models.DecimalField(
        max_digits=8,
        decimal_places=3
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "sku"

    def __str__(self):
        return self.name