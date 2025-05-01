from django.core.exceptions import ValidationError

from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from member.models import Profile
from organization.utils import get_fuel, get_vehicle


from rest_framework import status, views
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from organization.serializers import FuelSerializer, VehicleSerializer
from api import permissions
from expense.models import RideExpense
from member.models import Member
from member import search, serializers
from member.filter import filter_members, convert_query_params_to_dict
from organization.utils import (
    get_department,
    get_designation,
    get_organization_location,
    get_role,
)
from trip.models import Trip, TripDetails, TripScan
from trip.search import search_trips
from trip.serializers import TripSerializer
from utils import create_data, email_funcs, fetch_data, read_data

import base64
import csv
import pandas as pd
import logging


logger = logging.getLogger(__name__)


class MemberRoleAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.MemberSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid

        member_uuid = self.kwargs.get("uuid")
        member = fetch_data.get_member_by_uuid(org_uuid, member_uuid)
        if member is None:
            return read_data.get_404_response("Member")

        if fetch_data.has_access(org_uuid, request.user, "member", member) is False:
            return read_data.get_403_response()

        serializer = self.serializer_class(member)

        return Response(serializer.data, status=status.HTTP_200_OK)

    # ! Admin only
    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        requesting_member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(requesting_member) is False:
            return read_data.get_403_response()

        member_uuid = self.kwargs.get("uuid")
        member = fetch_data.get_member_by_uuid(org.uuid, member_uuid)
        if member is None:
            return read_data.get_404_response("Member")

        if requesting_member == member:
            return Response(
                {"message": "You cannot edit your own role"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ? Is this required since only Admins can make this API call
        # ? And they cannot edit their own roles. Therefore, there will be
        # ? at least one admin by default
        admin_role = fetch_data.get_admin_role()
        admin_count = org.members.filter(role=admin_role).count()
        if fetch_data.is_admin(member) and admin_count == 1:
            return Response(
                {"message": "At least one Admin should be present"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        role_uuid = request.data.get("role_uuid")
        role = get_role(role_uuid)

        member.role = role
        member.save()

        serializer = self.serializer_class(member)

        return Response(serializer.data, status=status.HTTP_200_OK)


class MemberDesignationAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.MemberSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid

        member_uuid = self.kwargs.get("uuid")
        member = fetch_data.get_member_by_uuid(org_uuid, member_uuid)
        if member is None:
            return read_data.get_404_response("Member")

        if fetch_data.has_access(org_uuid, request.user, "member", member) is False:
            return read_data.get_403_response()

        serializer = self.serializer_class(member)

        return Response(serializer.data, status=status.HTTP_200_OK)

    # ! Admin only
    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        requesting_member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(requesting_member) is False:
            return read_data.get_403_response()

        member_uuid = self.kwargs.get("uuid")
        member = fetch_data.get_member_by_uuid(org.uuid, member_uuid)
        if member is None:
            return read_data.get_404_response("Member")

        uuid = request.data.get("designation_uuid")
        designation = get_designation(org.uuid, uuid)
        if designation is None:
            return read_data.get_404_response("Designation")

        member.designation = designation
        member.save()

        serializer = self.serializer_class(member)
        return Response(serializer.data, status=status.HTTP_200_OK)


class MemberDepartmentAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.MemberSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid

        member_uuid = self.kwargs.get("uuid")
        member = fetch_data.get_member_by_uuid(org_uuid, member_uuid)
        if member is None:
            return read_data.get_404_response("Member")

        if fetch_data.has_access(org_uuid, request.user, "member", member) is False:
            return read_data.get_403_response()

        serializer = self.serializer_class(member)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # ! Admin only
    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        requesting_member = fetch_data.get_member(request.user, org_uuid)

        if fetch_data.is_admin(requesting_member) is False:
            return read_data.get_403_response()

        member_uuid = self.kwargs.get("uuid")
        member = fetch_data.get_member_by_uuid(org_uuid, member_uuid)
        if member is None:
            return read_data.get_404_response("Member")

        uuid = request.data.get("department_uuid")
        department = get_department(org_uuid, uuid)
        if department is None:
            return read_data.get_404_response("Department")

        member.department = department
        member.save()

        serializer = self.serializer_class(member)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # ! Admin only
    def delete(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        requesting_member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(requesting_member) is False:
            return read_data.get_403_response()

        member_uuid = self.kwargs.get("uuid")
        member = fetch_data.get_member_by_uuid(org.uuid, member_uuid)
        if member is None:
            return read_data.get_404_response("Member")

        member.department = None
        member.save()

        serializer = self.serializer_class(member)
        return Response(serializer.data, status=status.HTTP_200_OK)


class MemberOrganizationLocationAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.MemberSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid

        member_uuid = self.kwargs.get("uuid")
        member = fetch_data.get_member_by_uuid(org_uuid, member_uuid)
        if member is None:
            return read_data.get_404_response("Member")

        if fetch_data.has_access(org_uuid, request.user, "member", member) is False:
            return read_data.get_403_response()

        serializer = self.serializer_class(member)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # ! Admin only
    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        requesting_member = fetch_data.get_member(request.user, org_uuid)

        if fetch_data.is_admin(requesting_member) is False:
            return read_data.get_403_response()

        member_uuid = self.kwargs.get("uuid")
        member = fetch_data.get_member_by_uuid(org_uuid, member_uuid)
        if member is None:
            return read_data.get_404_response("Member")

        uuid = request.data.get("organization_location_uuid")
        organization_location = get_organization_location(uuid)
        if organization_location is None:
            return read_data.get_404_response("Department")

        member.organization_location = organization_location
        member.save()

        serializer = self.serializer_class(member)
        return Response(serializer.data, status=status.HTTP_200_OK)


class MemberLastLocationAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.MemberSerializer

    def get(self, request, *args, **kwargs):
        """ Employees  with the last location they scanned.
        """
        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        requesting_member = fetch_data.get_member(request.user, org.uuid)


        """
        OPTIMIZE
        Currently, members are fetched. Their latest trip scan is fetched

        Instead, fetch latest completed trips for each member directly
        """

        lookup = Q(organization=org)

        if fetch_data.is_admin(requesting_member) is False:
            department_of_member = requesting_member.department_head.all()
            lookup &= (Q(manager=requesting_member) | Q(id=requesting_member.id) | Q(department__in=department_of_member))

        members = Member.objects.filter(lookup)

        filter_query = convert_query_params_to_dict(request.GET)
        members = filter_members(members, filter_query)

        search_query = request.GET.get("search")
        members = search.search_members(members, search_query)

        per_page = request.GET.get("per_page", 10)
        page = request.GET.get("page", 1)
        paginator = Paginator(members, per_page)
        page_obj = paginator.get_page(page)
        serializer = self.serializer_class(page_obj.object_list, many=True)

        for member_data in serializer.data:

            member_id = member_data.get("id")
            last_trip_scan = (
                TripScan.objects.filter(
                    Q(end_trip_details__trip__assigned_to__id=member_id)
                    | Q(start_trip_details__trip__assigned_to__id=member_id)
                )
                .order_by("-time")
                .first()
            )

            if last_trip_scan is None:
                member_data["last_location"] = None
                member_data["last_check_in_time"] = None
            else:
                member_data["last_location"] = {
                    "latitude": last_trip_scan.latitude,
                    "longitude": last_trip_scan.longitude,
                    "name": last_trip_scan.name,
                }
                member_data["last_check_in_time"] = last_trip_scan.time

        return Response(
            {
                "data": serializer.data,
                "pagination": {"total_pages": paginator.num_pages, "page": page},
            },
            status=status.HTTP_200_OK,
        )


class MemberTripStatusAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = TripSerializer

    def get(self, request, *args, **kwargs):
        """ Member can have only one trip at a time.
        """

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        member = fetch_data.get_member(request.user, org.uuid)

        ongoing_trip = Trip.objects.filter(
            Q(assigned_to=member) & Q(status="started")
        ).first()

        if ongoing_trip is None: # No ongoing trips found
            return Response({}, status=status.HTTP_200_OK)

        serializer = self.serializer_class(ongoing_trip)
        return Response(serializer.data, status=status.HTTP_200_OK)


class MemberTripsAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = TripSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        requesting_member = fetch_data.get_member(request.user, org_uuid)

        uuid = self.kwargs.get("uuid")
        member = fetch_data.get_member_by_uuid(org_uuid, uuid)
        if member is None:
            return read_data.get_404_response("Member")

        trips = Trip.objects.filter(Q(organization=org) & Q(assigned_to=member))
        if fetch_data.is_admin(member) is False:
            trips = trips.filter(assigned_to__manager=requesting_member)

        search_query = request.GET.get("search")
        trips = search_trips(trips, search_query)

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


class GetMemberFuelAndVehicleAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        requesting_member = fetch_data.get_member(request.user, org_uuid)

        if not requesting_member:
            return read_data.get_403_response()

        profile, _ = Profile.objects.get_or_create(member=requesting_member)

        preferences = profile.settings.get("preferences")

        fuel_uuid = None
        vehicle_uuid = None
        fuel = None
        vehicle = None
        data = {
            "fuel": None,
            "vehicle": None
        }

        if preferences and isinstance(preferences, dict):
            fuel_uuid = preferences.get("fuel", {}).get("uuid")
            vehicle_uuid = preferences.get("vehicle", {}).get("uuid")

        if fuel_uuid:
            fuel = get_fuel(org.uuid, fuel_uuid)
            if fuel:
                data["fuel"] = FuelSerializer(fuel).data

        if vehicle_uuid:
            vehicle = get_vehicle(org.uuid, vehicle_uuid)
            if vehicle:
                data["vehicle"] = VehicleSerializer(vehicle).data

        return Response(data,status=status.HTTP_200_OK)
