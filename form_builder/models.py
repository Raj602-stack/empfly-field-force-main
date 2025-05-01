from django.db import models
import uuid
import os
import datetime as dt
from django.core.exceptions import ValidationError

from form_builder.constants import FIELD_REPORT_FILE_ALLOWED_EXT
# Create your models here.


class FieldReportFormConfig(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True)

    department = models.OneToOneField(
        "organization.Department",
        related_name="field_report_form_config",
        on_delete=models.CASCADE,
    )
    organization = models.ForeignKey(
        "organization.Organization",
        related_name="field_report_form_config",
        on_delete=models.CASCADE,
    )

    """
    JSONField example
        {
            "label": "Doctor",
            "constraint": "is_number",
            "required": True
        }
    """

    field_1 = models.JSONField(null=True, blank=True)
    field_2 = models.JSONField(null=True, blank=True)
    field_3 = models.JSONField(null=True, blank=True)
    field_4 = models.JSONField(null=True, blank=True)
    field_5 = models.JSONField(null=True, blank=True)
    field_6 = models.JSONField(null=True, blank=True)
    field_7 = models.JSONField(null=True, blank=True)
    field_8 = models.JSONField(null=True, blank=True)
    field_9 = models.JSONField(null=True, blank=True)
    field_10 = models.JSONField(null=True, blank=True)
    field_11 = models.JSONField(null=True, blank=True)
    field_12 = models.JSONField(null=True, blank=True)
    field_13 = models.JSONField(null=True, blank=True)
    field_14 = models.JSONField(null=True, blank=True)
    field_15 = models.JSONField(null=True, blank=True)
    field_16 = models.JSONField(null=True, blank=True)
    field_17 = models.JSONField(null=True, blank=True)
    field_18 = models.JSONField(null=True, blank=True)
    field_19 = models.JSONField(null=True, blank=True)
    field_20 = models.JSONField(null=True, blank=True)

    # This data will relate to field report files
    attachment = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class FieldReportFormSubmissions(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True)

    department = models.ForeignKey(
        "organization.Department",
        on_delete=models.CASCADE,
        related_name="field_report_form_submission",
    )
    organization = models.ForeignKey(
        "organization.Organization",
        on_delete=models.CASCADE,
        related_name="field_report_form_submission",
    )
    field_report_form = models.ForeignKey(
        FieldReportFormConfig,
        on_delete=models.CASCADE,
        related_name="field_report_form_submission",
    )
    trip = models.OneToOneField(
        "trip.Trip",
        on_delete=models.CASCADE,
        related_name="field_report_form_submission",
    )

    """
    JSONField example
        {
            "label": "Doctor",
            "value": "Jacob"
        }
    """

    field_1 = models.JSONField(null=True, blank=True)
    field_2 = models.JSONField(null=True, blank=True)
    field_3 = models.JSONField(null=True, blank=True)
    field_4 = models.JSONField(null=True, blank=True)
    field_5 = models.JSONField(null=True, blank=True)
    field_6 = models.JSONField(null=True, blank=True)
    field_7 = models.JSONField(null=True, blank=True)
    field_8 = models.JSONField(null=True, blank=True)
    field_9 = models.JSONField(null=True, blank=True)
    field_10 = models.JSONField(null=True, blank=True)
    field_11 = models.JSONField(null=True, blank=True)
    field_12 = models.JSONField(null=True, blank=True)
    field_13 = models.JSONField(null=True, blank=True)
    field_14 = models.JSONField(null=True, blank=True)
    field_15 = models.JSONField(null=True, blank=True)
    field_16 = models.JSONField(null=True, blank=True)
    field_17 = models.JSONField(null=True, blank=True)
    field_18 = models.JSONField(null=True, blank=True)
    field_19 = models.JSONField(null=True, blank=True)
    field_20 = models.JSONField(null=True, blank=True)

    attachment = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


def rename_image(attribute: uuid.uuid4, filename: "file") -> str:
    # Gets the file extension
    ext = filename.split(".")[-1]
    # Extracts the seconds passed and the first 3 milliseconds since epoch
    # and concatenates them into a string
    seconds_since_epoch = str(dt.datetime.now().timestamp())[:-3].replace(".", "")
    # Creates unique name based on user ID and time since epoch
    unique_name = f"{attribute}__{seconds_since_epoch}"
    # Concatenates unique name and file extension
    filename = f"{unique_name}.{ext}"
    return filename


def rename_field_report_file(instance: models.Model, filename: "file") -> str:
    filename = rename_image(instance.uuid, filename)
    return os.path.join("field_report/field_report_file/", filename)

def validate_file_extension(value):
    """Check file extension is valid or not.

    Args:
        value (file): uploading file (ex: img, csv)

    Raises:
        ValidationError: Unsupported file extension.
    """
    ext = os.path.splitext(value.name)[1]  # [0] returns path+filename
    valid_extensions = FIELD_REPORT_FILE_ALLOWED_EXT
    print(ext.lower(), "ext.lower()")
    if not ext.lower() in valid_extensions:
        raise ValidationError('Unsupported file extension.')

def file_size(value): # add this to some file where you can import it from
    max_file_size_in_mb = 10
    limit = max_file_size_in_mb * 1024 * 1024 # Byte
    print(f"file size: {value.size}")
    print(f"limit: {limit}")
    if value.size > limit:
        raise ValidationError(f'File too large. Size should not exceed {max_file_size_in_mb} MB.')

class FieldReportFile(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True)

    file = models.FileField(
        upload_to=rename_field_report_file, validators=[validate_file_extension, file_size]
    )

    field_report_form_submission = models.ForeignKey(
        FieldReportFormSubmissions,
        on_delete=models.CASCADE,
        related_name="field_report_file",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)



# Create trip Form Builder
class CreateTripFormConfig(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True)

    department = models.OneToOneField(
        "organization.Department",
        related_name="create_trip_form_config",
        on_delete=models.CASCADE,
    )
    organization = models.ForeignKey(
        "organization.Organization",
        related_name="create_trip_form_config",
        on_delete=models.CASCADE,
    )

    """
    JSONField example
        {
            "label": "Doctor",
            "constraint": "all / is_email / is_number / is_url ",
            "type": "text",
            "options": [],
            "required": True
        },
        {
            "label": "Doctor",
            "constraint": "is_number",
            "type": "dropdown",
            "options": ["option_1","option_2"],
            "required": False
        }
    """

    field_1 = models.JSONField(null=True, blank=True)
    field_2 = models.JSONField(null=True, blank=True)
    field_3 = models.JSONField(null=True, blank=True)
    field_4 = models.JSONField(null=True, blank=True)
    field_5 = models.JSONField(null=True, blank=True)
    field_6 = models.JSONField(null=True, blank=True)
    field_7 = models.JSONField(null=True, blank=True)
    field_8 = models.JSONField(null=True, blank=True)
    field_9 = models.JSONField(null=True, blank=True)
    field_10 = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class CreateTripFormSubmissions(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True)

    department = models.ForeignKey(
        "organization.Department",
        on_delete=models.CASCADE,
        related_name="create_trip_form_submissions",
    )
    organization = models.ForeignKey(
        "organization.Organization",
        on_delete=models.CASCADE,
        related_name="create_trip_form_submissions",
    )
    create_trip_form = models.ForeignKey(
        CreateTripFormConfig,
        on_delete=models.CASCADE,
        related_name="create_trip_form_submissions",
    )
    trip = models.OneToOneField(
        "trip.Trip",
        on_delete=models.CASCADE,
        related_name="create_trip_form_submissions",
    )
    """
    JSONField example
        {
            "label": "Doctor",
            "constraint": "all / is_email / is_number / is_url ",
            "type": "text",
            "options": [],
            "required": True
        },
        {
            "label": "Doctor",
            "constraint": "is_number",
            "type": "dropdown",
            "options": ["option_1","option_2"],
            "required": False
        }
    """

    field_1 = models.JSONField(null=True, blank=True)
    field_2 = models.JSONField(null=True, blank=True)
    field_3 = models.JSONField(null=True, blank=True)
    field_4 = models.JSONField(null=True, blank=True)
    field_5 = models.JSONField(null=True, blank=True)
    field_6 = models.JSONField(null=True, blank=True)
    field_7 = models.JSONField(null=True, blank=True)
    field_8 = models.JSONField(null=True, blank=True)
    field_9 = models.JSONField(null=True, blank=True)
    field_10 = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)



# Create admin Form Builder
class AdminReportFormConfig(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True)

    department = models.OneToOneField(
        "organization.Department",
        related_name="admin_report_form_config",
        on_delete=models.CASCADE,
    )
    organization = models.ForeignKey(
        "organization.Organization",
        related_name="admin_report_form_config",
        on_delete=models.CASCADE,
    )

    """
    JSONField example
        {
            "label": "Doctor",
            "constraint": "is_email / is_number / is_url ",
            "type": "text",
            "options": [],
            "required": True
        },
        {
            "label": "Doctor",
            "type": "dropdown",
            "options": ["option_1","option_2"],
            "required": False
        }
    """

    field_1 = models.JSONField(null=True, blank=True)
    field_2 = models.JSONField(null=True, blank=True)
    field_3 = models.JSONField(null=True, blank=True)
    field_4 = models.JSONField(null=True, blank=True)
    field_5 = models.JSONField(null=True, blank=True)
    field_6 = models.JSONField(null=True, blank=True)
    field_7 = models.JSONField(null=True, blank=True)
    field_8 = models.JSONField(null=True, blank=True)
    field_9 = models.JSONField(null=True, blank=True)
    field_10 = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)



class AdminReportFormSubmissions(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True)

    department = models.ForeignKey(
        "organization.Department",
        on_delete=models.CASCADE,
        related_name="admin_report_form_submissions",
    )
    organization = models.ForeignKey(
        "organization.Organization",
        on_delete=models.CASCADE,
        related_name="admin_report_form_submissions",
    )
    admin_report_form = models.ForeignKey(
        AdminReportFormConfig,
        on_delete=models.CASCADE,
        related_name="admin_report_form_submissions",
    )
    trip = models.OneToOneField(
        "trip.Trip",
        on_delete=models.CASCADE,
        related_name="admin_report_form_submissions",
    )
    """
    JSONField example
        {
            "label": "Doctor",
            "constraint": "all / is_email / is_number / is_url ",
            "type": "text",
            "options": [],
            "required": True
        },
        {
            "label": "Doctor",
            "constraint": "is_number",
            "type": "dropdown",
            "options": ["option_1","option_2"],
            "required": False
        }
    """

    field_1 = models.JSONField(null=True, blank=True)
    field_2 = models.JSONField(null=True, blank=True)
    field_3 = models.JSONField(null=True, blank=True)
    field_4 = models.JSONField(null=True, blank=True)
    field_5 = models.JSONField(null=True, blank=True)
    field_6 = models.JSONField(null=True, blank=True)
    field_7 = models.JSONField(null=True, blank=True)
    field_8 = models.JSONField(null=True, blank=True)
    field_9 = models.JSONField(null=True, blank=True)
    field_10 = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

