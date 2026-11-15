
from datetime import timedelta
from django.utils import timezone

from shipping.models import CarrierCalendar


MAX_CALENDAR_DAYS = 366


class PromiseCalculationError(Exception):
    pass


def is_carrier_working_day(carrier, day):
    """
    If a calendar override exists, use it.
    Otherwise, Monday-Friday are working days.
    """

    override = CarrierCalendar.objects.filter(
        carrier=carrier,
        calendar_date=day
    ).first()

    if override is not None:
        return override.is_working_day

    return day.weekday() < 5


def next_working_day(carrier, start_date):
    """
    Find the first working date on or after start_date.
    """

    day = start_date

    for _ in range(MAX_CALENDAR_DAYS):
        if is_carrier_working_day(carrier, day):
            return day

        day += timedelta(days=1)

    raise PromiseCalculationError(
        "No carrier working day found within 366 days"
    )


def calculate_dispatch_date(service, order_time):
    """
    Check order time, carrier cutoff and working calendar.
    """

    if timezone.is_naive(order_time):
        raise PromiseCalculationError(
            "Order time must be timezone-aware"
        )

    local_time = timezone.localtime(
        order_time,
        timezone.get_default_timezone()
    )

    order_date = local_time.date()
    current_time = local_time.time().replace(tzinfo=None)

    # If today is closed, move to next working day.
    if not is_carrier_working_day(
        service.carrier, order_date
    ):
        return next_working_day(
            service.carrier,
            order_date + timedelta(days=1)
        )

    # If cutoff is missed, dispatch next working day.
    if current_time > service.cutoff_time:
        return next_working_day(
            service.carrier,
            order_date + timedelta(days=1)
        )

    return order_date


def calculate_delivery_date(service, dispatch_date):
    """
    Count only eligible carrier working days.
    The dispatch date is day zero.
    """

    if service.transit_days == 0:
        return dispatch_date

    day = dispatch_date
    days_counted = 0

    for _ in range(MAX_CALENDAR_DAYS):
        day += timedelta(days=1)

        if is_carrier_working_day(
            service.carrier, day
        ):
            days_counted += 1

        if days_counted == service.transit_days:
            return day

    raise PromiseCalculationError(
        "Transit time exceeds supported calendar horizon"
    )



def calculate_promise(service, order_time):

    dispatch_date = calculate_dispatch_date(
        service,
        order_time
    )

    delivery_date = calculate_delivery_date(
        service,
        dispatch_date
    )

    # Convert order timestamp to local date
    local_order_date = timezone.localtime(
        order_time,
        timezone.get_default_timezone()
    ).date()

    # Validate the promised date
    if delivery_date < local_order_date:
        raise PromiseCalculationError(
            "Promise date cannot precede the order date"
        )

    return {
        "dispatch_date": dispatch_date,
        "delivery_date": delivery_date,
    }
