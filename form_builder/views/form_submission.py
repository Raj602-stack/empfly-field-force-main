from form_builder.constants import (
    FIELD_REPORT_FILE_ALLOWED_EXT_IN_STR,
    FIELD_REPORT_FORM_CONFIG_FIELDS,
)
from form_builder.models import (
    FieldReportFormConfig,
    FieldReportFormSubmissions,
    FieldReportFile,
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
import re

from rest_framework.parsers import MultiPartParser, FormParser

class FieldReportFormSubmissionsAPI(views.APIView):
    """Del a specific field from FieldReportFormConfig"""

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.FieldReportFormSubmissionsSerializer
    parser_classes = (MultiPartParser, FormParser, )

    EMAIL_REGEX = re.compile(r"[^@]+@[^@]+\.[^@]+")

    def post(self, request, *args, **kwargs):
        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        trip_uuid = request.data.get("trip")
        department = member.department

        if not trip_uuid:
            return HTTP_400("Trip uuid is required.")

        if department is None:
            return HTTP_400(
                {"message": "Department not found.", "enable_field_report": False}
            )

        if department.enable_field_report is False:
            return HTTP_400(
                {
                    "message": "Field report is not enabled for the department.",
                    "enable_field_report": False,
                }
            )

        try:
            field_report_builder = FieldReportFormConfig.objects.get(
                department=department
            )
        except FieldReportFormConfig.DoesNotExist:
            return read_data.get_404_response("FieldReportFormConfig")

        try:
            trip = Trip.objects.get(uuid=trip_uuid, organization=org)
        except Trip.DoesNotExist:
            return read_data.get_404_response("Trip")

        if trip.assigned_to != member:
            return HTTP_400("You dont have permission to perform this action.")

        try:
            FieldReportFormSubmissions.objects.get(trip=trip)
            return HTTP_400("Trip already have field report form submissions.")
        except FieldReportFormSubmissions.DoesNotExist:
            pass

        if trip.status != "ended":
            return HTTP_400("Trip not ended.")

        req_data = request.data

        # Check field data.
        validated_data = {}

        for fields in FIELD_REPORT_FORM_CONFIG_FIELDS:
            field_data = getattr(field_report_builder, fields)

            if field_data is None:
                # Not configured this field.
                continue
        
            field_is_required: bool = field_data.get("required")
            field_label: str = field_data.get("label")
            field_constraint: str = field_data.get("constraint")
            field_is_required: bool = field_data.get("required")
            field_type: str = field_data.get("type")

            if fields not in req_data:
                
                if field_is_required is True:
                    # field configured in form builder not found in req.
                    return HTTP_400(f"{fields} Not found.")
                elif field_is_required is False:
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

                        if not self.EMAIL_REGEX.match(field_input_value):
                            return HTTP_400(
                                f"Please enter a valid email for {field_label}."
                            )

                # elif field_constraint == "is_text":
                #     if isinstance(field_input_value, str) is False:
                #         return HTTP_400(f"{field_label} value must be a string.")

                else:
                    print("Type not found.")

            validated_data[fields] = {"label": field_label, "value": field_input_value}

        validated_data["field_report_form"] = field_report_builder
        validated_data["organization"] = org
        validated_data["department"] = department
        validated_data["trip"] = trip

        print(validated_data)

        # Validate attachments

        # {
        #   "type": "text",
        #   "label": "sample",
        #   "options": ["one"],
        #   "required": true,
        #   "constraint": "all",
        #   "max_file_size": 50,
        #   "max_file_count": 20
        # }

        attachment_data = field_report_builder.attachment

        if attachment_data is None:
            attachment_data = {}

        attachment_label: str = attachment_data.get("label")
        attachment_is_required: bool = attachment_data.get("required")
        # attachment_max_file_size: int = attachment_data.get("max_file_size")
        attachment_max_file_count: int = attachment_data.get("max_file_count")

        # If attachment is none
        # Validate with user entered file size.

        print(req_data)

        attachment_key_name: str = req_data.get("attachment_key_name", "")
        print(attachment_key_name, type(attachment_key_name))

        if attachment_key_name:
            attachment_name: list = attachment_key_name.split(", ")
        else:
            attachment_name: list = []

        print(attachment_key_name)
        print("attachment_key_name")
        print(attachment_name)
        print("attachment_name")

        if not attachment_data:
            pass
        elif attachment_is_required is True:
            if not attachment_key_name:
                return HTTP_400("Attachment names is required.")

            if not attachment_name:
                return HTTP_400("Attachment have not names.")

            if len(attachment_name) == 0:
                return HTTP_400(
                    "Minimum One file required."
                )
        else:
            if attachment_key_name and len(attachment_name) > attachment_max_file_count:
                return HTTP_400(
                    f"Attachment file count cannot be greater than {attachment_max_file_count}."
                )

        validated_files = []

        if not attachment_data:
            pass
        elif attachment_key_name:
            for attachment_file_name in attachment_name:
                if attachment_key_name and attachment_file_name not in req_data:
                    return HTTP_400(
                        f"Attachment file name {attachment_file_name} data not found."
                    )

                attached_file = req_data[attachment_file_name]

                print("@@@@@@@@@@@@@@@@@@")
                print(attached_file)
                print(request.FILES)
                print(type(attached_file))
                print("@@@@@@@@@@@@@@@@@@")

                field_report_file_serializers = (
                    serializers.FieldReportFileValidationSerializer(data={
                        "file": attached_file
                    })
                )

                if not field_report_file_serializers.is_valid():
                    return HTTP_400(
                        {
                            "message": f"Invalid file. file name {attachment_file_name}. Allowed file extensions are {FIELD_REPORT_FILE_ALLOWED_EXT_IN_STR}",
                            "field_report_file_error": field_report_file_serializers.errors,
                        }
                    )


                validated_files.append(attached_file)

            if not validated_files and attachment_is_required:
                return HTTP_400(
                    {
                        "message": "Minimum one file is required to submit.",
                    }
                )

        submission_data = FieldReportFormSubmissions.objects.create(**validated_data)

        if validated_files:
            submission_data.attachment = {"label": attachment_label}
            submission_data.save()

            field_report_files = FieldReportFile.objects.bulk_create(
                [
                    FieldReportFile(file=file, field_report_form_submission=submission_data)
                    for file in validated_files
                ]
            )
            print(field_report_files)

        print(submission_data)
        # TODO change trip status to field form field form submitted.
        trip.status = "field_report_submitted"
        trip.save()

        serializer = self.serializer_class(submission_data)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AllFieldReportFormSubmissionsAPI(views.APIView):
    """Get field report data using trip uuid."""

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.FieldReportFormSubmissionsSerializer

    def get(self, request, *args, **kwargs):
        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        try:
            trip = Trip.objects.get(uuid=kwargs.get("uuid"), organization=org)
        except Trip.DoesNotExist:
            return read_data.get_404_response("Trip")

        try:
            report_submission = FieldReportFormSubmissions.objects.get(
                trip=trip, organization=org
            )
        except FieldReportFormSubmissions.DoesNotExist:
            return read_data.get_404_response("FieldReportFormSubmissions")

        serializer = self.serializer_class(report_submission)

        return Response(serializer.data, status=status.HTTP_200_OK)


class CheckIsRequiredToSubmitFieldReportAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.FieldReportFormSubmissionsSerializer

    def get(self, request, *args, **kwargs):
        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        department = member.department

        if department is None:
            return HTTP_200({"submit_field_report": False})

        try:
            field_report_builder = FieldReportFormConfig.objects.get(
                department=department
            )
        except FieldReportFormConfig.DoesNotExist:
            return HTTP_200({"submit_field_report": False})

        if department.enable_field_report is False:
            return HTTP_200({"submit_field_report": False})

        try:
            trip = Trip.objects.get(uuid=kwargs.get("uuid"), organization=org)
        except Trip.DoesNotExist:
            return read_data.get_404_response("Trip")

        if trip.assigned_to != member:
            return HTTP_400("You dont have permission to perform this action.")

        if trip.status == "field_report_submitted":
            return HTTP_200({"submit_field_report": False})

        if trip.status == "ended":
            return HTTP_200({"submit_field_report": True})

        return HTTP_200({"submit_field_report": False})


