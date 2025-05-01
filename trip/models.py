from django.core.exceptions import ValidationError
from django.db import models

from organization.models import Location
from expense.models import RideExpense

import uuid
import datetime as dt
import os
from django.contrib.postgres.fields import ArrayField



def default_location():
    return {"latitude": "", "longitude": "", "radius": ""}

def trip_sync_comments() -> dict:
    return {
        "start_scan": {
            "error": None
        },
        "end_scan": {
            "error": None
        },
    }

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


def rename_trip_scan_images(instance: models.Model, filename: "file") -> str:
    filename = rename_image(instance.uuid, filename)
    return os.path.join("member/trip_scans/", filename)


class Trip(models.Model):

    TRIP_STATUS_CHOICES = (
        ("created", "Created"),
        ("started", "Started"),
        ("ended", "Ended"),
        ("field_report_submitted", "Field Report Submitted"),
        ("ride_expense_created", "Ride Expense Created"),
        ("cancelled", "Cancelled"),
    )

    TRIP_TYPE_CHOICES = (("self", "Self"), ("assigned", "Assigned"))
    PRIORITY_CHOICES = (
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("urgent", "Urgent"),
    )

    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    organization = models.ForeignKey(
        "organization.Organization", on_delete=models.CASCADE, related_name="trips"
    )

    name = models.CharField(max_length=200)
    # description = models.CharField(max_length=200, null=True, blank=True)
    description = models.TextField(null=True, blank=True)

    start_location = models.JSONField(default=default_location)
    end_location = models.JSONField(default=default_location)

    # * Explanation: FK and Json fields for location
    """
    The FK fields lets the user know if a system location or custom location was used.
    Regardless, the location data is extracted and stored in the respective JSON fields.
    This is to prevent any issues if the System Location data is updated while a trip is ongoing.
    Ex: Rider started a trip from L1 to L2. While the trip is ongoing, an Admin user decides to update
    L2's lat and long. This will cause issues for the rider and the current trip.
    By storing the lat/long in a JSON field at the time of creation, such issues can be prevented.
    The system will use the lat/long stored in the JSON field for any calculation.
    The FK fields are there for auditing purposes.
    """

    start_location_ptr = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        related_name="trips_start_location",
        null=True,
        blank=True,
    )
    end_location_ptr = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        related_name="trips_end_location",
        null=True,
        blank=True,
    )

    assigned_to = models.ForeignKey(
        "member.Member",
        on_delete=models.SET_NULL,
        related_name="trip_assigned_to",
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=200, choices=TRIP_STATUS_CHOICES, default="created"
    )
    offline = models.BooleanField(default=False)
    trip_type = models.CharField(max_length=200, choices=TRIP_TYPE_CHOICES)

    priority = models.CharField(
        max_length=200, choices=PRIORITY_CHOICES, null=True, blank=True
    )
    trip_sync_comments = models.JSONField(default=trip_sync_comments)

    date = models.DateField(null=True, blank=True)
    time = models.TimeField(null=True, blank=True)

    is_outside_geo_fencing = models.BooleanField(default=False)

    planned_start_time = models.DateTimeField(null=True, blank=True)
    planned_end_time = models.DateTimeField(null=True, blank=True)

    force_trip_sync_logs = ArrayField(
        models.TextField(), null=True, blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        "member.Member",
        on_delete=models.SET_NULL,
        related_name="trip_created_by",
        null=True,
        blank=True,
    )
    updated_by = models.ForeignKey(
        "member.Member",
        on_delete=models.SET_NULL,
        related_name="trip_updated_by",
        null=True,
        blank=True,
    )

    class Meta:
        # unique_together = ["organization", "name"]
        ordering = ["-updated_at"]

    def delete(self, *args, **kwargs):

        if self.status == "created":
            raise ValidationError(
                message="Trip cannot be deleted if status is 'created'"
            )

        super(Trip, self).delete(*args, **kwargs)

    def save(self, *args, **kwargs):

        created = False
        if self.pk is None:
            created = True

        super(Trip, self).save(*args, **kwargs)

        if created:
            TripDetails.objects.get_or_create(trip=self)

        if self.status == "ended":
            RideExpense.objects.get_or_create(trip=self)

    def __str__(self):
        return f"{self.uuid}__{self.name}"


# TODO Deprecate this
class TripEstimation(models.Model):

    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    trip = models.OneToOneField(
        Trip, on_delete=models.CASCADE, related_name="trip_estimation"
    )

    duration = models.CharField(max_length=200, null=True, blank=True)
    distance = models.CharField(max_length=200, null=True, blank=True)

    def __str__(self):
        return f"{self.trip}"


class TripScan(models.Model):

    uuid = models.UUIDField(default=uuid.uuid4, unique=True)

    image = models.ImageField(upload_to=rename_trip_scan_images, null=True, blank=True)

    # Location name is stored in this field
    name = models.CharField(max_length=255, null=True, blank=True)
    latitude = models.CharField(max_length=200)
    longitude = models.CharField(max_length=200)

    time = models.DateTimeField(null=True, blank=True)

    # Captures any issue in scanning (Face not identified or outside geo-fencing area)
    notes = models.JSONField(default=dict, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return str(self.uuid)


class TripDetails(models.Model):

    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    trip = models.OneToOneField(
        Trip, on_delete=models.CASCADE, related_name="trip_details"
    )

    # TODO Confirm if not being used and remove
    # TODO If required, add it in TripScansAPI line number ~319
    start_time = models.DateTimeField(null=True, blank=True)
    # TODO Confirm if not being used and remove
    end_time = models.DateTimeField(null=True, blank=True)

    # Actual duration and distance
    duration = models.CharField(max_length=200, null=True, blank=True)
    distance = models.CharField(max_length=200, null=True, blank=True)

    estimated_duration = models.TimeField(max_length=200, null=True, blank=True)
    estimated_distance = models.CharField(max_length=200, null=True, blank=True)

    start_scan = models.OneToOneField(
        TripScan,
        on_delete=models.SET_NULL,
        related_name="start_trip_details",
        null=True,
        blank=True,
    )
    end_scan = models.OneToOneField(
        TripScan,
        on_delete=models.SET_NULL,
        related_name="end_trip_details",
        null=True,
        blank=True,
    )

    # Used if trip is cancelled
    comments = models.JSONField(default=dict, null=True, blank=True)
    # TODO Add image field
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Trip Details"

    def __str__(self):
        return f"{self.trip}"


class TripTemplate(models.Model):

    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    organization = models.ForeignKey(
        "organization.Organization",
        on_delete=models.CASCADE,
        related_name="trip_templates",
    )

    name = models.CharField(max_length=200)
    # description = models.CharField(max_length=200, null=True, blank=True)
    description = models.TextField(null=True, blank=True)

    start_location = models.JSONField(default=default_location)
    end_location = models.JSONField(default=default_location)

    start_location_ptr = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        related_name="trip_templates_start_location",
        null=True,
        blank=True,
    )
    end_location_ptr = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        related_name="trip_templates_end_location",
        null=True,
        blank=True,
    )

    assigned_to = models.ForeignKey(
        "member.Member",
        on_delete=models.SET_NULL,
        related_name="trip_templates_assigned_to",
        null=True,
        blank=True,
    )

    priority = models.CharField(
        max_length=200, choices=Trip.PRIORITY_CHOICES, default="low"
    )

    date = models.DateField(null=True, blank=True)
    time = models.TimeField(null=True, blank=True)

    schedule = models.JSONField(default=dict, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    created_by = models.ForeignKey(
        "member.Member",
        on_delete=models.SET_NULL,
        related_name="trip_templates_created_by",
        null=True,
        blank=True,
    )
    updated_by = models.ForeignKey(
        "member.Member",
        on_delete=models.SET_NULL,
        related_name="trip_templates_updated_by",
        null=True,
        blank=True,
    )

    class Meta:
        unique_together = ["organization", "name"]

    def __str__(self):
        return f"{self.name}__{self.organization}"
