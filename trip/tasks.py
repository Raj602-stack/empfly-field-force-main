from celery import shared_task

from trip.models import Trip, TripTemplate
from utils import create_data, read_data

import datetime as dt
import logging


logger = logging.getLogger(__name__)


def can_trip_be_created(trip_template: TripTemplate) -> bool:

    current_date = read_data.get_current_datetime().date()
    schedule = trip_template.schedule

    frequency = schedule.get("frequency")

    if frequency == "daily":
        if current_date.weekday() not in schedule.get("skip_days", []):
            return True
        return False

    elif frequency == "weekly":
        if current_date.weekday() == schedule.get("day"):
            return True
        return False

    elif frequency == "monthly":
        if current_date.month not in schedule.get("skip_months", []) and current_date.weekday() == schedule.get("day"):
            return True
        return False

    elif frequency == "yearly":
        date_str = schedule.get("date")
        date = dt.datetime.strptime(date_str, "%d-%m")
        if current_date.month == date.month and current_date.day == date.day:
            return True
        return False

    else:
        return False


def create_trip_from_trip_template(trip_template: TripTemplate) -> Trip:

    random_string = create_data.generate_random_string(6)
    trip_name = f"trip_template.name__{random_string}"

    if trip_template.start_location_ptr:

        start_location_ptr = trip_template.start_location_ptr
        start_location_data = {
            "name": start_location_ptr.name,
            "latitude": str(start_location_ptr.latitude),
            "longitude": str(start_location_ptr.longitude),
            "radius": str(start_location_ptr.radius),
            "email": start_location_ptr.email,
            "phone": start_location_ptr.phone,
        }
    else:
        start_location_data = trip_template.start_location

    if trip_template.end_location_ptr:

        end_location_ptr = trip_template.end_location_ptr
        end_location_data = {
            "name": end_location_ptr.name,
            "latitude": str(end_location_ptr.latitude),
            "longitude": str(end_location_ptr.longitude),
            "radius": str(end_location_ptr.radius),
            "email": end_location_ptr.email,
            "phone": end_location_ptr.phone,
        }
    else:
        end_location_data = trip_template.end_location

    try:
        return Trip.objects.create(
            organization=trip_template.organization,
            name=trip_name,
            start_location=start_location_data,
            start_location_ptr=trip_template.start_location_ptr,
            end_location=end_location_data,
            end_location_ptr=trip_template.end_location_ptr,
            assigned_to=trip_template.assigned_to,
            priority=trip_template.priority,
            date=trip_template.date,
            time=trip_template.time,
        )
    except Exception as e:
        logger.error(e)
        logger.exception(
            f"Add exception for {e.__class__.__name__} "
            "in create_trip_from_trip_template"
        )
    return None


@shared_task(name="create_trip")
def create_trips():

    trip_templates = TripTemplate.objects.filter(is_active=True)

    for trip_template in trip_templates:

        is_allowed = can_trip_be_created(trip_template)

        if is_allowed:
            trip = create_trip_from_trip_template(trip_template)
            if trip is None:
                logger.error(f"Failed to create trip for {trip_template=}")
