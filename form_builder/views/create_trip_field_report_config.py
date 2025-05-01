from form_builder.constants import (
    CREATE_TRIP_CONFIG_FIELDS,
    CREATE_TRIP_FIELD_REPORT_FORM_CONFIG_FIELDS_VALUES,
    CREATE_TRIP_FORM_CONFIG_FIELDS_VALUES,
    CREATE_TRIP_CONFIG_VALUE_CONSTRAINT,
    CREATE_TRIP_CONFIG_FIELD_TYPES,
    CREATE_TRIP_CONFIG_DEFAULT_VALUES,
    CREATE_TRIP_CONFIG_TYPE_WITH_REQUIRED_FIELDS
)
from form_builder.models import (
    CreateTripFormConfig,
)
from rest_framework import views, status
from api import permissions
from rest_framework.response import Response
from utils import response
from utils.response import HTTP_200, HTTP_400
from django.db.models import Q
from utils import fetch_data, read_data
from trip.models import Trip
from form_builder import serializers

from rest_framework.parsers import MultiPartParser, FormParser


class CreateTripFormConfigAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.CreateTripFormConfigSerializer

    def get(self, request, *args, **kwargs):
        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        department = member.department

        if department is None:
            return HTTP_400(
                {"message": "Department not found.", "enable_field_report": False}
            )

        if department.enable_create_trip_form_config in (False, None):
            return HTTP_400(
                {
                    "message": "Field report is not enabled for the department.",
                    "enable_create_trip_form_config": False,
                }
            )

        try:
            field_report_form = CreateTripFormConfig.objects.get(
                department=department)
        except CreateTripFormConfig.DoesNotExist:
            return read_data.get_404_response("CreateTripFormConfig")

        serializer = self.serializer_class(field_report_form)

        serializer_data = {}

        for data in serializer.data:
            field_data = serializer.data[data]
            if field_data is None:
                continue
            serializer_data[data] = field_data

        return Response(serializer_data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        department_uuid = request.data.get("department")
        if not department_uuid:
            return response.HTTP_400("Department is required.")

        department = read_data.get_department(department_uuid, org)
        if department is None:
            return HTTP_400(
                {
                    "message": "Department not found.",
                    "enable_create_trip_form_config": False
                }
            )

        field_name = request.data.get("field_name")
        field_data = request.data.get("field_data")

        if not field_name:
            return response.HTTP_400("Field Name is required.")

        if isinstance(field_name, str) is False:
            return response.HTTP_400("Field Name must be string.")

        if (
            field_name not in CREATE_TRIP_CONFIG_FIELDS
        ):
            return response.HTTP_400("Field Name is not found.")

        if isinstance(field_data, dict) is False:
            return response.HTTP_400("Field Data must be json.")

        if "type" not in field_data:
            return response.HTTP_400(f"Type not found in {field_name}.")

        required_field_values = CREATE_TRIP_CONFIG_TYPE_WITH_REQUIRED_FIELDS.get(
            field_data["type"]
        )

        print(required_field_values)

        if required_field_values is None:
            return response.HTTP_400("Field type not found.")

        create_trip_config_for_dep = CreateTripFormConfig.objects.filter(
            department=department
        )
        if create_trip_config_for_dep.exists():
            create_trip_config_for_dep = create_trip_config_for_dep.first()

            model_field_data = getattr(create_trip_config_for_dep, field_name)

            if model_field_data:
                model_field_type = model_field_data.get("type")

                if model_field_type != field_data["type"]:
                    return HTTP_400("Cannot change field type. Please create another field.")

        # text:
        #     label, type, required, constraint
        # dropdown:
        #     label, type, required, options

        for field_key in required_field_values:
            if field_key not in field_data:
                return response.HTTP_400(f"{field_key} not found in {field_name}.")

            value = field_data[field_key]

            if field_key == "type" and value not in CREATE_TRIP_CONFIG_FIELD_TYPES:
                return response.HTTP_400("Type must be text/dropdown.")

            if field_key == "constraint":
                if value not in CREATE_TRIP_CONFIG_VALUE_CONSTRAINT:
                    return response.HTTP_400("constraint not found.")

            if field_key == "required" and isinstance(value, bool):
                pass
            elif not value:
                return response.HTTP_400(
                    f"Value is required for {field_key} in {field_name}."
                )

            if field_key == "options":
                if isinstance(value, list) is False:
                    return response.HTTP_400(
                        f"Options in {field_name} must be an array."
                    )

                if not value:
                    return response.HTTP_400(
                        f"Value is required for {field_key} in {field_name}."
                    )

            if field_key == "required" and isinstance(value, bool) is False:
                return response.HTTP_400(
                    f"Value must be True/False for {field_key} in {field_name}."
                )

        create_trip_config_form, config_created = CreateTripFormConfig.objects.get_or_create(
            department=department, organization=org
        )

        if config_created:
            department.enable_create_trip_form_config = True
            department.save()

        setattr(create_trip_config_form, field_name, field_data)
        create_trip_config_form.save()

        serializer = self.serializer_class(create_trip_config_form)
        return Response(serializer.data, status=status.HTTP_200_OK)


class DepartmentCreateTripFormConfigAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.FieldReportFormConfigSerializer

    def get(self, request, *args, **kwargs):
        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        department = read_data.get_department(kwargs.get("uuid"), org)

        print(department)

        if department is None:
            return HTTP_400(
                {
                    "message": "Department not found.",
                    "enable_create_trip_form_config": False,
                    "is_config": False,
                }
            )

        # if department.enable_field_report in (False, None):
        #     return HTTP_400({
        #         "message": "Field report is not enabled for the department.",
        #         "enable_field_report": False
        #     })

        try:
            create_trip_config_form = CreateTripFormConfig.objects.get(
                department=department)
        except CreateTripFormConfig.DoesNotExist:
            # return read_data.get_404_response("FieldReportFormConfig")
            return HTTP_400(
                {
                    "message": "CreateTripFormConfig not found.",
                    "is_config": False
                }
            )

        serializer = self.serializer_class(create_trip_config_form)
        return Response(serializer.data, status=status.HTTP_200_OK)





class DelCreateTripFormConfigAPI(views.APIView):
    """Del a specific field from FieldReportFormConfig"""

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.CreateTripFormConfigSerializer

    def delete(self, request, *args, **kwargs):
        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        field_name = request.data.get("field_name")
        if not field_name:
            return HTTP_400("Field name is required.")

        if field_name not in CREATE_TRIP_CONFIG_FIELDS:
            return HTTP_400("Field Name not found.")

        try:
            create_trip_field_config = CreateTripFormConfig.objects.get(
                uuid=kwargs.get("uuid")
            )
        except CreateTripFormConfig.DoesNotExist:
            return read_data.get_404_response("CreateTripFormConfig")

        department = create_trip_field_config.department
        if department.enable_create_trip_form_config is False:
            return HTTP_400(
                {
                    "message": "Field report is not enabled for the department.",
                    "enable_create_trip_form_config": False,
                }
            )

        if getattr(create_trip_field_config, field_name) is None:
            serializer = self.serializer_class(create_trip_field_config)
            return Response(serializer.data, status=status.HTTP_200_OK)

        is_field_is_the_last_field_have_value = True
        for field in CREATE_TRIP_CONFIG_FIELDS:
            field_data = getattr(create_trip_field_config, field)

            if (field_data is None) or (field == field_name):
                continue

            is_field_is_the_last_field_have_value = False
            break

        if is_field_is_the_last_field_have_value is True:
            return HTTP_400(
                "Cannot delete the field. Minimum one field required for create trip field form config."
            )

        setattr(create_trip_field_config, field_name, None)
        create_trip_field_config.save()

        serializer = self.serializer_class(create_trip_field_config)
        return Response(serializer.data, status=status.HTTP_200_OK)
