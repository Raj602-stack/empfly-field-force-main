from form_builder.constants import (
    ADMIN_REPORT_CONFIG_FIELDS,
    ADMIN_REPORT_FIELD_REPORT_FORM_CONFIG_FIELDS_VALUES,
    ADMIN_REPORT_FORM_CONFIG_FIELDS_VALUES,
    ADMIN_REPORT_CONFIG_VALUE_CONSTRAINT,
    ADMIN_REPORT_CONFIG_FIELD_TYPES,
    ADMIN_REPORT_CONFIG_DEFAULT_VALUES,
    ADMIN_REPORT_CONFIG_TYPE_WITH_REQUIRED_FIELDS,
    EMAIL_REGEX
)
from form_builder.models import (
    AdminReportFormConfig,
)
from django.core.exceptions import ValidationError
from form_builder.utils import get_admin_report_config_field
from form_builder.models import AdminReportFormSubmissions
from rest_framework import views, status
from api import permissions
from rest_framework.response import Response
from utils import response
from utils.response import HTTP_200, HTTP_400
from django.db.models import Q
from utils import fetch_data, read_data
from trip.models import Trip
from form_builder import serializers
from django.core.validators import URLValidator

from rest_framework.parsers import MultiPartParser, FormParser

from trip.utils import (
    create_trip_err_msg,
    get_my_trip,
    get_trip,
    has_access_to_trip,
    extract_coordinates,
    extract_coordinates_as_str,
    calculate_distance,
    round_off_value,
    save_scan_err,
)
from form_builder.models import CreateTripFormConfig

class AdminReportFormConfigAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.AdminReportFormConfigSerializer

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
        print("@@@@@@@@@@@@2")

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
                    "enable_admin_report_form_config": False
                }
            )

        field_name = request.data.get("field_name")
        field_data = request.data.get("field_data")

        if not field_name:
            return response.HTTP_400("Field Name is required.")

        if isinstance(field_name, str) is False:
            return response.HTTP_400("Field Name must be string.")

        if (
            field_name not in ADMIN_REPORT_CONFIG_FIELDS
        ):
            return response.HTTP_400("Field Name is not found.")

        if isinstance(field_data, dict) is False:
            return response.HTTP_400("Field Data must be json.")

        if "type" not in field_data:
            return response.HTTP_400(f"Type not found in {field_name}.")

        required_field_values = ADMIN_REPORT_CONFIG_TYPE_WITH_REQUIRED_FIELDS.get(
            field_data["type"]
        )

        print(required_field_values)

        if required_field_values is None:
            return response.HTTP_400("Field type not found.")

        admin_report_config_for_dep = AdminReportFormConfig.objects.filter(
            department=department
        )
        if admin_report_config_for_dep.exists():
            admin_report_config_for_dep = admin_report_config_for_dep.first()

            model_field_data = getattr(admin_report_config_for_dep, field_name)

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

            if field_key == "type" and value not in ADMIN_REPORT_CONFIG_FIELD_TYPES:
                return response.HTTP_400("Type must be text/dropdown.")

            if field_key == "constraint":
                if value not in ADMIN_REPORT_CONFIG_VALUE_CONSTRAINT:
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

        admin_report_config_form, config_created = AdminReportFormConfig.objects.get_or_create(
            department=department, organization=org
        )

        if config_created:
            department.enable_admin_report_form_config = True
            department.save()

        setattr(admin_report_config_form, field_name, field_data)
        admin_report_config_form.save()

        serializer = self.serializer_class(admin_report_config_form)
        return Response(serializer.data, status=status.HTTP_200_OK)





class CreateAdminReportFormConfigAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.AdminReportFormSubmissionsSerializer

    
    def post(self, request, *args, **kwargs):
        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)
        print("@@@@@@@@@@@@2")

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()
        
        if not request.data.get("trip"):
            return HTTP_400("Trip not found")

        trip = get_trip(org.uuid, request.data.get("trip"))
        if not trip:
            return HTTP_400("Trip not found")

        trip_member = trip.assigned_to
        department = trip_member.department

        if not department:
            return HTTP_400(
                {
                    "message": "Department not found.",
                    "enable_admin_report_form_config": False
                }
            )

        if department.enable_admin_report_form_config is False:
            return HTTP_400(
                {
                    "message": "Admin report for config is not enabled for the department.",
                    "enable_admin_report_form_config": False,
                }
            )

        if trip.status not in ("field_report_submitted", "ended"):
            return HTTP_400("Trip status must be ended/field_report_submitted.")

        if trip.status == "ended":
            if department.enable_field_report is True:
                return HTTP_400("Cannot create admin report. Field Report is enabled for member department.")

        if AdminReportFormSubmissions.objects.filter(
            trip=trip
        ).exists():
            return HTTP_400(
                {
                    "message": "Trip already have AdminReportFormSubmissions.",
                }
            )

        try:
            admin_report_config_field = AdminReportFormConfig.objects.get(department=department)
        except AdminReportFormConfig.DoesNotExist:
            return read_data.get_404_response("AdminFieldReportConfig")


        req_data = request.data
        validated_data = {}

        for fields in ADMIN_REPORT_CONFIG_FIELDS:
            addon_data = {}
            field_data = getattr(admin_report_config_field, fields)

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
                            field_input_value = int(field_input_value)
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
                        except ValidationError as err:
                            # URL is not valid
                            print(err)
                            return HTTP_400(
                                f"Please enter a valid URL for {field_label}."
                            )
                else:
                    print("Type not found.")

            validated_data[fields] = {"label": field_label, "value": field_input_value, **addon_data}

        validated_data["admin_report_form"] = admin_report_config_field
        validated_data["department"] = department
        validated_data["organization"] = org
        validated_data["trip"] = trip

        admin_report = AdminReportFormSubmissions.objects.create(
            **validated_data
        )

        serializer = self.serializer_class(admin_report)
        return Response(serializer.data, status=status.HTTP_200_OK)



class DepartmentAdminReportFormConfigAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.AdminReportFormConfigSerializer

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
                    "enable_admin_report_form_config": False,
                    "is_config": False,
                }
            )

        try:
            admin_report_config_form = AdminReportFormConfig.objects.get(
                department=department)
        except AdminReportFormConfig.DoesNotExist:
            # return read_data.get_404_response("FieldReportFormConfig")
            return HTTP_400(
                {
                    "message": "AdminReportFormConfig not found.",
                    "enable_admin_report_form_config": False
                }
            )

        serializer = self.serializer_class(admin_report_config_form)
        return Response(serializer.data, status=status.HTTP_200_OK)

class DelAdminReportFormConfigAPI(views.APIView):
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

        if field_name not in ADMIN_REPORT_CONFIG_FIELDS:
            return HTTP_400("Field Name not found.")

        try:
            admin_report_field_config = AdminReportFormConfig.objects.get(
                uuid=kwargs.get("uuid")
            )
        except AdminReportFormConfig.DoesNotExist:
            return read_data.get_404_response("AdminReportFormConfig")

        department = admin_report_field_config.department
        if department.enable_admin_report_form_config is False:
            return HTTP_400(
                {
                    "message": "Field report is not enabled for the department.",
                    "enable_admin_report_form_config": False,
                }
            )

        if getattr(admin_report_field_config, field_name) is None:
            serializer = self.serializer_class(admin_report_field_config)
            return Response(serializer.data, status=status.HTTP_200_OK)

        is_field_is_the_last_field_have_value = True
        for field in ADMIN_REPORT_CONFIG_FIELDS:
            field_data = getattr(admin_report_field_config, field)

            if (field_data is None) or (field == field_name):
                continue

            is_field_is_the_last_field_have_value = False
            break

        if is_field_is_the_last_field_have_value is True:
            return HTTP_400(
                "Cannot delete the field. Minimum one field required for admin report form config."
            )

        setattr(admin_report_field_config, field_name, None)
        admin_report_field_config.save()

        serializer = self.serializer_class(admin_report_field_config)
        return Response(serializer.data, status=status.HTTP_200_OK)
