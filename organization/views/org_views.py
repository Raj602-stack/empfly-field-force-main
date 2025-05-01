from django.db.models.deletion import ProtectedError
from django.db import DataError, IntegrityError
from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from django.core.files.base import ContentFile
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from drf_yasg.openapi import Parameter, IN_QUERY, IN_BODY, Schema
from export.utils import create_export_request
from swagger.constants import (
    SchemaConstants,
    SchemaParameters,
    SchemaResponse,
    SchemaPayload,
)
from utils.response import HTTP_200, HTTP_400

from api import permissions
from organization.models import Department, Designation, ExternalConnection, Organization, OrganizationLocation, Role
from organization import serializers, search
from organization.utils import get_designation, get_department
from account.models import User
from member.models import Member, Profile
from utils import read_data, fetch_data, create_data, email_funcs

import pandas as pd
import base64
import logging

from utils.google_api import check_google_map_api_is_valid


logger = logging.getLogger(__name__)


class OrganizationAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.OrganizationSerializer

    @swagger_auto_schema(
        tags=["Organization"],
        operation_id="Get organization",
        responses={
            200: serializer_class(),
            404: SchemaResponse.get_404("organization"),
            429: SchemaResponse.get_429(),
            500: SchemaResponse.get_500(),
        },
    )
    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid

        serializer = self.serializer_class(org)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        tags=["Organization"],
        operation_id="Update organization",
        responses={
            200: serializer_class(),
            404: SchemaResponse.get_404("organization"),
            429: SchemaResponse.get_429(),
            500: SchemaResponse.get_500(),
        },
        request_body=Schema(
            properties={
                "name": Schema(
                    description="Name of the organizaton", type=openapi.TYPE_STRING
                ),
                "description": Schema(
                    description="Description of the organizaton",
                    type=openapi.TYPE_STRING,
                ),
                "logo": Schema(description="Logo of the organizaton", type="image"),
                "city": Schema(
                    description="Organizaton's city", type=openapi.TYPE_STRING
                ),
                "address": Schema(
                    description="Organizaton's address", type=openapi.TYPE_STRING
                ),
                "organization_email": Schema(
                    description="Organizaton's email", type=openapi.TYPE_STRING
                ),
            },
            type=openapi.TYPE_OBJECT,
            required=[],
        ),
    )
    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        logo = request.data.get("logo")
        if logo is not None:
            # Split the string into file format and image string
            format, imgstr = logo.split(";base64,")
            # Get file extension
            ext = format.split("/")[-1]
            # Decoding the base64 encoded text and converting it into a ContentFile
            logo = ContentFile(base64.b64decode(imgstr), name="lo." + ext)
            org.logo = logo

        name = request.data.get("name", org.name)
        description = request.data.get("description", org.description)
        location = request.data.get("location", org.location)
        organization_email = request.data.get(
            "organization_email", org.organization_email
        )
        # city = request.data.get("city", org.city)
        # address = request.data.get("address", org.address)

        if org.name != name and Organization.objects.filter(name=name).exists():
            return Response({"message": "Organization name already exists."}, status=status.HTTP_400_BAD_REQUEST)

        org.name = name
        org.description = description
        # org.city = city
        # org.address = address
        org.location = location
        org.organization_email = organization_email
        org.save()

        serializer = self.serializer_class(org)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        tags=["Organization"],
        operation_id="Delete organization",
        responses={
            200: SchemaResponse.get_200(
                {"message": "Successfully deleted Organization"}
            ),
            404: SchemaResponse.get_404("organization"),
            429: SchemaResponse.get_429(),
            500: SchemaResponse.get_500(),
        },
    )
    def delete(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        org.delete()
        return Response(
            {"message": "Successfully delete organization"}, status=status.HTTP_200_OK
        )


class AllDepartmentsAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.DepartmentSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        departments = org.departments.all()
        search_query = request.GET.get("search")
        departments = search.search_departments(departments, search_query)

        if bool(request.GET.get("export_csv")) is True:
            department_ids = departments.values_list("id", flat=True)
            export_request = create_export_request(member, "department", list(department_ids))
            if export_request is None:
                return Response({"export_request_uuid": None}, status=status.HTTP_400_BAD_REQUEST)
            return Response({"export_request_uuid": export_request.uuid}, status=status.HTTP_200_OK)

        per_page = request.GET.get("per_page", 10)
        page = request.GET.get("page", 1)
        paginator = Paginator(departments, per_page)
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
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        name = request.data.get("name")
        description = request.data.get("description")
        department_head = request.data.get("department_head", [])

        if department_head and isinstance(department_head, list):
            members = Member.objects.filter(
                uuid__in=department_head, organization=org
            )
            department_head = list(members.values_list("id", flat=True))
        else:
            department_head = []

        try:
            department = Department.objects.create(
                organization=org,
                name=name,
                description=description,
                created_by=member,
                # department_head=department_head,
            )


        except IntegrityError as e:
            return read_data.get_409_response("Department", "name")

        if isinstance(department_head, list):
            department.department_head.add(*department_head)
            department.save()

        serializer = self.serializer_class(department)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class DepartmentAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.DepartmentSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        department_uuid = self.kwargs.get("uuid")
        department = get_department(org_uuid, department_uuid)
        if department is None:
            return read_data.get_404_response("Department")

        serializer = self.serializer_class(department)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        department_uuid = self.kwargs.get("uuid")
        department = get_department(org_uuid, department_uuid)
        if department is None:
            return read_data.get_404_response("Department")

        name = request.data.get("name", department.name)
        description = request.data.get("description", department.description)
        is_active = request.data.get("is_active", department.is_active)

        if isinstance(is_active, bool) is False:
            return Response(
                {"message": "Status should be true/false"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        department_head = request.data.get("department_head")


        if department_head and isinstance(department_head, list):
            members = Member.objects.filter(
                uuid__in=department_head, organization=org
            )
            department_head = list(members.values_list("id", flat=True))
        else:
            department_head = []

        department.name = name
        department.description = description
        department.is_active = is_active

        department.department_head.clear()
        department.department_head.add(*department_head)

        department.save()

        serializer = self.serializer_class(department)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        department_uuid = self.kwargs.get("uuid")
        department = get_department(org_uuid, department_uuid)
        if department is None:
            return read_data.get_404_response("Department")

        try:
            department.delete()
        except ProtectedError as e:
            logger.error(e)
            return Response(
                {"message": "Department is assigned to a member"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"message": "Successfully deleted department"}, status=status.HTTP_200_OK
        )


    def patch(self, request, *args, **kwargs):
        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        department_uuid = self.kwargs.get("uuid")
        department = get_department(org_uuid, department_uuid)
        if department is None:
            return read_data.get_404_response("Department")

        department.enable_field_report = {
            True: False,
            False: True
        }.get(department.enable_field_report, False)
        department.save()


        serializer = self.serializer_class(department)
        return Response(serializer.data, status=status.HTTP_200_OK)

class DepartmentUploadCSVAPI(views.APIView):

    permission_classes = [IsAuthenticated]
    serializer_class = None

    def get(self, request, *args, **kwargs):

        response = create_data.create_csv_response("sample_locations")
        writer = create_data.create_csv_writer(response)

        # Add title.
        writer.writerow(["name", "description", "department_head"])
        # Add sample data to csv
        writer.writerow(["Engineering", "Engineering Desc", "user1@gmail.com"])
        writer.writerow(["HR", "HR Desc", ""])

        return response

    def post(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        csv_file = request.data.get("csv_file")

        df = create_data.create_pandas_dataframe(csv_file)

        added_locations_count = 0
        failed_locations = []

        for row in df.values:

            try:
                name = row[0]
            except Exception as e:
                logger.error(e)
                logger.exception(
                    f"Add exception for {e.__class__.__name__} in DepartmentUploadCSVAPI"
                )
                failed_locations.append(
                    {
                        "name": "",
                        "reason": str(e.__class__.__name__),
                        "detailed_reason": str(e),
                    }
                )
                continue

            try:
                if row[2]:
                    dept_head = Member.objects.filter(
                        Q(organization=org) & Q(email=row[2])
                    ).first()
                else:
                    dept_head = None
            except Exception as e:
                logger.error(e)
                logger.exception(
                    f"Add exception for {e.__class__.__name__} in DepartmentUploadCSVAPI"
                )
                dept_head = None

            try:
                Department.objects.create(
                    organization=org,
                    name=name,
                    description=row[1],
                    department_head=dept_head,
                )
                added_locations_count += 1
            except Exception as e:
                failed_locations.append(
                    {
                        "name": name,
                        "reason": str(e.__class__.__name__),
                        "detailed_reason": str(e),
                    }
                )
                logger.error(e)
                logger.exception(
                    f"Add exception for {e.__class__.__name__} in DepartmentUploadCSVAPI"
                )

        return Response(
            {
                "added_locations_count": added_locations_count,
                "failed_locations": failed_locations,
            },
            status=status.HTTP_201_CREATED,
        )


class AllDesignationsAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.DesignationSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user) # get organization belongs to the user
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        designations = org.designations.all()
        search_query = request.GET.get("search")
        designations = search.search_destinations(designations, search_query)

        per_page = request.GET.get("per_page", 10)
        page = request.GET.get("page", 1)
        paginator = Paginator(designations, per_page)
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
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        name = request.data.get("name")
        description = request.data.get("description")

        try:
            designation = Designation.objects.create(
                organization=org,
                name=name,
                description=description,
                created_by=member,
            )
        except IntegrityError as e:
            return read_data.get_409_response("Designation", "name")

        serializer = self.serializer_class(designation)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class DesignationAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.DesignationSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        designation_uuid = self.kwargs.get("uuid")
        designation = get_designation(org_uuid, designation_uuid)
        if designation is None:
            return read_data.get_404_response("Designation")

        serializer = self.serializer_class(designation)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        designation_uuid = self.kwargs.get("uuid")
        designation = get_designation(org_uuid, designation_uuid)
        if designation is None:
            return read_data.get_404_response("Designation")

        name = request.data.get("name", designation.name)
        description = request.data.get("description", designation.description)
        is_active = request.data.get("is_active", designation.is_active)

        if isinstance(is_active, bool) is False:
            return Response(
                {"message": "Status should be true/false"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        designation.name = name
        designation.description = description
        designation.is_active = is_active

        designation.save()

        serializer = self.serializer_class(designation)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        designation_uuid = self.kwargs.get("uuid")
        designation = get_designation(org_uuid, designation_uuid)
        if designation is None:
            return read_data.get_404_response("Designation")

        try:
            designation.delete()
        except ProtectedError as e:
            logger.error(e)
            return Response(
                {"message": "Designation is assigned to a member"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"message": "Successfully deleted designation"}, status=status.HTTP_200_OK
        )


class AllOrganizationLocationsAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.OrganizationLocationSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")

        # get data of Organization model
        org = fetch_data.get_organization2(request.user) 
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        # get all the data related from OrganizationLocation model
        locations = org.organization_locations.all()
        search_query = request.GET.get("search")
        locations = search.search_locations(locations, search_query)

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

    def post(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        requesting_member = fetch_data.get_member(request.user, org_uuid)

        if fetch_data.is_admin(requesting_member) is False:
            return read_data.get_403_response()

        name = request.data.get("name")
        description = request.data.get("description")
        # latitude = request.data.get("latitude")
        # longitude = request.data.get("longitude")
        # email = request.data.get("email")
        # phone = request.data.get("phone")

        try:
            location = OrganizationLocation.objects.create(
                organization=org,
                name=name,
                description=description,
                # latitude=latitude,
                # longitude=longitude,
                # email=email,
                # phone=phone,
            )
        except IntegrityError as e:
            logger.error(e)
            return Response(
                {"message": "Organization Location with name already exists"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.serializer_class(location)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class OrganizationLocationAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.OrganizationLocationSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")

        # return organization attached with the user model -> Organization
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        location_uuid = self.kwargs.get("uuid")  # --------> what is the use of this. how this kwrgs work !!!!!!
        location = fetch_data.get_org_location(location_uuid) # --------> method not found !!!!!
        if location is None:
            return read_data.get_404_response("Organization Location")

        serializer = self.serializer_class(location)
        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")

        # get organization using member member model
        # returning data of Organization model
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        location_uuid = self.kwargs.get("uuid")
        try:
            location = org.organization_locations.get(uuid=location_uuid)
        except (OrganizationLocation.DoesNotExist, ValidationError) as e:
            return read_data.get_404_response("Location")


        name = request.data.get("name", location.name)
        description = request.data.get("description", location.description)
        is_active = request.data.get("is_active", location.is_active)
        # latitude = request.data.get("latitude", location.latitude)
        # longitude = request.data.get("longitude", location.longitude)
        # email = request.data.get("email", location.email)
        # phone = request.data.get("phone", location.phone)
        if isinstance(is_active, bool) is False:
            return Response(
                {"message": "Status should be true/false"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        location.name = name
        location.description = description
        location.is_active=is_active
        # location.latitude = latitude
        # location.longitude = longitude
        # location.email = email
        # location.phone = phone

        try:
            location.save()
        except IntegrityError as e:
            logger.error(e)
            return Response(
                {"message": "Organization Location with name already exists"},
                status=status.HTTP_409_CONFLICT,
            )

        serializer = self.serializer_class(location)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    def delete(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        location_uuid = self.kwargs.get("uuid")
        try:
            location = org.organization_locations.get(uuid=location_uuid)
        except (OrganizationLocation.DoesNotExist, ValidationError) as e:
            return read_data.get_404_response("Organization Location")

        location.delete()

        return Response(
            {"message": "Successfully deleted Organization Location"},
            status=status.HTTP_200_OK,
        )


class AllRolesAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.RoleSerializer

    @swagger_auto_schema(
        tags=["Roles"],
        operation_id="List all roles",
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

        roles = Role.objects.all()
        per_page = request.GET.get("per_page", 10)
        page = request.GET.get("page", 1)

        paginator = Paginator(roles, per_page)
        page_obj = paginator.get_page(page)
        serializer = self.serializer_class(page_obj.object_list, many=True)

        return Response(
            {
                "data": serializer.data,
                "pagination": {"total_pages": paginator.num_pages, "page": page},
            },
            status=status.HTTP_200_OK,
        )


class RoleAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.RoleSerializer

    @swagger_auto_schema(
        tags=["Role"],
        operation_id="Get a role",
        responses={
            200: serializer_class(),
            404: SchemaResponse.get_404("role"),
            429: SchemaResponse.get_429(),
            500: SchemaResponse.get_500(),
        },
        manual_parameters=[SchemaParameters.get_uuid("role")],
    )
    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        role_uuid = self.kwargs.get("uuid")
        try:
            role = Role.objects.get(uuid=role_uuid)
        except (Role.DoesNotExist, ValidationError) as e:
            return read_data.get_404_response("Role")

        serializer = self.serializer_class(role)
        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )


class ExternalConnectionAPIView(views.APIView):
    """
    Retrieve, update or delete a external connection instance.
    """

    permission_classes = [permissions.IsTokenAuthenticated, permissions.IsAdmin]
    serializer_class = serializers.ExternalConnectionSerializer

   
    def get_object(self, request):
        try:
            organization = fetch_data.get_organization2(request.user)
            externalConnection = ExternalConnection.objects.filter(organization=organization)
            if externalConnection.exists():
                return externalConnection.first()
            else:
                return None
        except ExternalConnection.DoesNotExist:
            # raise Http404
            return None


    def get(self, request, format=None):
        externalConnection = self.get_object(request)
        if not externalConnection:
            return Response({"message": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = self.serializer_class(externalConnection, exclude=["gcp_api_key"])
        return Response(serializer.data)


    def post(self, request, format=None):
        """ While creating trip scan we can search location from google.
            Add Google API for that.
        """
        externalConnection = self.get_object(request)
        # payload
        datas = request.data
        organization = fetch_data.get_organization2(request.user)
        # set organization
        datas["organization"] = organization.id
        # check payload has gcp_api_key key
        # if exists
        if datas.get("gcp_api_key"):
            response = check_google_map_api_is_valid(datas["gcp_api_key"])
            if response:
                json_response = response.json()
                error_message = json_response.get("error_message", None)
                if error_message:
                    return Response({"message": error_message}, status=status.HTTP_403_FORBIDDEN)

            datas["short_gcp_api_key"] = read_data.convertGoogleAPIKeyShort(datas["gcp_api_key"])
            # encrypt api key and assign to gcp_api_key
            datas["gcp_api_key"] = read_data.encrypt_text(datas["gcp_api_key"])
        # check request user has member objects
        if request.user.members.exists():
            # assign requested member in updated_by
            datas["updated_by"] = request.user.members.first().id
        serializer = self.serializer_class(externalConnection, data=datas)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    
    def patch(self, request, format=None):
        externalConnection = self.get_object(request)
        serializer = self.serializer_class(externalConnection, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


    def delete(self, request, format=None):
        externalConnection = self.get_object(request)
        if externalConnection:
            externalConnection.delete()
            return Response({"message": "Successfully deleted"},status=status.HTTP_204_NO_CONTENT)
        return Response({"message": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        



class IsActiveExternalConnectionAPIView(views.APIView):
    """
    Retrieve, update or delete a external connection instance.
    """

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.ExternalConnectionSerializer


    def get(self, request, *args, **kwargs):
        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        if not member:
            return HTTP_400(
                "Member not found."
            )
        
        try:
            ext_connection = ExternalConnection.objects.get(organization=org)
        except ExternalConnection.DoesNotExist:
            return HTTP_400(
                "ExternalConnection not found."
            )
        except ExternalConnection.MultipleObjectsReturned:
            return HTTP_400(
                "ExternalConnection not found."
            )

        is_gcp_key_active = ext_connection.gcp_api_key and ext_connection.status

        return HTTP_200({"is_gcp_key_active": is_gcp_key_active})



class DepartmentPatchAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.DepartmentSerializer

    def patch(self, request, *args, **kwargs):
        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        department_uuid = self.kwargs.get("uuid")
        department = get_department(org_uuid, department_uuid)
        if department is None:
            return read_data.get_404_response("Department")
        print(department.enable_create_trip_form_config)
        department.enable_create_trip_form_config = {
            True: False,
            False: True
        }.get(department.enable_create_trip_form_config, False)
        department.save()


        serializer = self.serializer_class(department)
        return Response(serializer.data, status=status.HTTP_200_OK)



class DepartmentAdminReportPatchAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.DepartmentSerializer

    def patch(self, request, *args, **kwargs):
        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        department_uuid = self.kwargs.get("uuid")
        department = get_department(org_uuid, department_uuid)
        if department is None:
            return read_data.get_404_response("Department")
        print(department.enable_admin_report_form_config)
        department.enable_admin_report_form_config = {
            True: False,
            False: True
        }.get(department.enable_admin_report_form_config, False)
        department.save()


        serializer = self.serializer_class(department)
        return Response(serializer.data, status=status.HTTP_200_OK)

class AllDepartmentsV2API(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.DepartmentSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        departments = Department.objects.filter(organization=org)
        if fetch_data.is_admin(member) is False:
            departments = departments.filter(department_head=member)

        search_query = request.GET.get("search")
        departments = search.search_departments(departments, search_query)

        per_page = request.GET.get("per_page", 10)
        page = request.GET.get("page", 1)
        paginator = Paginator(departments, per_page)
        page_obj = paginator.get_page(page)

        serializer = self.serializer_class(page_obj.object_list, many=True, fields=["name", "uuid"])
        return Response(
            {
                "data": serializer.data,
                "pagination": {"total_pages": paginator.num_pages, "page": page},
            },
            status=status.HTTP_200_OK,
        )
