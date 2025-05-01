from django.db import IntegrityError
from django.http import HttpResponse
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from form_builder.models import FieldReportFormSubmissions, AdminReportFormSubmissions, CreateTripFormSubmissions

from rest_framework import status, views
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from drf_yasg import openapi
from drf_yasg.openapi import IN_BODY, IN_QUERY, Parameter, Schema
from drf_yasg.utils import swagger_auto_schema
from swagger.constants import (
    SchemaConstants,
    SchemaParameters,
    SchemaPayload,
    SchemaResponse,
)
from expense.serializers import RideExpenseAndTripSerializer
from api import permissions
from export.utils import create_export_request, export_field_report_submission_csv
from organization.utils import get_location

from trip.utils import validate_create_trip_config_field, create_trip_config_field

from trip import search, serializers
from trip.filter import convert_query_params_to_dict, filter_trips, filter_expenses
from trip.models import Trip
from expense.models import RideExpense
from trip.utils import (
    create_system_location,
    get_my_trip,
    get_trip,
)
from trip.email_funcs import (
    send_trip_creation_notification,
    send_trip_cancellation_notification,
)
from utils.response import HTTP_200, HTTP_400
from utils import create_data, fetch_data, google_api, read_data
import logging
from django.http import JsonResponse
from organization.models import Location
from member.models import Member
from django.utils import timezone
from datetime import timedelta
from organization.serializers import LocationSerializer



logger = logging.getLogger(__name__)


class AllTripsAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.TripSerializer

    def add_rag_status(self, trip_data):

        AMBER = "amber"
        RED = "red"
        GREEN = "green"

        # print(type(trip_data))
        # print(trip_data)
        for data in trip_data:
            try:
                print("===================================")
                trip_planned_start_time = data["planned_start_time"]
                trip_planned_end_time = data["planned_end_time"]
                trip_status = data["status"]

                if trip_planned_start_time:
                    trip_planned_start_time = read_data.string_to_dt(
                        trip_planned_start_time
                    )

                if trip_planned_end_time:
                    trip_planned_end_time = read_data.string_to_dt(
                        trip_planned_end_time
                    )

                if not trip_planned_start_time and not trip_planned_end_time:
                    continue

                trip_actual_start_scan_dt = read_data.extract_data_from_dict(
                    data, ["trip_details", "start_scan", "time"]
                )
                trip_actual_end_scan_dt = read_data.extract_data_from_dict(
                    data, ["trip_details", "end_scan", "time"]
                )

                print(trip_actual_start_scan_dt)
                print(trip_actual_end_scan_dt)

                if trip_actual_start_scan_dt:
                    trip_actual_start_scan_dt = read_data.string_to_dt(
                        trip_actual_start_scan_dt
                    )

                if trip_actual_end_scan_dt:
                    trip_actual_end_scan_dt = read_data.string_to_dt(
                        trip_actual_end_scan_dt
                    )

                curr_dt = read_data.get_current_datetime()

                color_code = None

                if trip_planned_start_time:
                    if trip_actual_start_scan_dt:
                        if trip_actual_start_scan_dt < trip_planned_start_time:
                            color_code = AMBER
                        else:
                            color_code = RED
                    else:
                        if curr_dt > trip_planned_start_time:
                            color_code = RED

                # if trip_planned_end_time and trip_status in ("ended", "field_report_submitted", "ride_expense_created"):
                if trip_planned_end_time:
                    if trip_actual_end_scan_dt:
                        if trip_actual_end_scan_dt <= trip_planned_end_time:
                            color_code = GREEN
                        else:
                            color_code = RED
                    # else:

                data["color_code"] = color_code
            except Exception as err:
                print(err)

        return trip_data

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        member = fetch_data.get_member(request.user, org.uuid)

        lookup = Q(organization=org)

        # If not Admin
        if fetch_data.is_admin(member) is False:
            # Fetch trips that are
            # 1. Created by me
            # 2. Assigned to me
            # 3. Assigned to my subordinate
            # 4. Assign to members department manager is user

            departments_of_member = member.department_head.all()

            lookup &= (
                Q(created_by=member) | Q(assigned_to=member) | Q(assigned_to__manager=member) | Q(assigned_to__department__in=departments_of_member)
            )

        trips = Trip.objects.filter(lookup).order_by("-created_at")

        filter_query = convert_query_params_to_dict(request.GET)
        trips = filter_trips(trips, filter_query)

        search_query = request.GET.get("search")
        # trips = search.search_trips(trips, search_query)
        trips = search.search_all_trips(trips, search_query)

        if bool(request.GET.get("export_csv")) is True:
            trip_ids = trips.values_list("id", flat=True)
            export_request = create_export_request(member, "trip", list(trip_ids))
            if export_request:
                return Response(
                    {"export_request_uuid": export_request.uuid},
                    status=status.HTTP_200_OK,
                )
            return Response(
                {"export_request_uuid": None}, status=status.HTTP_400_BAD_REQUEST
            )

        if bool(request.GET.get("export_csv_for_submission")) is True:
            trip_ids = trips.values_list("id", flat=True)

            field_report_submission = FieldReportFormSubmissions.objects.filter(
                trip__id__in=trip_ids
            ).values_list("id", flat=True)

            export_request = create_export_request(
                member, "field_report_submission", list(field_report_submission)
            )

            if export_request:
                return Response(
                    {"export_request_uuid": export_request.uuid},
                    status=status.HTTP_200_OK,
                )
            return Response(
                {"export_request_uuid": None}, status=status.HTTP_400_BAD_REQUEST
            )

        if bool(request.GET.get("export_csv_for_admin_report")) is True:
            trip_ids = trips.values_list("id", flat=True)

            admin_report_submission = AdminReportFormSubmissions.objects.filter(
                trip__id__in=trip_ids
            ).values_list("id", flat=True)

            export_request = create_export_request(
                member, "admin_report_submission", list(admin_report_submission)
            )

            if export_request:
                return Response(
                    {"export_request_uuid": export_request.uuid},
                    status=status.HTTP_200_OK,
                )
            return Response(
                {"export_request_uuid": None}, status=status.HTTP_400_BAD_REQUEST
            )

        if bool(request.GET.get("export_csv_for_create_trip")) is True:
            trip_ids = trips.values_list("id", flat=True)

            create_report_submission = CreateTripFormSubmissions.objects.filter(
                trip__id__in=trip_ids
            ).values_list("id", flat=True)

            export_request = create_export_request(
                member, "create_trip_submission", list(create_report_submission)
            )

            if export_request:
                return Response(
                    {"export_request_uuid": export_request.uuid},
                    status=status.HTTP_200_OK,
                )
            return Response(
                {"export_request_uuid": None}, status=status.HTTP_400_BAD_REQUEST
            )

        per_page = request.GET.get("per_page", 10)
        page = request.GET.get("page", 1)
        paginator = Paginator(trips, per_page)
        page_obj = paginator.get_page(page)
        serializer = self.serializer_class(page_obj.object_list, many=True)

        trip_rag_analysis = org.settings.get("trip_rag_analysis", False)

        trip_data = serializer.data

        if trip_rag_analysis:
            trip_data = self.add_rag_status(trip_data)

        return Response(
            {
                "data": trip_data,
                "pagination": {"total_pages": paginator.num_pages, "page": page},
            },
            status=status.HTTP_200_OK,
        )


class MyTripsAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.TripSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        completed = request.GET.get("completed", False)
        cancelled = request.GET.get("cancelled", False)

        trips = Trip.objects.filter(
            Q(organization=org) & (Q(assigned_to=member) | Q(created_by=member))
        ).order_by("-created_at")

        if trips.filter(status="started").exists():
            ongoing = True
        else:
            ongoing = False

        if completed:
            trips = trips.filter(
                status__in=["ended", "ride_expense_created", "field_report_submitted"]
            )
        elif cancelled:
            trips = trips.filter(status__in=["cancelled"])
        else:
            trips = trips.filter(status__in=["created", "started"])

        search_query = request.GET.get("search")
        trips = search.search_trips(trips, search_query)

        per_page = request.GET.get("per_page", 10)
        page = request.GET.get("page", 1)
        paginator = Paginator(trips, per_page)
        page_obj = paginator.get_page(page)

        serializer = self.serializer_class(page_obj.object_list, many=True)
        return Response(
            {
                "data": serializer.data,
                "pagination": {"total_pages": paginator.num_pages, "page": page},
                "ongoing": ongoing,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request, *args, **kwargs):
        """Start and end trip
        for start and end trip we need locations.
        Location can be a system location or just lati and long get from google map API.

        start_location_ptr and end_location_ptr saves the lati and long. If user using system location also
        That data will save here. Because if admin deleted system location it will effect the trip.
        """

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        name = request.data.get("name", create_data.generate_random_string(6))
        description = request.data.get("description")
        priority = request.data.get("priority")
        date = request.data.get("date")
        time = request.data.get("time")

        # Feature used for RAG.
        planned_start_time = request.data.get("planned_start_time")
        planned_end_time = request.data.get("planned_end_time")

        if planned_start_time:
            planned_start_time = create_data.convert_string_to_datetime(
                planned_start_time, "%Y-%m-%d %H:%M:%S"
            )
            if planned_start_time is None:
                return HTTP_400(
                    "Planned start time is required. Datetime format is (%Y-%m-%d %H:%M:%S)."
                )
        else:
            planned_start_time = None

        if planned_end_time:
            planned_end_time = create_data.convert_string_to_datetime(
                planned_end_time, "%Y-%m-%d %H:%M:%S"
            )
            if planned_end_time is None:
                return HTTP_400(
                    "Planned end time is required. Datetime format is (%Y-%m-%d %H:%M:%S)."
                )

            if planned_start_time:
                if planned_end_time <= planned_start_time:
                    return HTTP_400(
                        "Planned end time must be grater than the planned start time."
                    )

                print(planned_start_time)
                print(read_data.get_current_datetime())

                add_tz_to_planned_dt = read_data.convert_dt_to_another_tz(
                    planned_start_time
                )

                if add_tz_to_planned_dt < read_data.get_current_datetime():
                    return HTTP_400(
                        "Planned start time cannot be less than current time."
                    )
        else:
            planned_end_time = None

        if priority is not None and priority not in [
            x[0] for x in Trip.PRIORITY_CHOICES
        ]:
            return Response(
                {"message": "Invalid priority"}, status=status.HTTP_400_BAD_REQUEST
            )

        if date:
            date = create_data.convert_string_to_date(date)
            if date is None:
                return Response(
                    {"message": "Invalid date format"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if time:
            time = create_data.convert_string_to_time(time)
            if time is None:
                return Response(
                    {"message": "Invalid time format"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # * Start location
        # User selected system location instead of google map API.
        # If its None user selected google map API
        start_location_uuid = request.data.get("start_location_uuid")
        start_location_data = request.data.get("start_location_data")

        start_location_ptr = None
        end_location_ptr = None
        default_radius = org.settings.get("geo_fencing_radius", 50)

        if start_location_uuid:
            # User selected system location
            start_location = get_location(org_uuid, start_location_uuid)

            if start_location is None:
                return read_data.get_404_response("Location")

            start_location_data = {
                "name": start_location.name,
                "latitude": str(start_location.latitude),
                "longitude": str(start_location.longitude),
                "radius": str(start_location.radius),
                "email": start_location.email,
                "phone": start_location.phone,
            }
            start_location_ptr = start_location
        else:
            # CONFIRM Mahesh: Is radius being sent in custom location
            start_location_data["radius"] = default_radius
            create_system_location(start_location_data.copy(), org)

        # * End location
        end_location_uuid = request.data.get("end_location_uuid")
        end_location_data = request.data.get("end_location_data")

        if end_location_uuid:
            # User selected system location
            end_location = get_location(org_uuid, end_location_uuid)

            if end_location is None:
                return read_data.get_404_response("Location")

            end_location_data = {
                "name": end_location.name,
                "latitude": str(end_location.latitude),
                "longitude": str(end_location.longitude),
                "radius": str(end_location.radius),
                "email": end_location.email,
                "phone": end_location.phone,
            }
            end_location_ptr = end_location
        else:
            end_location_data["radius"] = default_radius
            create_system_location(end_location_data.copy(), org)

        # * Assigned to
        assigned_to_uuid = request.data.get("member_uuid")
        assigned_to = fetch_data.get_member_by_uuid(org_uuid, assigned_to_uuid)
        if assigned_to is None:
            return read_data.get_404_response("Member")

        # member can create trip them self. Manager and admin can only create trips for other members
        if assigned_to == member:
            trip_type = "self"
        else:
            if assigned_to.manager != member and fetch_data.is_admin(member) is False:
                return Response(
                    {"message": "You cannot assign trips to this member"},
                    status=status.HTTP_403_FORBIDDEN,
                )
            trip_type = "assigned"

        if start_location_data is None:
            return Response(
                {"message": "Start location is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if end_location_data is None:
            return Response(
                {"message": "End location is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        validated_data = validate_create_trip_config_field(request, member.department)
        print("=========validated_data=========")
        print(validated_data)
        print("=========validated_data=========")

        from rest_framework.response import Response

        if isinstance(validated_data, Response):
            print("Type matches")
            return validated_data

        try:
            trip = Trip.objects.create(
                organization=org,
                name=name,
                description=description,
                start_location=start_location_data,
                end_location=end_location_data,
                start_location_ptr=start_location_ptr,
                end_location_ptr=end_location_ptr,
                assigned_to=assigned_to,
                trip_type=trip_type,
                created_by=member,
                status="created",
                priority=priority,
                date=date,
                time=time,
                planned_start_time=planned_start_time,
                planned_end_time=planned_end_time,
            )
        except IntegrityError as e:
            return read_data.get_409_response("Trip", "name")
        except Exception as e:
            logger.error(e)
            logger.exception(f"Add exception for {e.__class__.__name__} in MyTripsAPI")
            return Response(
                {"message": "Unknown error occurred"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if member != assigned_to:
            send_trip_creation_notification(trip)

        if validated_data:
            create_trip_config_field(validated_data, trip, member.department)

        serializer = self.serializer_class(trip)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AssignedTripsAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.TripSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        member = fetch_data.get_member(request.user, org.uuid)

        completed = request.GET.get("completed", False)
        cancelled = request.GET.get("cancelled", False)
        is_mobile = request.GET.get("is_mobile", "false")

        trips = Trip.objects.filter(
            Q(organization=org) & Q(assigned_to=member)
        ).order_by("-created_at")

        if trips.filter(status="started").exists():
            ongoing = True
        else:
            ongoing = False

        filter_query = convert_query_params_to_dict(request.GET)
        trips = filter_trips(trips, filter_query)

        # CONFIRM Mahesh: We can use filter_trips instead
        if completed:
            trips = trips.filter(status__in=["ended", "ride_expense_created"])
        elif cancelled:
            trips = trips.filter(status__in=["cancelled"])
        else:
            trips = trips.filter(status__in=["created", "started"])

        search_query = request.GET.get("search")
        trips = search.search_all_trips(trips, search_query)

        if is_mobile == "true":
            trips = trips.order_by("planned_start_time")

        per_page = request.GET.get("per_page", 10)
        page = request.GET.get("page", 1)
        paginator = Paginator(trips, per_page)
        page_obj = paginator.get_page(page)

        serializer = self.serializer_class(page_obj.object_list, many=True)
        return Response(
            {
                "data": serializer.data,
                "pagination": {"total_pages": paginator.num_pages, "page": page},
                "ongoing": ongoing,
            },
            status=status.HTTP_200_OK,
        )


class TripsAssignedByMeAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.TripSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        completed = request.GET.get("completed", False)
        cancelled = request.GET.get("cancelled", False)

        trips = Trip.objects.filter(
            Q(organization=org) & Q(created_by=member)
        ).order_by("-created_at")

        if trips.filter(status="started").exists():
            ongoing = True
        else:
            ongoing = False

        filter_query = convert_query_params_to_dict(request.GET)
        trips = filter_trips(trips, filter_query)

        # CONFIRM Mahesh: We can use filter_trips instead
        if completed:
            trips = trips.filter(status__in=["ended", "ride_expense_created"])
        elif cancelled:
            trips = trips.filter(status__in=["cancelled"])
        else:
            trips = trips.filter(status__in=["created", "started"])

        search_query = request.GET.get("search")
        trips = search.search_all_trips(trips, search_query)

        per_page = request.GET.get("per_page", 10)
        page = request.GET.get("page", 1)
        paginator = Paginator(trips, per_page)
        page_obj = paginator.get_page(page)

        serializer = self.serializer_class(page_obj.object_list, many=True)
        return Response(
            {
                "data": serializer.data,
                "pagination": {"total_pages": paginator.num_pages, "page": page},
                "ongoing": ongoing,
            },
            status=status.HTTP_200_OK,
        )


class TripAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.TripSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        uuid = self.kwargs.get("uuid")
        if fetch_data.is_admin(member):
            trip = Trip.objects.filter(Q(uuid=uuid) & Q(organization=org))
        else:
            trip = Trip.objects.filter(
                Q(uuid=uuid)
                & Q(organization=org)
                & (
                    Q(assigned_to=member)
                    | Q(created_by=member)
                    | Q(assigned_to__manager=member)
                )
            )

        if trip.exists():
            trip = trip.first()
        else:
            return read_data.get_404_response("Trip")

        serializer = self.serializer_class(trip)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        uuid = self.kwargs.get("uuid")

        trip = get_trip(org_uuid, uuid)
        if trip is None:
            return read_data.get_404_response("Trip")

        default_radius = org.settings.get("geo_fencing_radius", 50)

        if fetch_data.is_admin(member) is False:
            if member != trip.created_by:
                return read_data.get_403_response()

        if trip.status != "created":
            return Response(
                {"message": "Trip in progress. Cannot be edited."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # * Name & Description
        name = request.data.get("name")
        if name:
            trip.name = name

        description = request.data.get("description")
        if description:
            trip.description = description

        # Feature used for RAG.
        planned_start_time = request.data.get("planned_start_time")
        planned_end_time = request.data.get("planned_end_time")

        if planned_start_time:
            planned_start_time = create_data.convert_string_to_datetime(
                planned_start_time, "%Y-%m-%d %H:%M:%S"
            )
            if planned_start_time is None:
                return HTTP_400(
                    "Planned start time is required. Datetime format is (%Y-%m-%d %H:%M:%S)."
                )
        else:
            planned_start_time = None

        if planned_end_time:
            planned_end_time = create_data.convert_string_to_datetime(
                planned_end_time, "%Y-%m-%d %H:%M:%S"
            )
            if planned_end_time is None:
                return HTTP_400(
                    "Planned end time is required. Datetime format is (%Y-%m-%d %H:%M:%S)."
                )

            if planned_start_time:
                if planned_end_time <= planned_start_time:
                    return HTTP_400(
                        "Planned end time must be grater than the planned start time."
                    )

                print(planned_start_time)
                print(read_data.get_current_datetime())

                add_tz_to_planned_dt = read_data.convert_dt_to_another_tz(
                    planned_start_time
                )

                if add_tz_to_planned_dt < read_data.get_current_datetime():
                    return HTTP_400(
                        "Planned start time cannot be less than current time."
                    )
        else:
            planned_end_time = None

        trip.planned_start_time = planned_start_time
        trip.planned_end_time = planned_end_time

        # * Priority
        priority = request.data.get("priority")
        if priority not in [x[0] for x in Trip.PRIORITY_CHOICES]:
            return Response(
                {"message": "Invalid priority"}, status=status.HTTP_400_BAD_REQUEST
            )
        trip.priority = priority

        # * Date Time
        date = request.data.get("date")
        time = request.data.get("time")

        if date:
            date = create_data.convert_string_to_date(date)
            if date is None:
                return Response(
                    {"message": "Invalid date format"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            trip.date = date

        if time:
            time = create_data.convert_string_to_time(time)
            if time is None:
                return Response(
                    {"message": "Invalid time format"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            trip.time = time

        # * Start location
        start_location_uuid = request.data.get("start_location_uuid")
        start_location_data = request.data.get("start_location_data")
        start_location_ptr = None
        end_location_ptr = None

        if start_location_uuid:
            start_location = get_location(org_uuid, start_location_uuid)

            if start_location is None:
                return read_data.get_404_response("Location")

            start_location_data = {
                "name": start_location.name,
                "latitude": str(start_location.latitude),
                "longitude": str(start_location.longitude),
                "radius": str(start_location.radius),
                "email": start_location.email,
                "phone": start_location.phone,
            }
            start_location_ptr = start_location
        else:
            print("===========================================================")
            new_start_location_data = start_location_data.copy()
            new_start_location_data["radius"] = default_radius
            create_system_location(new_start_location_data.copy(), org)

        # * End location
        end_location_uuid = request.data.get("end_location_uuid")
        end_location_data = request.data.get("end_location_data")

        if end_location_uuid:
            end_location = get_location(org_uuid, end_location_uuid)

            if end_location is None:
                return read_data.get_404_response("Location")

            end_location_data = {
                "name": end_location.name,
                "latitude": str(end_location.latitude),
                "longitude": str(end_location.longitude),
                "radius": str(end_location.radius),
                "email": end_location.email,
                "phone": end_location.phone,
            }
            end_location_ptr = end_location
        else:
            new_end_location_data = end_location_data.copy()
            new_end_location_data["radius"] = default_radius
            create_system_location(new_end_location_data, org)

        # * Assigned to
        assigned_to_uuid = request.data.get("member_uuid")
        if assigned_to_uuid:
            assigned_to = fetch_data.get_member_by_uuid(org_uuid, assigned_to_uuid)
            if assigned_to is None:
                return read_data.get_404_response("Member")
            trip.assigned_to = assigned_to

        if start_location_data:
            trip.start_location = start_location_data
            trip.start_location_ptr = start_location_ptr

        if end_location_data:
            trip.end_location = end_location_data
            trip.end_location_ptr = end_location_ptr

        trip.updated_by = member
        trip.save()

        serializer = self.serializer_class(trip)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    def delete(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        uuid = self.kwargs.get("uuid")

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        trip = Trip.objects.filter(Q(uuid=uuid) & Q(organization=org))
        if trip.exists():
            trip = trip.first()
        else:
            return read_data.get_404_response("Trip")

        if trip.status not in ["created"]:
            return Response(
                {"message": "Trip cannot be deleted."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        trip.delete()
        return Response(
            {"message": "Successfully deleted Trip"},
            status=status.HTTP_200_OK,
        )


class TripCancelAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.TripSerializer

    CANCELLED_STATUSES = (
        "ended",
        "ride_expense_created",
        "cancelled",
    )

    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        uuid = self.kwargs.get("uuid")
        trip = get_my_trip(org_uuid, uuid, member)
        if trip is None:
            return read_data.get_404_response("Trip")

        if trip.status in self.CANCELLED_STATUSES:
            return Response(
                {"message": "Trip is already ended."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        comments = str(request.data.get("comments", ""))
        comments = comments.strip()
        if not comments:
            return Response(
                {"message": "Comments are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        trip_details = trip.trip_details
        trip_details.comments["cancellation_reason"] = comments
        trip_details.save()

        trip.status = "cancelled"
        trip.save()

        send_trip_cancellation_notification(trip)

        serializer = self.serializer_class(trip)
        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )


class SearchLocationAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]

    def get(self, request, *args, **kwargs):
        response = google_api.search_location(request, request.query_params)
        return Response(response, status=status.HTTP_200_OK)


class GetGeoCodeAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]

    def get(self, request, *args, **kwargs):
        response = google_api.get_geo_code(request, request.query_params)
        return Response(response, status=status.HTTP_200_OK)


class RecentTripsAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.TripSerializer

    def get(self, request, *args, **kwargs):
        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        # trip_status = ["ended", "ride_expense_created", "cancelled"]
        # lookup &= Q(status__in=trip_status)

        DEFAULT_STATUS = [
            "created",
            "ride_expense_created",
            "started",
            "ended",
            "cancelled",
        ]
        DEFAULT_PRIORITY = ["low", "medium", "high", "urgent"]

        # trip_status = [request.GET.get("status")] if request.GET.get("status") else DEFAULT_STATUS
        # trip_priority = [request.GET.get("priority")] if request.GET.get("priority") else DEFAULT_PRIORITY

        # lookup = Q(organization=org) & Q(assigned_to=member) &Q(status__in= trip_status) &Q(priority__in= trip_priority)
        lookup = Q(organization=org) & Q(assigned_to=member)

        trips = Trip.objects.filter(lookup).order_by("-created_at")

        filter_query = convert_query_params_to_dict(request.GET)
        trips = filter_trips(trips, filter_query)

        search_query = request.GET.get("search")
        trips = search.search_all_trips(trips, search_query)

        per_page = request.GET.get("per_page", 10)
        page = request.GET.get("page", 1)
        paginator = Paginator(trips, per_page)
        page_obj = paginator.get_page(page)

        serializer = self.serializer_class(page_obj.object_list, many=True)
        return Response(
            {
                "data": serializer.data,
                "pagination": {"total_pages": paginator.num_pages, "page": page},
            },
            status=status.HTTP_200_OK,
        )


class MyRideExpensesAPI(views.APIView):

    permission_classes = [IsAuthenticated]
    # serializer_class = serializers.RideExpenseAndTripSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        # all the expense status in the RideExpenses modal
        DEFAULT_RIDE_EXP = [
            "draft",
            "pending_approval",
            "pending_reimbursement",
            "approval_rejected",
            "reimbursement_rejected",
            "reimbursed",
        ]

        trips = RideExpense.objects.filter(
            Q(trip__organization=org)
            & Q(trip__assigned_to=member)
            & Q(trip__status__in=["ended", "ride_expense_created"])
        )

        filter_query = convert_query_params_to_dict(request.GET)
        trips = filter_expenses(trips, filter_query)

        search_query = request.GET.get("search")
        trips = search.search_all_ride_expeses(trips, search_query)

        per_page = request.GET.get("per_page", 10)
        page = request.GET.get("page", 1)
        paginator = Paginator(trips, per_page)
        page_obj = paginator.get_page(page)

        serializer = RideExpenseAndTripSerializer(page_obj.object_list, many=True)
        return Response(
            {
                "data": serializer.data,
                "pagination": {"total_pages": paginator.num_pages, "page": page},
            },
            status=status.HTTP_200_OK,
        )


class OngoingTripAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.TripSerializer

    def get(self, request, *args, **kwargs):
        """Get member current trip."""

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        trip = Trip.objects.filter(Q(assigned_to=member) & Q(status="started")).first()

        if trip is None:
            return read_data.get_404_response("Trip")
        else:
            serializer = self.serializer_class(trip)
            return Response(serializer.data, status=status.HTTP_200_OK)


class MyTripsWithUUIDAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.TripSerializer

    def post(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        trip_uuids = request.data.get("trip_uuids", [])
        print("trip_uuids: ", trip_uuids)
        trips = Trip.objects.filter(uuid__in=trip_uuids, assigned_to=member)

        serializer = self.serializer_class(trips, many=True)
        return Response(
            {
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

class TripsUploadCSVAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.TripSerializer

    def get(self, request, *args, **kwargs):

        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        schema = [
            {
                "name": "HSR Trip",
                "description": "",

                "start location name": "Agara Lake",
                "start location lat": "12.9249",
                "start location long": "77.6219",

                "end location name": "Laser Republic",
                "end location lat": "12.9148",
                "end location long": "77.6390",

                "assigned to": "admin@empfly.com",
                "priority": "low"
            },
            {
                "name": "Gurgaon Trip",
                "description": "",

                "start location name": "Sultanpur National Park",
                "start location lat": "28.3944",
                "start location long": "77.0533",

                "end location name": "Cyber Hub",
                "end location lat": "28.4947",
                "end location long": "77.0864",

                "assigned to": "admin@empfly.com",
                "priority": "low"
            },
        ]

        return Response(schema)

        # return JsonResponse(schema, safe=False, status=status.HTTP_200_OK)


    def post(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        csv_file = request.data.get("csv_file")

        if not csv_file:
            return HTTP_400("Csv file is required.")

        df = create_data.create_pandas_dataframe(csv_file)

        created_count = 0
        failed_count = 0
        failed_rows = []
        failed_reason = []
        row_count = 1

        geo_fencing_radius = org.settings.get("geo_fencing_radius", 50)
        

        for row in df.values:
            row_count += 1
            row_length = len(row)

            try:

                name = row[0]
                if name in (None, ""):
                    failed_count += 1
                    failed_rows.append(row_count)
                    continue

                name = str(name).strip()
                description = row[1]

                start_location_name = row[2]
                start_location_lat = row[3]
                start_location_long = row[4]

                end_location_name = row[5]
                end_location_lat = row[6]
                end_location_long = row[7]

                if not start_location_name:
                    start_location_name = "Start location"

                if not end_location_name:
                    end_location_name = "End location"

                assigned_to_member_email = row[8]
                priority = row[9]

                if priority not in ("low", "medium", "high", "urgent",):
                    failed_count += 1
                    failed_rows.append(row_count)
                    continue

                assigned_to = Member.objects.get(
                    organization=org, user__email=assigned_to_member_email
                )

                start_location_data = {
                    "name": start_location_name,
                    "latitude": str(start_location_lat),
                    "longitude": str(start_location_long),
                    "radius": str(geo_fencing_radius),
                    "email": "",
                    "phone": "",
                }
                end_location_data = {
                    "name": end_location_name,
                    "latitude": str(end_location_lat),
                    "longitude": str(end_location_long),
                    "radius": str(geo_fencing_radius),
                    "email": "",
                    "phone": "",
                }

                start_location_serializer = LocationSerializer(
                    data=start_location_data,
                    fields=["latitude", "longitude", "radius"]
                )

                end_location_serializer = LocationSerializer(
                    data=end_location_data,
                    fields=["latitude", "longitude", "radius"]
                )

                # print(start_location_data)

                if not start_location_serializer.is_valid():
                    # print(start_location_serializer.errors)
                    failed_rows.append(row_count)
                    failed_count += 1
                    continue

                if not end_location_serializer.is_valid():
                    # print(end_location_serializer.errors)
                    failed_rows.append(row_count)
                    failed_count += 1
                    continue

                if assigned_to == member:
                    trip_type = "self"
                else:
                    if assigned_to.manager != member and fetch_data.is_admin(member) is False:
                        failed_rows.append(row_count)
                        failed_count += 1
                        continue

                    trip_type = "assigned"

                Trip.objects.create(
                    name=name,
                    description=description,
                    # start_location_ptr=start_location,
                    # end_location_ptr=end_location,
                    assigned_to=assigned_to,
                    priority=priority,
                    trip_type=trip_type,
                    created_by=member,
                    status="created",
                    organization=org,
                    start_location=start_location_data,
                    end_location=end_location_data,
                )
                created_count += 1
            except Exception as err:
                failed_rows.append(row_count)
                failed_count += 1
                try:
                    failed_reason.append(
                        {
                            "reason": str(err.__class__.__name__),
                            "detailed_reason": str(err),
                        }
                    )
                except Exception as err:
                    pass
                logger.error(err)
                logger.exception(f"Add exception for {err.__class__.__name__} in TripsUploadCSVAPI.")

        return Response(
            {
                "created_trips": created_count,
                "failed_trips": failed_count,
                "failed_rows": failed_rows,
            },
            status=status.HTTP_201_CREATED,
        )
    


class CompletedTripsAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.TripSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        trips = Trip.objects.filter(
            Q(organization=org) & Q(assigned_to=member)
        ).order_by("-created_at")

        trips = trips.filter(
            status__in=["ended", "ride_expense_created", "field_report_submitted"]
        )

        curr_date = timezone.now()

        date_before_60_days = curr_date.date() - timedelta(days=60)


        trips = trips.filter(created_at__date__gte=date_before_60_days)

        # search_query = request.GET.get("search")
        # trips = search.search_trips(trips, search_query)

        # per_page = request.GET.get("per_page", 10)
        # page = request.GET.get("page", 1)
        # paginator = Paginator(trips, per_page)
        # page_obj = paginator.get_page(page)

        serializer = self.serializer_class(trips, many=True)
        return Response(
            {
                "data": serializer.data,
                # "pagination": {"total_pages": paginator.num_pages, "page": page},
                # "ongoing": ongoing,
            },
            status=status.HTTP_200_OK,
        )