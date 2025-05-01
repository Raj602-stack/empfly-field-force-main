import datetime as dt
import os
import uuid

from django.db import models
from django.db.models import UniqueConstraint


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


def rename_member_fr_images(instance: models.Model, filename: "file") -> str:
    filename = rename_image(instance.uuid, filename)
    return os.path.join("member/face_recognition/", filename)


def rename_member_profile_images(instance: models.Model, filename: "file") -> str:
    filename = rename_image(instance.member.uuid, filename)
    return os.path.join("member/profile/", filename)


class Member(models.Model):

    uuid = models.UUIDField(unique=True, default=uuid.uuid4)
    user = models.ForeignKey(
        "account.User", on_delete=models.CASCADE, related_name="members"
    )

    organization = models.ForeignKey(
        "organization.Organization",
        on_delete=models.CASCADE,
        related_name="members",
    )
    role = models.ForeignKey(
        "organization.Role",
        on_delete=models.CASCADE,
        related_name="members",
    )
    manager = models.ForeignKey(
        "member.Member",
        on_delete=models.PROTECT,
        related_name="managed_members",
        null=True,
        blank=True,
    )

    designation = models.ForeignKey(
        "organization.Designation",
        related_name="members",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    department = models.ForeignKey(
        "organization.Department",
        related_name="members",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    organization_location = models.ForeignKey(
        "organization.OrganizationLocation",
        related_name="members",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    employee_id = models.CharField(max_length=200, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["organization", "user"]
        constraints = [
            UniqueConstraint(
                fields=["organization", "employee_id"], name="unique_employee_id"
            )
        ]
        ordering = ['-updated_at']

    def save(self, *args, **kwargs):

        created = False
        if self.pk is None:
            created = True

        super(Member, self).save(*args, **kwargs)
        if created:
            Profile.objects.get_or_create(member=self)

    def __str__(self):
        return f"{self.user.email}__{self.organization}"


class Profile(models.Model):

    THEME_CHOICES = (
        ("light", "Light"),
        ("dark", "Dark"),
        ("system", "System"),
    )
    GENDER_CHOICES = (
        ("Male", "male"),
        ("Female", "female"),
        ("Non-binary", "non-binary"),
        ("Prefer not to say", "prefer not to say"),
    )

    member = models.OneToOneField(
        Member, on_delete=models.CASCADE, related_name="profile"
    )

    photo = models.ImageField(
        upload_to=rename_member_profile_images, null=True, blank=True
    )
    phone = models.CharField(max_length=15, null=True, blank=True)
    dob = models.DateField(null=True, blank=True)
    address = models.TextField(null=True, blank=True)

    gender = models.CharField(
        max_length=200, choices=GENDER_CHOICES, null=True, blank=True
    )
    language = models.CharField(
        max_length=200, default="English", null=True, blank=True
    )
    location = models.CharField(max_length=200, null=True, blank=True)
    timezone = models.CharField(max_length=200, default="UTC", null=True, blank=True)

    # Preferences
    date_format = models.CharField(max_length=200, null=True, blank=True)
    theme = models.CharField(max_length=200, choices=THEME_CHOICES, default="light")
    settings = models.JSONField(default=dict, null=True, blank=True)

    def __str__(self):
        return f"{self.member}"


class MemberImage(models.Model):

    uuid = models.UUIDField(unique=True, default=uuid.uuid4)
    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name="member_images",
    )

    image = models.ImageField(upload_to=rename_member_fr_images, null=True, blank=True)
    encoding = models.JSONField(default=dict, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.member}"
