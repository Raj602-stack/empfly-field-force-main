from django.db import models
from django.db.models import CheckConstraint, Q
from django.core.validators import MaxLengthValidator, MinValueValidator, MaxValueValidator

import datetime as dt
import os
import uuid


def default_org_settings() -> dict:
    return {
        "scan_settings": {
            "online": {
                "face_recognition": True,
                "geo_fencing": True,
            },
            "offline": {
                "face_recognition": True,
                "geo_fencing": True,
            },
        },
        "geo_fencing_radius": 50.0,
        "mandatory_approval": True,
        # TODO HIGH: Check if this is enforced
        "allow_offline_trips": True,
        "trip_rag_analysis": True
    }


def default_limit_settings() -> dict:
    return {"member": 5}


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


def rename_company_logo(instance: "Organization", filename: "file") -> str:
    filename = rename_image(instance.uuid, filename)
    return os.path.join("company/logo/", filename)


class Organization(models.Model):

    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    logo = models.ImageField(upload_to=rename_company_logo, null=True, blank=True)

    name = models.CharField(max_length=200, unique=True)
    # description = models.CharField(max_length=200, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    # domain = models.CharField(max_length=200, unique=True)

    location = models.CharField(max_length=200, null=True, blank=True)

    # trip_rag_analysis = models.BooleanField(default=False)

    # city = models.CharField(max_length=200, null=True, blank=True)
    # address = models.TextField(null=True, blank=True)

    organization_email = models.EmailField(null=True, blank=True)
    timezone = models.CharField(max_length=200, default="UTC")

    settings = models.JSONField(default=default_org_settings, null=True, blank=True)
    limit = models.JSONField(default=default_limit_settings, null=True, blank=True)

    disable_offline_trips = models.BooleanField(default=False)

    STATUS_CHOICES = (("active", "Active"), ("inactive", "Inactive"))
    status = models.CharField(max_length=50, default="active", choices=STATUS_CHOICES)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    created_by = models.ForeignKey(
        "member.Member",
        on_delete=models.SET_NULL,
        related_name="org_created_by",
        null=True,
        blank=True,
    )
    updated_by = models.ForeignKey(
        "member.Member",
        on_delete=models.SET_NULL,
        related_name="org_updated_by",
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"{self.name}"


class Vehicle(models.Model):

    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="vehicles")

    name = models.CharField(max_length=200)
    # description = models.CharField(max_length=200, null=True, blank=True)
    description = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        "member.Member",
        on_delete=models.SET_NULL,
        related_name="vehicle_created_by",
        null=True,
        blank=True,
    )
    updated_by = models.ForeignKey(
        "member.Member",
        on_delete=models.SET_NULL,
        related_name="vehicle_updated_by",
        null=True,
        blank=True,
    )

    auto_approval_limit = models.FloatField(null=True, blank=True)

    class Meta:
        unique_together = ["organization", "name"]
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.name}__{self.organization}"


class Fuel(models.Model):

    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="fuels")

    name = models.CharField(max_length=200)
    # description = models.CharField(max_length=200, null=True, blank=True)
    description = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        "member.Member",
        on_delete=models.SET_NULL,
        related_name="fuel_created_by",
        null=True,
        blank=True,
    )
    updated_by = models.ForeignKey(
        "member.Member",
        on_delete=models.SET_NULL,
        related_name="fuel_updated_by",
        null=True,
        blank=True,
    )

    class Meta:
        unique_together = ["organization", "name"]
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.name}__{self.organization}"


class RideExpenseCostMatrix(models.Model):

    DISTANCE_UNIT_CHOICES = (
        ("kilometer", "Kilometer"),
        ("mile", "Mile"), # TODO deprecated
    )

    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="cost_matrices")

    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT, related_name="cost_matrices")
    fuel = models.ForeignKey(Fuel, on_delete=models.PROTECT, related_name="cost_matrices")

    distance_unit = models.CharField(max_length=200, choices=DISTANCE_UNIT_CHOICES)
    cost_per_unit = models.FloatField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        "member.Member",
        on_delete=models.SET_NULL,
        related_name="cost_matrices_created_by",
        null=True,
        blank=True,
    )
    updated_by = models.ForeignKey(
        "member.Member",
        on_delete=models.SET_NULL,
        related_name="cost_matrices_updated_by",
        null=True,
        blank=True,
    )

    class Meta:
        unique_together = ["fuel", "vehicle"]
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.vehicle.organization.name}__{self.vehicle.name}__{self.fuel.name}"


# system location
class Location(models.Model):
    
    SOURCE_CHOICES = (
        ("manual", "Manual"),
        ("places_api", "Places API"),
    )

    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="locations")

    name = models.CharField(max_length=1000)
    description = models.TextField(null=True, blank=True)

    latitude = models.DecimalField(max_digits=26, decimal_places=22)
    longitude = models.DecimalField(max_digits=26, decimal_places=22)
    radius = models.FloatField(default=50.0, validators=[MinValueValidator(0.0), MaxValueValidator(5000.0)])

    source = models.CharField(
        max_length=200,
        choices=SOURCE_CHOICES,
        default=SOURCE_CHOICES[0][0],
    )

    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)

    department  = models.ForeignKey(
        "organization.Department",
        on_delete=models.SET_NULL,
        null=True ,
         blank=True,
        related_name="location",
    )


    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        "member.Member",
        on_delete=models.SET_NULL,
        related_name="location_created_by",
        null=True,
        blank=True,
    )
    updated_by = models.ForeignKey(
        "member.Member",
        on_delete=models.SET_NULL,
        related_name="location_updated_by",
        null=True,
        blank=True,
    )

    class Meta:
        unique_together = ["organization", "name"]
        constraints = (
            # Radius should be between 0-5000 meters
            CheckConstraint(
                check=Q(radius__gte=0.0) & Q(radius__lte=5000.0),
                name="location_radius_range",
            ),
        )
        ordering = ["-updated_at"]
        verbose_name = "System Location"
        verbose_name_plural = "System Locations"

    def __str__(self):
        return f"{self.name}__{self.organization}"


class Role(models.Model):

    uuid = models.UUIDField(unique=True, default=uuid.uuid4)
    name = models.CharField(max_length=200)
    # description = models.CharField(max_length=200, null=True, blank=True)
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.name}"


class Designation(models.Model):

    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    organization = models.ForeignKey(Organization, related_name="designations", on_delete=models.CASCADE)

    name = models.CharField(max_length=200)
    # description = models.CharField(max_length=200, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        "member.Member",
        on_delete=models.SET_NULL,
        related_name="designation_created_by",
        null=True,
        blank=True,
    )
    updated_by = models.ForeignKey(
        "member.Member",
        on_delete=models.SET_NULL,
        related_name="designation_updated_by",
        null=True,
        blank=True,
    )

    class Meta:
        unique_together = ("organization", "name")
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.organization}__{self.name}"


class Department(models.Model):

    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    organization = models.ForeignKey(Organization, related_name="departments", on_delete=models.CASCADE)

    name = models.CharField(max_length=200)
    # description = models.CharField(max_length=200, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    # department_head = models.OneToOneField(
    #     "member.Member",
    #     on_delete=models.SET_NULL,
    #     related_name="department_head",
    #     null=True,
    #     blank=True,
    # )
    is_active = models.BooleanField(default=True)
    enable_field_report = models.BooleanField(default=False)

    enable_create_trip_form_config = models.BooleanField(default=False)
    enable_admin_report_form_config = models.BooleanField(default=False)

    department_head = models.ManyToManyField(
        "member.Member",
        related_name="department_head",
        # null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    created_by = models.ForeignKey(
        "member.Member",
        on_delete=models.SET_NULL,
        related_name="department_created_by",
        null=True,
        blank=True,
    )
    updated_by = models.ForeignKey(
        "member.Member",
        on_delete=models.SET_NULL,
        related_name="department_updated_by",
        null=True,
        blank=True,
    )

    class Meta:
        unique_together = ("organization", "name")
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.organization}__{self.name}"


class OrganizationLocation(models.Model):

    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    organization = models.ForeignKey(
        "organization.Organization",
        on_delete=models.CASCADE,
        related_name="organization_locations",
    )

    name = models.CharField(max_length=200)
    # description = models.CharField(max_length=200, null=True, blank=True)
    description = models.TextField(null=True, blank=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        "member.Member",
        on_delete=models.SET_NULL,
        related_name="organization_location_created_by",
        null=True,
        blank=True,
    )
    updated_by = models.ForeignKey(
        "member.Member",
        on_delete=models.SET_NULL,
        related_name="organization_location_updated_by",
        null=True,
        blank=True,
    )

    class Meta:
        unique_together = ["organization", "name"]
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.name}__{self.organization}"


class ExternalConnection(models.Model):

    organization = models.ForeignKey(
        Organization, 
        on_delete=models.CASCADE, 
        related_name="external_connections"
    )

    updated_by = models.ForeignKey(
        "member.Member", 
        on_delete=models.SET_NULL, 
        related_name="external_connections", 
        null=True,
        blank=True
    )

    # google map API key
    gcp_api_key = models.CharField(max_length=255)

    """we are converting google map api key yo shorthand version
        ex: abcdefghijklmn -> abcd******klmn
        Used for frontend view purpose
    """
    short_gcp_api_key = models.CharField(max_length=255, null=True, blank=True)

    status = models.BooleanField(default=True)

    # automaticaly updates to current date time -> timezone now 
    # model.save()
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"org:{self.organization.name} status: {self.status}"


# TODO Low: Move PaymentMode to Organization
