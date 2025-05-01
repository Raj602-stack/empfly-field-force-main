from form_builder.constants import (
    FIELD_REPORT_FORM_CONFIG_FIELDS,
    FIELD_REPORT_FORM_CONFIG_FIELDS_VALUES,
    FIELD_CONFIG_VALUE_CONSTRAINT,
    FIELD_CONFIG_TYPE_WITH_REQUIRED_FIELDS,
    validate_max_file_count,
    validate_max_file_size,
    FIELD_CONFIG_FIELD_TYPES,
)
from form_builder.models import FieldReportFormConfig
from rest_framework import views, status
from api import permissions
from rest_framework.response import Response
from utils import response
from utils.response import HTTP_200, HTTP_400
from django.db.models import Q
from utils import fetch_data, read_data
from form_builder import serializers
from rest_framework.parsers import MultiPartParser, FormParser


class FieldReportFormConfigAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.FieldReportFormConfigSerializer

    def get(self, request, *args, **kwargs):
        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        department = member.department

        if department is None:
            return HTTP_400(
                {"message": "Department not found.", "enable_field_report": False}
            )

        if department.enable_field_report in (False, None):
            return HTTP_400(
                {
                    "message": "Field report is not enabled for the department.",
                    "enable_field_report": False,
                }
            )

        try:
            field_report_form = FieldReportFormConfig.objects.get(department=department)
        except FieldReportFormConfig.DoesNotExist:
            return read_data.get_404_response("FieldReportFormConfig")

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
                {"message": "Department not found.", "enable_field_report": False}
            )

        field_name = request.data.get("field_name")
        field_data = request.data.get("field_data")

        if not field_name:
            return response.HTTP_400("Field Name is required.")

        if isinstance(field_name, str) is False:
            return response.HTTP_400("Field Name must be string.")

        if (
            field_name != "attachment"
            and field_name not in FIELD_REPORT_FORM_CONFIG_FIELDS
        ):
            return response.HTTP_400("Field Name is not found.")

        if isinstance(field_data, dict) is False:
            return response.HTTP_400("Field Data must be json.")

        if field_name != "attachment" and "type" not in field_data:
            return response.HTTP_400(f"Type not found in {field_name}.")

        if field_name == "attachment":
            print("@@@@@@@@@")
            required_field_values = FIELD_CONFIG_TYPE_WITH_REQUIRED_FIELDS.get(
                "attachment"
            )
        else:
            required_field_values = FIELD_CONFIG_TYPE_WITH_REQUIRED_FIELDS.get(
                field_data["type"]
            )

            field_report_for_dep = FieldReportFormConfig.objects.filter(department=department)
            if field_report_for_dep.exists():
                field_report_for_dep = field_report_for_dep.first()

                model_field_data = getattr(field_report_for_dep, field_name)

                if model_field_data:
                    model_field_type = model_field_data.get("type")

                    if model_field_type != field_data["type"]:
                        return HTTP_400("Cannot change field type. Please create another field.")

        if required_field_values is None:
            return response.HTTP_400("Field type not found.")

        # text:
        #     label, type, required, constraint
        # dropdown:
        #     label, type, required, options

        for field_key in required_field_values:
            if field_key not in field_data:
                return response.HTTP_400(f"{field_key} not found in {field_name}.")

            value = field_data[field_key]

            if field_key == "type" and value not in FIELD_CONFIG_FIELD_TYPES:
                return response.HTTP_400("Type must be text/dropdown.")

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

            elif field_name == "attachment":
                # if field_key == "max_file_size":
                #     res, is_res = validate_max_file_size(value)
                #     if is_res is True:
                #         return res
                if field_key == "max_file_count":
                    res, is_res = validate_max_file_count(value)
                    if is_res is True:
                        return res
            else:
                if (
                    field_key == "constraint"
                    and value not in FIELD_CONFIG_VALUE_CONSTRAINT
                ):
                    return response.HTTP_400(
                        f"Value must be is_email/is_number/all for {field_key} in {field_name}."
                    )

            if field_key == "required" and isinstance(value, bool) is False:
                return response.HTTP_400(
                    f"Value must be True/False for {field_key} in {field_name}."
                )

        field_report_form, config_created = FieldReportFormConfig.objects.get_or_create(
            department=department, organization=org
        )

        if config_created:
            department.enable_field_report = True
            department.save()

        setattr(field_report_form, field_name, field_data)
        field_report_form.save()

        serializer = self.serializer_class(field_report_form)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # def put(self, request, *args, **kwargs):
    #     org_uuid = request.headers.get("organization-uuid")
    #     org = fetch_data.get_organization(request.user, org_uuid)
    #     member = fetch_data.get_member(request.user, org.uuid)

    #     if fetch_data.is_admin(member) is False:
    #         return read_data.get_403_response()

    #     department_uuid = kwargs.get("kwargs")
    #     department = read_data.get_department(department_uuid, org)

    #     try:
    #         field_report_form = FieldReportFormConfig.objects.get(department=department)
    #     except FieldReportFormConfig.DoesNotExist:
    #         return read_data.get_404_response("FieldReportFormConfig")

    #     field_report_form.delete()
    #     # return Response("Successfully deleted FieldReportFormConfig.", status=status.HTTP_200_OK)


class AllFieldReportFormConfigAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.FieldReportFormConfigSerializer

    def get(self, request, *args, **kwargs):
        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        # if department.enable_field_report is False:
        #     return HTTP_400("Field report is not enabled for the organization.")
        try:
            field_report_form = FieldReportFormConfig.objects.get(
                uuid=kwargs.get("uuid")
            )
        except FieldReportFormConfig.DoesNotExist:
            return read_data.get_404_response("FieldReportFormConfig")

        serializer = self.serializer_class(field_report_form)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # def put(self, request, *args, **kwargs):
    #     org_uuid = request.headers.get("organization-uuid")
    #     org = fetch_data.get_organization(request.user, org_uuid)
    #     member = fetch_data.get_member(request.user, org.uuid)

    #     if fetch_data.is_admin(member) is False:
    #         return read_data.get_403_response()

    #     try:
    #         field_report_form = FieldReportFormConfig.objects.get(uuid=kwargs.get("uuid"))
    #     except FieldReportFormConfig.DoesNotExist:
    #         return read_data.get_404_response("FieldReportFormConfig")

    #     department = field_report_form.department
    #     if department.enable_field_report is False:
    #         return HTTP_400({
    #             "message": "Field report is not enabled for the department.",
    #             "enable_field_report": False
    #         })

    #     req_data = request.data

    #     actual_field_data = {}

    #     for field_name in FIELD_REPORT_FORM_CONFIG_FIELDS:
    #         if field_name not in req_data:
    #             continue

    #         field_data = req_data[field_name]

    #         print(field_data)

    #         if isinstance(field_data, dict) is False:
    #             return response.HTTP_400("Field must ba a json field.")

    #         for key in self.key_in_field:
    #             if key not in field_data:
    #                 return response.HTTP_400(f"{key} not found in {field_name}.")

    #             key_value = field_data[key]

    #             if key == "required" and isinstance(key_value, bool):
    #                 pass
    #             elif not key_value:
    #                 return response.HTTP_400(f"Value is required for {key} in {field_name}.")

    #             if key == "constraint" and key_value not in  ("is_number", "is_email"):
    #                 return response.HTTP_400(f"Value must be is_email/is_number for {key} in {field_name}.")

    #             if key == "required" and  isinstance(key_value, bool) is False:
    #                 return response.HTTP_400(f"Value must be True/False for {key} in {field_name}.")

    #         setattr(field_report_form, field_name, field_data)
    #         actual_field_data[field_name] = field_data

    #     if not actual_field_data:
    #         return response.HTTP_400("Minimum one field required for FieldReportFormConfig.")

    #     print(actual_field_data)
    #     print(field_report_form)

    #     field_report_form.save()

    #     serializer = self.serializer_class(field_report_form)
    #     return Response(serializer.data, status=status.HTTP_200_OK)


class DelFieldReportFormConfigAPI(views.APIView):
    """Del a specific field from FieldReportFormConfig"""

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.FieldReportFormConfigSerializer

    def delete(self, request, *args, **kwargs):
        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        field_name = request.data.get("field_name")
        if not field_name:
            return HTTP_400("Field name is required.")

        if field_name not in FIELD_REPORT_FORM_CONFIG_FIELDS + ["attachment"]:
            return HTTP_400("Field Name not found.")

        try:
            field_report_form = FieldReportFormConfig.objects.get(
                uuid=kwargs.get("uuid")
            )
        except FieldReportFormConfig.DoesNotExist:
            return read_data.get_404_response("FieldReportFormConfig")

        department = field_report_form.department
        if department.enable_field_report is False:
            return HTTP_400(
                {
                    "message": "Field report is not enabled for the department.",
                    "enable_field_report": False,
                }
            )

        if getattr(field_report_form, field_name) is None:
            serializer = self.serializer_class(field_report_form)
            return Response(serializer.data, status=status.HTTP_200_OK)

        is_field_is_the_last_field_have_value = True
        for field in FIELD_REPORT_FORM_CONFIG_FIELDS + ["attachment"]:
            field_data = getattr(field_report_form, field)

            if (field_data is None) or (field == field_name):
                continue

            is_field_is_the_last_field_have_value = False
            break

        if is_field_is_the_last_field_have_value is True:
            return HTTP_400(
                "Cannot delete the field. Minimum one field required for field form report."
            )

        setattr(field_report_form, field_name, None)
        field_report_form.save()

        serializer = self.serializer_class(field_report_form)
        return Response(serializer.data, status=status.HTTP_200_OK)


class DepartmentFieldReportFormConfigAPI(views.APIView):

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
                    "enable_field_report": False,
                    "is_config": False,
                }
            )

        # if department.enable_field_report in (False, None):
        #     return HTTP_400({
        #         "message": "Field report is not enabled for the department.",
        #         "enable_field_report": False
        #     })

        try:
            field_report_form = FieldReportFormConfig.objects.get(department=department)
        except FieldReportFormConfig.DoesNotExist:
            # return read_data.get_404_response("FieldReportFormConfig")
            return HTTP_400(
                {"message": "FieldReportFormConfig not found.", "is_config": False}
            )

        serializer = self.serializer_class(field_report_form)
        return Response(serializer.data, status=status.HTTP_200_OK)
