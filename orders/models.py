from django.db import models
from django.core.validators import MinValueValidator


class Order(models.Model):

    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("ALLOCATED", "Allocated"),
        ("PARTIALLY_SHIPPED", "Partially Shipped"),
        ("SHIPPED", "Shipped"),
        ("PARTIALLY_DELIVERED", "Partially Delivered"),
        ("DELIVERED", "Delivered"),
        ("CANCELLED", "Cancelled"),
        ("EXCEPTION", "Exception"),
    ]

    order_id = models.CharField(
        max_length=30,
        primary_key=True
    )

    customer_name = models.CharField(max_length=150)
    destination_city = models.CharField(max_length=100)
    destination_zone = models.CharField(max_length=30)
    order_time = models.DateTimeField()

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="PENDING"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "orders"
        ordering = ["-order_time"]

    def __str__(self):
        return self.order_id


class OrderLine(models.Model):

    line_id = models.BigAutoField(primary_key=True)

    order = models.ForeignKey(
        Order,
        on_delete=models.PROTECT,
        related_name="lines"
    )

    sku = models.ForeignKey(
        "catalog.SKU",
        on_delete=models.PROTECT,
        related_name="order_lines"
    )

    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)]
    )

    class Meta:
        db_table = "order_lines"

    def __str__(self):
        return f"{self.order.order_id} - {self.sku.name}"