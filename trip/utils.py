from typing import Union
from django.core.exceptions import ValidationError
from member.models import Member
from member.serializers import MemberSerializer
from organization.models import Location
from trip.models import Trip, TripTemplate
from trip.serializers import TripSerializer

from geopy.distance import geodesic
from uuid import uuid4
import csv
import logging

from utils import fetch_data
from decimal import Decimal
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
from form_builder.constants import CREATE_TRIP_CONFIG_FIELDS, EMAIL_REGEX, URL_REGEX
from utils.response import HTTP_400
from organization.utils import get_create_trip_config_field
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def get_trip(org_uuid: uuid4, uuid: uuid4) -> Trip:

    try:
        return Trip.objects.get(organization__uuid=org_uuid, uuid=uuid)
    except (Trip.DoesNotExist, ValidationError, ValueError) as e:
        logger.error(e)
    except Exception as e:
        logger.exception(
            f"Add exception for {e.__class__.__name__} in get_my_trip")
    return None


def get_trip_template(org_uuid: uuid4, uuid: uuid4) -> Trip:

    try:
        return TripTemplate.objects.get(organization__uuid=org_uuid, uuid=uuid)
    except (TripTemplate.DoesNotExist, ValidationError, ValueError) as e:
        logger.error(e)
    except Exception as e:
        logger.exception(
            f"Add exception for {e.__class__.__name__} in get_trip_template"
        )
    return None


def get_my_trip(org_uuid: uuid4, uuid: uuid4, member: Member) -> Trip:

    try:
        return Trip.objects.get(
            organization__uuid=org_uuid, uuid=uuid, assigned_to=member
        )
    except (Trip.DoesNotExist, ValidationError, ValueError) as e:
        logger.error(e)
    except Exception as e:
        logger.exception(
            f"Add exception for {e.__class__.__name__} in get_my_trip")
    return None


def has_access_to_trip(trip: Trip, member: Member) -> bool:

    # If member is not assigned to the trip
    if (
        member == trip.assigned_to
        or trip.assigned_to.manager == member
        or fetch_data.is_admin(member)
    ):
        return True
    return False


def extract_coordinates(location: dict) -> tuple:
    """Get lat and log in tuple"""
    return (
        float(location.get("latitude")),
        float(location.get("longitude")),
    )


def extract_coordinates_as_str(location: dict) -> str:
    """Get concat lat and log"""
    lat = float(location.get("latitude"))
    long = float(location.get("longitude"))
    return f"{lat},{long}"

def extract_coordinates_from_scan_obj_as_str(scan_obj: dict) -> str:
    """Get concat lat and log"""
    return f"{scan_obj.latitude},{scan_obj.longitude}"


def calculate_distance(point1: tuple, point2: tuple) -> "distance in meters":
    """Cal dis in between 2 diff lat and log"""

    distance = geodesic(point1, point2)
    return distance.m


def round_off_value(value) -> Decimal:
    """Round off string or decimal values"""

    if isinstance(value, str):
        value = Decimal(value)

    return round(value, 2)


def create_trip_err_msg(scan_type: str, msg: str) -> dict:

    data = {
        "start_scan": {"error": None},
        "end_scan": {"error": None},
    }

    if scan_type == "start_scan":
        data["start_scan"]["error"] = msg
    elif scan_type == "end_scan":
        data["end_scan"]["error"] = msg

    return data


def save_scan_err(trip: Trip, error: dict):
    trip.trip_sync_comments = error
    trip.save()


system_location_required_field = (
    "latitude", "longitude", "name", "radius", "source", "organization")
SYSTEM_LOCATION_CREATE_USING_GOOGLE_API = "places_api"


def create_system_location(data: dict, org):
    """
        data sample
        -----------

        latitude: 9.978776
        longitude: 77.02478099999999
        name: vellathooval, Kerala, India"
        radius: 50
    """

    data["source"] = SYSTEM_LOCATION_CREATE_USING_GOOGLE_API
    data["organization"] = org

    validated_data = {}

    for field in system_location_required_field:
        if field not in data:
            print(field, "not found")
            return
        validated_data[field] = data[field]

    print(validated_data)

    try:
        Location.objects.create(
            **validated_data
        )
        print("Created")
    except Exception as err:
        pass
        # print(err)
        # logger.error(err)


def validate_create_trip_config_field(request, department):
    if not department:
        return

    if department.enable_create_trip_form_config is False:
        return

    create_trip_config_field = get_create_trip_config_field(
        department.organization.uuid, department.uuid
    )

    if not create_trip_config_field:
        return

    req_data = request.data
    validated_data = {}

    for fields in CREATE_TRIP_CONFIG_FIELDS:
        addon_data = {}
        field_data = getattr(create_trip_config_field, fields)

        if field_data is None:
            continue

        field_is_required: bool = field_data.get("required")
        field_label: str = field_data.get("label")
        field_constraint: str = field_data.get("constraint")
        field_type: str = field_data.get("type")

        print(field_is_required)
        print(field_label)
        print(field_constraint)
        print(field_constraint)

        if fields not in req_data:
            if field_is_required is True:
                # field configured in form builder not found in req.
                return HTTP_400(f"{fields} Not found.")
            if field_is_required is False:
                validated_data[fields] = {"label": field_label, "value": None}
                continue

        field_input_value = req_data[fields]

        if field_is_required:
            if not field_input_value and field_input_value not in (0,):
                return HTTP_400(f"{field_label} is required. Field name {fields}.")

        if field_input_value:
            print(field_input_value)

            if field_type == "dropdown":
                dropdown_options: list = field_data.get("options", [])

                if field_input_value not in dropdown_options:
                    print("!")
                    return HTTP_400(
                        f"{field_input_value} not found {field_label} options."
                    )

            elif field_type == "text":
                if field_constraint == "is_number":
                    try:
                        field_input_value = float(field_input_value)
                    except Exception as err:
                        print(err)
                        return HTTP_400(f"{field_label} value must be a number.")

                elif field_constraint == "is_email":
                    if isinstance(field_input_value, str) is False:
                        return HTTP_400(f"{field_label} value must be a string.")

                    if not EMAIL_REGEX.match(field_input_value):
                        return HTTP_400(
                            f"Please enter a valid email for {field_label}."
                        )
                elif field_constraint == "is_url":
                    # if not URL_REGEX.match(field_input_value):
                    #     return HTTP_400(
                    #         f"Please enter a valid URL for {field_label}."
                    #     )
                    validator = URLValidator()

                    print(field_input_value, "@@@@@@@@@@2")

                    addon_data["constraint"] = "is_url"

                    try:
                        validator(field_input_value)
                        # URL is valid
                    except ValidationError as e:
                        # URL is not valid
                        print(e)
                        return HTTP_400(
                            f"Please enter a valid URL for {field_label}."
                        )
            else:
                print("Type not found.")

        validated_data[fields] = {"label": field_label, "value": field_input_value, **addon_data}

    validated_data["create_trip_form"] = create_trip_config_field
    return validated_data

from form_builder.models import CreateTripFormSubmissions

def create_trip_config_field(validated_data, trip, department):
    if CreateTripFormSubmissions.objects.filter(trip=trip).exists():
        return

    validated_data["trip"] = trip
    validated_data["department"] = department
    validated_data["organization"] = department.organization

    return CreateTripFormSubmissions.objects.create(**validated_data)
