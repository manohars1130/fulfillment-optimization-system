
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, serializers
from rest_framework.permissions import IsAdminUser

from shipping.models import Shipment

from shipping.shipment_service import (
    create_order_shipments,
    ShipmentCreationError,
)

from shipping.tracking_service import (
    record_tracking_event,
    TrackingValidationError,
)


class TrackingInputSerializer(serializers.Serializer):
    event_type = serializers.ChoiceField(
        choices=[
            "DISPATCHED",
            "IN_TRANSIT",
            "OUT_FOR_DELIVERY",
            "DELIVERED",
            "EXCEPTION",
        ]
    )
    event_time = serializers.DateTimeField(required=False)
    remarks = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=255
    )


class CreateShipmentAPIView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, order_id):
        try:
            result = create_order_shipments(order_id)

            return Response(
                result,
                status=status.HTTP_201_CREATED
            )

        except ShipmentCreationError as error:
            return Response(
                {"error": str(error)},
                status=status.HTTP_400_BAD_REQUEST
            )


class TrackingEventAPIView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, shipment_id):
        serializer = TrackingInputSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        try:
            result = record_tracking_event(
                shipment_id=shipment_id,
                event_type=data["event_type"],
                event_time=data.get("event_time"),
                remarks=data.get("remarks", "")
            )

            return Response(
                result,
                status=status.HTTP_201_CREATED
            )

        except TrackingValidationError as error:
            return Response(
                {"error": str(error)},
                status=status.HTTP_400_BAD_REQUEST
            )




class ShipmentDetailAPIView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, shipment_id):
        try:
            shipment = Shipment.objects.select_related(
                "order", "node", "service__carrier"
            ).get(shipment_id=shipment_id)

        except Shipment.DoesNotExist:
            return Response(
                {"error": "Shipment not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        tracking = list(
            shipment.tracking_events.values(
                "event_id",
                "event_type",
                "event_time",
                "remarks"
            ).order_by("event_time", "event_id")
        )

        return Response({
            "shipment_id": shipment.shipment_id,
            "order_id": shipment.order_id,
            "warehouse": shipment.node.name,
            "carrier": shipment.service.carrier.name,
            "service": shipment.service.name,
            "status": shipment.status,
            "planned_dispatch_date": shipment.planned_dispatch_date,
            "expected_delivery_date": shipment.expected_delivery_date,
            "tracking_events": tracking,
        })

    from shipping.models import Shipment

