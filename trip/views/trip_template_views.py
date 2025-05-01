from django.http import HttpResponse
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.db import IntegrityError

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

from api import permissions
from expense.models import RideExpense, RideExpenseDocs
from organization.models import Organization
from organization.utils import get_location

from trip import search, serializers
from trip.models import Trip, TripDetails, TripEstimation, TripScan, TripTemplate
from trip.utils import get_trip_template

from utils import create_data, fetch_data, google_api, read_data

import logging


logger = logging.getLogger(__name__)


class AllTripTemplatesAPI(views.APIView):

    permission_classes = [IsAuthenticated]
    serializer_class = serializers.TripTemplateSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        trip_templates = org.trip_templates.all()
        per_page = request.GET.get("per_page", 10)
        page = request.GET.get("page", 1)
        paginator = Paginator(trip_templates, per_page)
        page_obj = paginator.get_page(page)

        serializer = self.serializer_class(page_obj.object_list, many=True)
        return Response(
            {
                "data": serializer.data,
                "pagination": {"total_pages": paginator.num_pages, "page": page},
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        name = request.data.get("name")
        description = request.data.get("description")

        name = request.data.get("name", create_data.generate_random_string(6))
        description = request.data.get("description")

        # * Priority
        priority = request.data.get("priority")
        # if priority not in [x[0] for x in Trip.PRIORITY_CHOICES]:
        #     return Response(
        #         {"message": "Invalid priority"}, status=status.HTTP_400_BAD_REQUEST
        #     )

        # * Date and Time
        date = request.data.get("date")
        time = request.data.get("time")

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
        start_location_uuid = request.data.get("start_location_uuid")
        start_location_data = request.data.get("start_location_data")

        start_location_ptr = None
        end_location_ptr = None
        start_location = None
        end_location = None

        if start_location_uuid:
            start_location = get_location(org_uuid, start_location_uuid)

            if start_location is None:
                return read_data.get_404_response("Location")

            start_location_ptr = start_location
        else:
            start_location = start_location_data

        # * End location
        end_location_uuid = request.data.get("end_location_uuid")
        end_location_data = request.data.get("end_location_data")

        if end_location_uuid:
            end_location = get_location(org_uuid, end_location_uuid)

            if end_location is None:
                return read_data.get_404_response("Location")

            end_location_ptr = end_location
        else:
            end_location = end_location_data

        # * Assigned to
        assigned_to_uuid = request.data.get("member_uuid")
        assigned_to = fetch_data.get_member_by_uuid(org_uuid, assigned_to_uuid)
        if assigned_to is None:
            return read_data.get_404_response("Member")

        # * Schedule
        schedule = request.data.get("schedule")

        try:
            trip_template = TripTemplate.objects.create(
                organization=org,
                name=name,
                description=description,
                start_location_ptr=start_location_ptr,
                start_location=start_location,
                end_location_ptr=end_location_ptr,
                end_location=end_location,
                priority=priority,
                assigned_to=assigned_to,
                date=date,
                time=time,
                schedule=schedule,
            )
        except IntegrityError as e:
            logger.error(e)
            return read_data.get_409_response("Trip Template", "name")
        except Exception as e:
            logger.error(e)
            logger.exception(
                f"Add exception for {e.__class__.__name__} in AllTripTemplatesAPI"
            )

        serializer = self.serializer_class(trip_template)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class TripTemplatesAPI(views.APIView):

    permission_classes = [IsAuthenticated]
    serializer_class = serializers.TripTemplateSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        uuid = self.kwargs.get("uuid")
        trip_template = get_trip_template(org_uuid, uuid)
        if trip_template is None:
            return read_data.get_404_response("Trip Template")

        serializer = self.serializer_class(trip_template)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        uuid = self.kwargs.get("uuid")
        trip_template = get_trip_template(org_uuid, uuid)
        if trip_template is None:
            return read_data.get_404_response("Trip Template")

        name = request.data.get("name")
        description = request.data.get("description")
        is_active = request.data.get("is_active")

        name = request.data.get("name", create_data.generate_random_string(6))
        description = request.data.get("description")

        # * Priority
        priority = request.data.get("priority")
        if priority not in [x[0] for x in Trip.PRIORITY_CHOICES]:
            return Response(
                {"message": "Invalid priority"}, status=status.HTTP_400_BAD_REQUEST
            )

        # * Date and Time
        date = request.data.get("date")
        time = request.data.get("time")

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
        start_location_uuid = request.data.get("start_location_uuid")
        start_location_data = request.data.get("start_location_data")

        start_location_ptr = None
        end_location_ptr = None
        start_location = None
        end_location = None

        if start_location_uuid:
            start_location = get_location(org_uuid, start_location_uuid)

            if start_location is None:
                return read_data.get_404_response("Location")

            start_location_ptr = start_location
        else:
            start_location = start_location_data

        # * End location
        end_location_uuid = request.data.get("end_location_uuid")
        end_location_data = request.data.get("end_location_data")

        if end_location_uuid:
            end_location = get_location(org_uuid, end_location_uuid)

            if end_location is None:
                return read_data.get_404_response("Location")

            end_location_ptr = end_location
        else:
            end_location = end_location_data

        # * Assigned to
        assigned_to_uuid = request.data.get("member_uuid")
        assigned_to = fetch_data.get_member_by_uuid(org_uuid, assigned_to_uuid)
        if assigned_to is None:
            return read_data.get_404_response("Member")

        # * Schedule
        schedule = request.data.get("schedule")

        trip_template.name = name
        trip_template.description = description

        trip_template.start_location_ptr = start_location_ptr
        trip_template.start_location = start_location
        trip_template.end_location_ptr = end_location_ptr
        trip_template.end_location = end_location

        trip_template.priority = priority
        trip_template.date = date
        trip_template.time = time
        trip_template.assigned_to = assigned_to

        trip_template.schedule = schedule
        trip_template.is_active = is_active

        try:
            trip_template.save()
        except Exception as e:
            logger.error(e)
            logger.exception(
                f"Add exception for {e.__class__.__name__} in TripTemplatesAPI"
            )

        serializer = self.serializer_class(trip_template)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        uuid = self.kwargs.get("uuid")
        trip_template = get_trip_template(org_uuid, uuid)
        if trip_template is None:
            return read_data.get_404_response("Trip Template")

        trip_template.delete()
        return read_data.get_200_delete_response("Trip Template")
