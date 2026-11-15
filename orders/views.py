
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from .models import Order
from .serializers import OrderSerializer


class OrderListCreateAPIView(generics.ListCreateAPIView):
    queryset = Order.objects.prefetch_related("lines").all()
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]


class OrderDetailAPIView(generics.RetrieveAPIView):
    queryset = Order.objects.prefetch_related("lines").all()
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "order_id"
