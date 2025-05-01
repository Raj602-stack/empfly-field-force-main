from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import DataError, IntegrityError
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.http import HttpResponse, JsonResponse

from rest_framework import status, views
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from drf_yasg import openapi
from drf_yasg.openapi import IN_BODY, IN_QUERY, Parameter, Schema
from drf_yasg.utils import swagger_auto_schema
from export.utils import create_export_request
from swagger.constants import (
    SchemaConstants,
    SchemaParameters,
    SchemaPayload,
    SchemaResponse,
)
from expense.models import RideExpense
from api import permissions
from account.models import User

from organization import search, serializers
from organization.utils import (
    get_location,
    get_fuel,
    get_cost_matrix,
    get_vehicle,
)
from organization.models import Fuel, Location, RideExpenseCostMatrix, Vehicle, Department

from utils import create_data, fetch_data, read_data

import pandas as pd
import csv
import logging

logger = logging.getLogger(__name__)


class AllVehiclesAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.VehicleSerializer

    @swagger_auto_schema(
        tags=["Vehicles"],
        operation_id="List all vehicles",
        responses={
            200: serializer_class(many=True),
            429: SchemaResponse.get_429(),
            500: SchemaResponse.get_500(),
        },
        manual_parameters=[
            SchemaParameters.get_page(),
            SchemaParameters.get_per_page(),
        ],
    )
    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        vehicles = org.vehicles.all()
        search_query = request.GET.get("search")
        vehicles = search.search_vehicles(vehicles, search_query)
        preferred_vehicle = member.profile.settings.get("preferences", {}).get(
            "vehicle"
        )

        per_page = request.GET.get("per_page", 10)
        page = request.GET.get("page", 1)

        paginator = Paginator(vehicles, per_page)
        page_obj = paginator.get_page(page)
        serializer = self.serializer_class(page_obj.object_list, many=True)

        return Response(
            {
                "data": serializer.data,
                "preferred_vehicle": preferred_vehicle,
                "pagination": {"total_pages": paginator.num_pages, "page": page},
            },
            status=status.HTTP_200_OK,
        )

    @swagger_auto_schema(
        tags=["Vehicles"],
        operation_id="Create vehicle",
        responses={
            201: serializer_class(),
            400: SchemaResponse.get_response(
                {"message": "Failed to create vehicle"}, description="Failed"
            ),
            409: SchemaResponse.get_409("vehicle", "name"),
            429: SchemaResponse.get_429(),
            500: SchemaResponse.get_500(),
        },
        request_body=Schema(
            properties={
                "name": Schema(
                    description="Name of the vehicle",
                    type=openapi.TYPE_STRING,
                ),
                "description": Schema(
                    description="Description of the vehicle",
                    type=openapi.TYPE_STRING,
                ),
                "auto_approval_limit": Schema(
                    description="Auto approval limit of the vehicle",
                    type=openapi.TYPE_STRING,
                ),
            },
            type=openapi.TYPE_OBJECT,
            required=["name", "description"],
        ),
    )
    def post(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        requesting_member = fetch_data.get_member(request.user, org_uuid)

        if fetch_data.is_admin(requesting_member) is False:
            return read_data.get_403_response()

        name = request.data.get("name")
        description = request.data.get("description")
        auto_approval_limit = request.data.get("auto_approval_limit")

        if auto_approval_limit is not None:
            try:
                auto_approval_limit = float(auto_approval_limit)
            except Exception as e:
                logger.error(e)
                logger.exception(
                    f"Add exception for {e.__class__.__name__} in VehicleAPI"
                )
                auto_approval_limit = None

        try:
            vehicle = Vehicle.objects.create(
                name=name,
                description=description,
                organization=org,
                auto_approval_limit=auto_approval_limit,
            )
        except IntegrityError as e:
            return read_data.get_409_response("Vehicle", "name")
        except Exception as e:
            logger.error(e)
            logger.exception(
                f"Add exception for {e.__class__.__name__} in AllVehiclesAPI"
            )
            return Response(
                {"message": "Failed to create Vehicle"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.serializer_class(vehicle)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class VehicleAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.VehicleSerializer

    @swagger_auto_schema(
        tags=["Vehicles"],
        operation_id="Get a vehicle",
        responses={
            200: serializer_class(),
            404: SchemaResponse.get_404("vehicle"),
            429: SchemaResponse.get_429(),
            500: SchemaResponse.get_500(),
        },
        manual_parameters=[SchemaParameters.get_uuid("vehicle")],
    )
    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        vehicle_uuid = self.kwargs.get("uuid")
        vehicle = get_vehicle(vehicle_uuid)
        if vehicle is None:
            return read_data.get_404_response("Vehicle")

        serializer = self.serializer_class(vehicle)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    @swagger_auto_schema(
        tags=["Vehicles"],
        operation_id="Update vehicle",
        responses={
            200: serializer_class(),
            400: SchemaResponse.get_response(
                {"message": "Failed to create vehicle"}, description="Failed"
            ),
            409: SchemaResponse.get_409("vehicle", "name"),
            429: SchemaResponse.get_429(),
            500: SchemaResponse.get_500(),
        },
        request_body=Schema(
            properties={
                "name": Schema(
                    description="Name of the vehicle",
                    type=openapi.TYPE_STRING,
                ),
                "description": Schema(
                    description="Description of the vehicle",
                    type=openapi.TYPE_STRING,
                ),
                "auto_approval_limit": Schema(
                    description="Auto approval limit of the vehicle",
                    type=openapi.TYPE_STRING,
                ),
            },
            type=openapi.TYPE_OBJECT,
            required=["name", "description"],
        ),
    )
    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        vehicle_uuid = self.kwargs.get("uuid")
        try:
            vehicle = org.vehicles.get(uuid=vehicle_uuid)
        except (Vehicle.DoesNotExist, ValidationError) as e:
            return read_data.get_404_response("Vehicle")

        name = request.data.get("name", vehicle.name)
        description = request.data.get("description", vehicle.description)
        auto_approval_limit = request.data.get(
            "auto_approval_limit", vehicle.auto_approval_limit
        )

        if auto_approval_limit is not None:
            try:
                auto_approval_limit = float(auto_approval_limit)
            except Exception as e:
                logger.error(e)
                logger.exception(
                    f"Add exception for {e.__class__.__name__} in VehicleAPI"
                )
                auto_approval_limit = None

        vehicle.name = name
        vehicle.description = description
        vehicle.auto_approval_limit = auto_approval_limit

        try:
            vehicle.save()
        except IntegrityError as e:
            return Response(
                {"message": "Vehicle with name already exists"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.serializer_class(vehicle)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    @swagger_auto_schema(
        tags=["Vehicles"],
        operation_id="Delete a vehicle",
        responses={
            200: SchemaResponse.get_200_delete("vehicle"),
            404: SchemaResponse.get_404("vehicle"),
            429: SchemaResponse.get_429(),
            500: SchemaResponse.get_500(),
        },
        manual_parameters=[SchemaParameters.get_uuid("vehicle")],
    )
    def delete(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        vehicle_uuid = self.kwargs.get("uuid")
        vehicle = get_vehicle(org_uuid, vehicle_uuid)
        if vehicle is None:
            return read_data.get_404_response("Vehicle")

        name = request.data.get("name", vehicle.name)
        description = request.data.get("description", vehicle.description)

        vehicle.name = name
        vehicle.description = description

        if RideExpense.objects.filter(trip__organization=org, vehicle=vehicle).exists():
            return Response(
                {"message": "Vehicle being used in Ride Expense."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if RideExpenseCostMatrix.objects.filter(organization=org, vehicle=vehicle).exists():
            return Response(
                {"message": "Vehicle being used in Cost Matrices."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            vehicle.delete()
        except ProtectedError as e:
            logger.error(e)
            return Response(
                {"message": "Vehicle being used in Cost Matrices"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"message": "Successfully deleted Vehicle"},
            status=status.HTTP_200_OK,
        )


class AllFuelsAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.FuelSerializer

    @swagger_auto_schema(
        tags=["Fuels"],
        operation_id="List all fuels",
        responses={
            200: serializer_class(many=True),
            429: SchemaResponse.get_429(),
            500: SchemaResponse.get_500(),
        },
        manual_parameters=[
            SchemaParameters.get_page(),
            SchemaParameters.get_per_page(),
        ],
    )
    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        preferred_fuel = member.profile.settings.get("preferences", {}).get("fuel")
        fuels = org.fuels.all()
        search_query = request.GET.get("search")
        fuels = search.search_fuels(fuels, search_query)

        per_page = request.GET.get("per_page", 10)
        page = request.GET.get("page", 1)

        paginator = Paginator(fuels, per_page)
        page_obj = paginator.get_page(page)
        serializer = self.serializer_class(page_obj.object_list, many=True)

        return Response(
            {
                "data": serializer.data,
                "preferred_fuel": preferred_fuel,
                "pagination": {"total_pages": paginator.num_pages, "page": page},
            },
            status=status.HTTP_200_OK,
        )

    @swagger_auto_schema(
        tags=["Fuels"],
        operation_id="Create fuel",
        responses={
            201: serializer_class(),
            400: SchemaResponse.get_response(
                {"message": "Failed to create fuel"}, description="Failed"
            ),
            409: SchemaResponse.get_409("fuel", "name"),
            429: SchemaResponse.get_429(),
            500: SchemaResponse.get_500(),
        },
        request_body=Schema(
            properties={
                "name": Schema(
                    description="Name of the fuel",
                    type=openapi.TYPE_STRING,
                ),
                "description": Schema(
                    description="Description of the fuel",
                    type=openapi.TYPE_STRING,
                ),
            },
            type=openapi.TYPE_OBJECT,
            required=["name", "description"],
        ),
    )
    def post(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        requesting_member = fetch_data.get_member(request.user, org_uuid)

        if fetch_data.is_admin(requesting_member) is False:
            return read_data.get_403_response()

        name = request.data.get("name")
        description = request.data.get("description")

        try:
            fuel = Fuel.objects.create(
                name=name, description=description, organization=org
            )
        except IntegrityError as e:
            return read_data.get_409_response("Fuel", "name")
        serializer = self.serializer_class(fuel)

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class FuelAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.FuelSerializer

    @swagger_auto_schema(
        tags=["Fuels"],
        operation_id="Get a fuel",
        responses={
            200: serializer_class(),
            404: SchemaResponse.get_404("fuel"),
            429: SchemaResponse.get_429(),
            500: SchemaResponse.get_500(),
        },
        manual_parameters=[SchemaParameters.get_uuid("fuel")],
    )
    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        fuel_uuid = self.kwargs.get("uuid")
        fuel = get_fuel(org.uuid, fuel_uuid)
        if fuel is None:
            return read_data.get_404_response("Fuel")

        serializer = self.serializer_class(fuel)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    @swagger_auto_schema(
        tags=["Fuels"],
        operation_id="Create fuel",
        responses={
            200: serializer_class(),
            400: SchemaResponse.get_response(
                {"message": "Failed to create fuel"}, description="Failed"
            ),
            409: SchemaResponse.get_409("Fuel", "name"),
            429: SchemaResponse.get_429(),
            500: SchemaResponse.get_500(),
        },
        request_body=Schema(
            properties={
                "name": Schema(
                    description="Name of the fuel",
                    type=openapi.TYPE_STRING,
                ),
                "description": Schema(
                    description="Description of the fuel",
                    type=openapi.TYPE_STRING,
                ),
            },
            type=openapi.TYPE_OBJECT,
            required=["name", "description"],
        ),
    )
    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        fuel_uuid = self.kwargs.get("uuid")
        fuel = get_fuel(org.uuid, fuel_uuid)
        if fuel is None:
            return read_data.get_404_response("Fuel")

        name = request.data.get("name", fuel.name)
        description = request.data.get("description", fuel.description)

        fuel.name = name
        fuel.description = description
        try:
            fuel.save()
        except IntegrityError as e:
            logger.error(e)
            return Response(
                {"message": "Fuel with name already exists"},
                status=status.HTTP_409_CONFLICT,
            )

        serializer = self.serializer_class(fuel)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    @swagger_auto_schema(
        tags=["Fuels"],
        operation_id="Delete a fuel",
        responses={
            200: SchemaResponse.get_200_delete("fuel"),
            404: SchemaResponse.get_404("fuel"),
            429: SchemaResponse.get_429(),
            500: SchemaResponse.get_500(),
        },
        manual_parameters=[SchemaParameters.get_uuid("fuel")],
    )
    def delete(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        fuel_uuid = self.kwargs.get("uuid")
        fuel = get_fuel(org.uuid, fuel_uuid)
        if fuel is None:
            return read_data.get_404_response("Fuel")

        name = request.data.get("name", fuel.name)
        description = request.data.get("description", fuel.description)

        fuel.name = name
        fuel.description = description
        
        if RideExpenseCostMatrix.objects.filter(organization=org, fuel=fuel).exists():
            return Response(
                {"message": "Fuel being used in Cost Matrices."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if RideExpense.objects.filter(trip__organization=org, fuel=fuel).exists():
            return Response(
                {"message": "Fuel being used in Ride Expense."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            fuel.delete()
        except ProtectedError as e:
            logger.error(e)
            return Response(
                {"message": "Fuel being used in Cost Matrices."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"message": "Successfully deleted Fuel"},
            status=status.HTTP_200_OK,
        )


class AllRideExpenseCostMatrixAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.RideExpenseCostMatrixSerializer

    @swagger_auto_schema(
        tags=["Cost Matrices"],
        operation_id="List all cost matrices",
        responses={
            200: serializer_class(many=True),
            429: SchemaResponse.get_429(),
            500: SchemaResponse.get_500(),
        },
        manual_parameters=[
            SchemaParameters.get_page(),
            SchemaParameters.get_per_page(),
        ],
    )
    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        cost_matrices = org.cost_matrices.all()
        search_query = request.GET.get("search")
        cost_matrices = search.search_cost_matrices(cost_matrices, search_query)

        per_page = request.GET.get("per_page", 10)
        page = request.GET.get("page", 1)
        paginator = Paginator(cost_matrices, per_page)
        page_obj = paginator.get_page(page)

        serializer = self.serializer_class(page_obj.object_list, many=True)
        return Response(
            {
                "data": serializer.data,
                "pagination": {"total_pages": paginator.num_pages, "page": page},
            },
            status=status.HTTP_200_OK,
        )

    @swagger_auto_schema(
        tags=["Cost Matrices"],
        operation_id="Create cost matrix",
        responses={
            201: serializer_class(),
            400: SchemaResponse.get_response(
                {"message": "Failed to create object"}, description="Failed"
            ),
            409: SchemaResponse.get_409("cost matrix", "fuel/vehicle"),
            429: SchemaResponse.get_429(),
            500: SchemaResponse.get_500(),
        },
        request_body=Schema(
            properties={
                "fuel_uuid": SchemaPayload.get_uuid("fuel"),
                "vehicle_uuid": SchemaPayload.get_uuid("vehicle"),
                "distance_unit": Schema(
                    description="Unit of distance",
                    type=openapi.TYPE_STRING,
                ),
                "cost_per_unit": Schema(
                    description="Cost per unit distance",
                    type="decimal",
                ),
            },
            type=openapi.TYPE_OBJECT,
            required=["fuel_uuid", "vehicle_uuid", "distance_unit", "cost_per_unit"],
        ),
    )
    def post(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        fuel_uuid = request.data.get("fuel_uuid")
        fuel = get_fuel(org_uuid, fuel_uuid)
        if fuel is None:
            return read_data.get_404_response("Fuel")

        vehicle_uuid = request.data.get("vehicle_uuid")
        vehicle = get_vehicle(org_uuid, vehicle_uuid)
        if fuel is None:
            return read_data.get_404_response("Vehicle")

        distance_unit = request.data.get("distance_unit")
        distance_unit = "kilometer"

        cost_per_unit = request.data.get("cost_per_unit")

        try:
            cost_matrix = RideExpenseCostMatrix.objects.create(
                organization=org,
                fuel=fuel,
                vehicle=vehicle,
                distance_unit=distance_unit,
                cost_per_unit=cost_per_unit,
            )
        except IntegrityError as e:
            return Response(
                {"message": "Cost Matrix already exists"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.serializer_class(cost_matrix)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class RideExpenseCostMatrixAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.RideExpenseCostMatrixSerializer

    @swagger_auto_schema(
        tags=["Trips"],
        operation_id="Get a cost matrix",
        responses={
            200: serializer_class(),
            404: SchemaResponse.get_404("cost matrix"),
        },
        manual_parameters=[SchemaParameters.get_uuid("cost matrix")],
    )
    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        member = fetch_data.get_member(request.user, org.uuid)

        uuid = self.kwargs.get("uuid")
        cost_matrix = get_cost_matrix(org.uuid, uuid)
        if cost_matrix is None:
            return read_data.get_404_response("Cost Matrix")

        serializer = self.serializer_class(cost_matrix)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    @swagger_auto_schema(
        tags=["Cost Matrices"],
        operation_id="Update cost matrix",
        responses={
            200: serializer_class(),
            400: SchemaResponse.get_response(
                {"message": "Failed to create object"}, description="Failed"
            ),
            409: SchemaResponse.get_409("cost matrix", "fuel/vehicle"),
            429: SchemaResponse.get_429(),
            500: SchemaResponse.get_500(),
        },
        request_body=Schema(
            properties={
                "fuel_uuid": SchemaPayload.get_uuid("fuel"),
                "vehicle_uuid": SchemaPayload.get_uuid("vehicle"),
                "distance_unit": Schema(
                    description="Unit of distance",
                    type=openapi.TYPE_STRING,
                ),
                "cost_per_unit": Schema(
                    description="Cost per unit distance",
                    type="decimal",
                ),
            },
            type=openapi.TYPE_OBJECT,
            required=["fuel_uuid", "vehicle_uuid", "distance_unit", "cost_per_unit"],
        ),
    )
    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        member = fetch_data.get_member(request.user, org.uuid)

        uuid = self.kwargs.get("uuid")
        cost_matrix = get_cost_matrix(org.uuid, uuid)
        if cost_matrix is None:
            return read_data.get_404_response("Cost  Matrix")

        distance_unit = request.data.get("distance_unit", cost_matrix.distance_unit)
        cost_per_unit = request.data.get("cost_per_unit", cost_matrix.cost_per_unit)

        cost_matrix.distance_unit = distance_unit
        cost_matrix.cost_per_unit = cost_per_unit

        try:
            cost_matrix.save()
        except IntegrityError as e:
            return Response(
                {"message": "Cost Matrix already exists"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.serializer_class(cost_matrix)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    @swagger_auto_schema(
        tags=["Cost Matrices"],
        operation_id="Delete a cost matrix",
        responses={
            200: SchemaResponse.get_200_delete("cost matrix"),
            404: SchemaResponse.get_404("cost matrix"),
            429: SchemaResponse.get_429(),
            500: SchemaResponse.get_500(),
        },
        manual_parameters=[SchemaParameters.get_uuid("cost matrix")],
    )
    def delete(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        uuid = self.kwargs.get("uuid")
        cost_matrix = get_cost_matrix(org.uuid, uuid)
        if cost_matrix is None:
            return read_data.get_404_response("Cost Matrix")

        cost_matrix.delete()

        return Response(
            {"message": "Successfully deleted Cost Matrix"},
            status=status.HTTP_200_OK,
        )


class AllLocationsAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.LocationSerializer

    @swagger_auto_schema(
        tags=["Locations"],
        operation_id="List all locations",
        responses={
            200: serializer_class(many=True),
            429: SchemaResponse.get_429(),
            500: SchemaResponse.get_500(),
        },
        manual_parameters=[
            SchemaParameters.get_page(),
            SchemaParameters.get_per_page(),
        ],
    )
    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        locations = org.locations.all()
        search_query = request.GET.get("search")
        locations = search.search_locations(locations, search_query)

        if bool(request.GET.get("export_csv")) is True:
            locations = locations.values_list("id", flat=True)
            export_request = create_export_request(member, "locations", list(locations))
            if export_request is None:
                return Response({"export_request_uuid": None}, status=status.HTTP_400_BAD_REQUEST)
            return Response({"export_request_uuid": export_request.uuid}, status=status.HTTP_200_OK)

        per_page = request.GET.get("per_page", 10)
        page = request.GET.get("page", 1)

        paginator = Paginator(locations, per_page)
        page_obj = paginator.get_page(page)
        serializer = self.serializer_class(page_obj.object_list, many=True)

        return Response(
            {
                "data": serializer.data,
                "pagination": {"total_pages": paginator.num_pages, "page": page},
            },
            status=status.HTTP_200_OK,
        )

    @swagger_auto_schema(
        tags=["Locations"],
        operation_id="Create location",
        responses={
            201: serializer_class(),
            400: SchemaResponse.get_response(
                {"message": "Failed to create location"}, description="Failed"
            ),
            429: SchemaResponse.get_429(),
            500: SchemaResponse.get_500(),
        },
        request_body=Schema(
            properties={
                "name": Schema(
                    description="Name of the location",
                    type=openapi.TYPE_STRING,
                ),
                "description": Schema(
                    description="Description of the location",
                    type=openapi.TYPE_STRING,
                ),
                "latitude": Schema(
                    description="Latitude of the location",
                    type="decimal",
                ),
                "longitude": Schema(
                    description="Longitude of the location",
                    type="decimal",
                ),
                "radius": Schema(
                    description="Geofencing radius of the location",
                    type="decimal",
                    default=50.0,
                ),
                "email": Schema(
                    description="Location contact's email",
                    type="email",
                ),
                "phone": Schema(
                    description="Location contact's phone number",
                    type=openapi.TYPE_STRING,
                ),
            },
            type=openapi.TYPE_OBJECT,
            required=["name", "latitude", "longitude"],
        ),
    )
    def post(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        requesting_member = fetch_data.get_member(request.user, org_uuid)

        if fetch_data.is_admin(requesting_member) is False:
            return read_data.get_403_response()

        name = request.data.get("name")
        description = request.data.get("description")
        latitude = request.data.get("latitude")
        longitude = request.data.get("longitude")
        radius = request.data.get("radius", 50)
        email = request.data.get("email")
        phone = request.data.get("phone")
        department = request.data.get("department")

        # checking department in db with error handling
        if department:
            try:
                department = Department.objects.get(uuid=department)
            except Department.DoesNotExist:
                return Response(
                    {"message": "Sorry! Department not found in database"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            department = None

        try:
            location = Location.objects.create(
                organization=org,
                name=name,
                description=description,
                latitude=latitude,
                longitude=longitude,
                radius=radius,
                email=email,
                phone=phone,
                department=department
            )
        except DataError as e:
            return Response(
                {"message": "Enter valid coordinates"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except IntegrityError as e:
            logger.error(e)
            if "location_radius_range" in str(e):
                return Response(
                    {"message": "Radius has to be between 0.0-5000.0"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return read_data.get_409_response("Location", "name")
        except Exception as e:
            logger.error(e)
            logger.exception(
                f"Add exception for {e.__class__.__name__} in AllLocationsAPI"
            )
            return Response(
                {"message": "Failed to create Location"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.serializer_class(location)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class LocationAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.LocationSerializer

    @swagger_auto_schema(
        tags=["Locations"],
        operation_id="Get a location",
        responses={
            200: serializer_class(),
            404: SchemaResponse.get_404("location"),
            429: SchemaResponse.get_429(),
            500: SchemaResponse.get_500(),
        },
        manual_parameters=[SchemaParameters.get_uuid("location")],
    )
    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        location_uuid = self.kwargs.get("uuid")
        location = get_location(org_uuid, location_uuid)
        if location is None:
            return read_data.get_404_response("Location")
        serializer = self.serializer_class(location)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    @swagger_auto_schema(
        tags=["Locations"],
        operation_id="Create location",
        responses={
            200: serializer_class(),
            400: SchemaResponse.get_response(
                {"message": "Failed to create location"}, description="Failed"
            ),
            429: SchemaResponse.get_429(),
            500: SchemaResponse.get_500(),
        },
        request_body=Schema(
            properties={
                "name": Schema(
                    description="Name of the location",
                    type=openapi.TYPE_STRING,
                ),
                "description": Schema(
                    description="Description of the location",
                    type=openapi.TYPE_STRING,
                ),
                "latitude": Schema(
                    description="Latitude of the location",
                    type="decimal",
                ),
                "longitude": Schema(
                    description="Longitude of the location",
                    type="decimal",
                ),
                "radius": Schema(
                    description="Geofencing radius of the location",
                    type="decimal",
                    default=50.0,
                ),
                "email": Schema(
                    description="Location contact's email",
                    type="email",
                ),
                "phone": Schema(
                    description="Location contact's phone number",
                    type=openapi.TYPE_STRING,
                ),
            },
            type=openapi.TYPE_OBJECT,
            required=["name", "latitude", "longitude"],
        ),
    )
    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        location_uuid = self.kwargs.get("uuid")
        location = get_location(org_uuid, location_uuid)
        if location is None:
            return read_data.get_404_response("Location")

        name = request.data.get("name", location.name)
        description = request.data.get("description", location.description)
        latitude = request.data.get("latitude", location.latitude)
        longitude = request.data.get("longitude", location.longitude)
        radius = request.data.get("radius", location.radius)
        email = request.data.get("email", location.email)
        phone = request.data.get("phone", location.phone)
        department = request.data.get("department")

        # checking department in db with error handling
        if department:
            try:
                department = Department.objects.get(uuid=department)
            except Department.DoesNotExist:
                return Response(
                    {"message": "Sorry! Department not found in database"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            department = None

        if radius is None:
            radius = 50

        location.name = name
        location.description = description
        location.latitude = latitude
        location.longitude = longitude
        location.radius = radius
        location.email = email
        location.phone = phone
        location.department = department

        try:
            location.save()
        except IntegrityError as e:
            logger.error(e)
            if "location_radius_range" in str(e):
                return Response(
                    {"message": "Radius has to be between 0.0-5000.0"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return read_data.get_409_response("Location", "name")
        except Exception as e:
            logger.error(e)
            logger.exception(f"Add exception for {e.__class__.__name__} in LocationAPI")
            return Response(
                {"message": "Failed to update Location"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.serializer_class(location)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    @swagger_auto_schema(
        tags=["Locations"],
        operation_id="Delete a location",
        responses={
            200: SchemaResponse.get_200_delete("location"),
            404: SchemaResponse.get_404("location"),
            429: SchemaResponse.get_429(),
            500: SchemaResponse.get_500(),
        },
        manual_parameters=[SchemaParameters.get_uuid("location")],
    )
    def delete(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        location_uuid = self.kwargs.get("uuid")
        location = get_location(org_uuid, location_uuid)
        if location is None:
            return read_data.get_404_response("Location")

        location.delete()

        return Response(
            {"message": "Successfully deleted Location"},
            status=status.HTTP_200_OK,
        )


class LocationsUploadCSVAPI(views.APIView):

    permission_classes = [IsAuthenticated]
    serializer_class = serializers.LocationSerializer

    def get(self, request, *args, **kwargs):
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        schema = [
            {
                "name": "Indiranagar",
                "description": "Indiranagar center",
                "latitude": 12.97837181055267,
                "longitude": 77.64436068922599,
                "radius": 200,
                "department": "Sales"
            },
            {
                "name": "HSR Layout",
                "description": "HSR Layout center",
                "latitude": 24.97837181055267,
                "longitude": 99.64436068922599,
                "radius": 55,
                "department": "Marketing"
            },
        ]

        return JsonResponse(schema, safe=False, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        csv_file = request.data.get("csv_file")
        df = create_data.create_pandas_dataframe(csv_file)

        failed_rows = []
        failed_locations = []
        row_count = 1
        updated_count = 0
        created_locations = 0

        all_locations = Location.objects.filter(organization=org)

        for row in df.values:
            row_count += 1

            try:
                is_update = 0 # if not update value must be 0
                row_length = len(row)
                

                # print(f'department_name: {department_name}')
                # print(f'row_length: {row_length}')

                department_obj = None


                # Upload
                if row_length == 6: 
                    if not row[0]:
                        raise ValidationError("name cannot be null")
                    
                    department_name = row[5]
                    
                    department_obj = None
                    if department_name:
                        try:
                            department_obj = Department.objects.get(name=department_name, organization=org)
                        except Department.DoesNotExist:
                            pass

                    location = all_locations.filter(name=row[0]) # check with name

                    if not location.exists():
                        Location.objects.create(
                            organization=org,
                            name=row[0],
                            description=row[1],
                            latitude=row[2],
                            longitude=row[3],
                            radius= org.settings.get("geo_fencing_radius") if not row[4] and not row[4] == 0 else row[4],
                            department=department_obj
                        )
                        created_locations += 1

                        continue
                    else:
                        location = location.first()
                
                # Update
                if row_length == 8:
                    location = all_locations.filter(id=row[0], organization=org).get() # check with pk
                    is_update = 1

                    department_name = row[7]

                    if row[1]:
                        location.name = row[1]

                    if row[7]:
                        if department_name:
                            try:
                                department_obj = Department.objects.get(name=department_name, organization=org)
                            except Department.DoesNotExist:
                                pass

                description=row[1 + is_update]
                latitude=row[2 + is_update]
                longitude=row[3 + is_update]
                radius = row[4 + is_update]

                if not radius and not radius == 0 and not location.radius:
                    radius = org.settings.get("geo_fencing_radius")

                if description:
                    location.description=description
                elif description in ("", "NA"):
                    location.description=None

                if 0 <= radius <= 5000:
                    location.radius=radius
                if latitude and isinstance(latitude, float):
                    location.latitude=latitude
                if longitude and isinstance(longitude, float):
                    location.longitude=longitude
                if department_obj:
                    location.department = department_obj

                location.save()
                updated_count += 1

            except Exception as e:
                failed_rows.append(row_count)
                failed_locations.append(
                    {
                        "name": "",
                        "reason": str(e.__class__.__name__),
                        "detailed_reason": str(e),
                    }
                )
                logger.error(e)
                logger.exception(
                    f"Add exception for {e.__class__.__name__} in LocationsUploadCSVAPI"
                )

        return Response(
            {
                "added_locations_count": created_locations,
                "failed_locations": failed_locations,
                "failed_rows": failed_rows,
                "updated_count": updated_count
            },
            status=status.HTTP_201_CREATED,
        )


class ScanSettingsAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.OrganizationSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid

        # True indicates that requirement must be met
        default_scan_settings = {
            "online": {
                "face_recognition": True,
                "geo_fencing": True,
            },
            "offline": {
                "face_recognition": True,
                "geo_fencing": True,
            },
        }

        return Response(
            org.settings.get("scan_settings", default_scan_settings),
            status=status.HTTP_200_OK,
        )

    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get('organization-uuid')
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        online_scan = request.data.get("online")
        offline_scan = request.data.get("offline")

        scan_settings = {"offline": offline_scan, "online": online_scan}
        org.settings["scan_settings"] = scan_settings
        org.save()

        return Response(org.settings, status=status.HTTP_200_OK)


class RideExpenseSettingsAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.OrganizationSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid

        return Response(
            org.settings,
            status=status.HTTP_200_OK,
        )

    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid

        geo_fencing_radius = request.data.get("geo_fencing_radius", 50)
        try:
            geo_fencing_radius = float(geo_fencing_radius)
        except (ValueError, TypeError) as e:
            logger.error(e)
            return Response(
                {"message": "Enter valid geo-fencing radius value"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.exception(
                f"Add exception for {e.__class__.__name__} in RideExpenseSettingsAPI"
            )
            return Response(
                {"message": "Enter valid geo-fencing radius value"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if geo_fencing_radius < 0:
            return Response(
                {"message": "Enter valid geo-fencing radius value"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        trip_rag_analysis = request.data.get("trip_rag_analysis", False)

        if isinstance(trip_rag_analysis, bool) is False:
            return Response(
                {"message": "Trip Rag Analysis must be a boolean."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        allow_offline_trips = request.data.get("allow_offline_trips", True)
        mandatory_approval = request.data.get("mandatory_approval", True)
        online_scan = request.data.get("online")
        offline_scan = request.data.get("offline")

        org.settings["geo_fencing_radius"] = geo_fencing_radius
        org.settings["allow_offline_trips"] = allow_offline_trips
        org.settings["mandatory_approval"] = mandatory_approval


        org.settings["trip_rag_analysis"] = trip_rag_analysis

        scan_settings = {"offline": offline_scan, "online": online_scan}
        org.settings["scan_settings"] = scan_settings

        org.save()

        return Response(org.settings, status=status.HTTP_200_OK)


class AllowedLocationsAPI(views.APIView):
    """api for get locations associated with login member's department"""

    # class for checking authentication
    permission_classes = [permissions.IsTokenAuthenticated]

    # to list api in swagger documentation
    @swagger_auto_schema(
        tags=["Locations"],
        operation_id="List all locations",
        responses={
            429: SchemaResponse.get_429(),
            500: SchemaResponse.get_500(),
        },
        manual_parameters=[
            SchemaParameters.get_page(),
            SchemaParameters.get_per_page(),
        ],
    )
    def get(self, request, *args, **kwargs):
        """api for get locations associated with login member's department"""

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        # To access member department
        member_department = member.department
        organization = member.organization

        # To filter location with null value
        locations = Location.objects.filter(department=None, organization=organization)

        # To filter location with member's department and none value , if member have department
        if member_department:
            locations = Location.objects.filter(
                Q(department=member_department) | Q(department=None)
            )
            locations = locations.filter(organization=organization)

        # To search
        search_query = request.GET.get("search")
        locations = search.search_locations(locations, search_query)

        # To export csv
        if bool(request.GET.get("export_csv")) is True:
            locations = locations.values_list("id", flat=True)
            export_request = create_export_request(member, "locations", list(locations))
            if export_request is None:
                return Response(
                    {"export_request_uuid": None}, status=status.HTTP_400_BAD_REQUEST
                )
            return Response(
                {"export_request_uuid": export_request.uuid}, status=status.HTTP_200_OK
            )

        # For pagination
        per_page = request.GET.get("per_page", 10)
        page = request.GET.get("page", 1)

        paginator = Paginator(locations, per_page)
        page_obj = paginator.get_page(page)
        serializer = serializers.LocationSerializer(
            page_obj.object_list,
            many=True,
            exclude=["department"]
        )

        # success response 
        return Response(
            {
                "data": serializer.data,
                "pagination": {"total_pages": paginator.num_pages, "page": page},
            },
            status=status.HTTP_200_OK,
        )

