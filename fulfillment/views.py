
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAdminUser

from fulfillment.services import (
    allocate_order,
    AllocationError,
)


class OrderAllocationAPIView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, order_id):
        try:
            result = allocate_order(order_id)

            return Response(
                result,
                status=status.HTTP_200_OK
            )

        except AllocationError as error:
            return Response(
                {"error": str(error)},
                status=status.HTTP_400_BAD_REQUEST
            )

