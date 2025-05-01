from django.db import models
from django.db.models import Q
from django.conf import settings

from django.utils import crypto
import uuid
import logging


logger = logging.getLogger(__name__)


def generate_random_string(length: int = 10) -> str:
    return crypto.get_random_string(length)


class ExportRequest(models.Model):

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    )

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    member = models.ForeignKey(
        "member.Member",
        on_delete=models.CASCADE,
        related_name="export_requests",
    )
    request_id = models.CharField(
        max_length=200,
        default=generate_random_string,
        unique=True,
        editable=False,
    )

    # Determines if data in CSV is of Trips, RideExpenses or Members etc
    # content = models.CharField(max_length=200)
    content = models.TextField()
    filter = models.JSONField(default=dict, null=True, blank=True)

    status = models.CharField(max_length=200, choices=STATUS_CHOICES, default="pending")
    link = models.CharField(max_length=200, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.member}__{self.request_id}"

    def save(self, *args, **kwargs):

        if self.pk is None:
            is_duplicate = ExportRequest.objects.filter(
                Q(member=self.member) & Q(content=self.content) & Q(status="pending")
            ).exists()

            if is_duplicate:
                raise ValueError

        super(ExportRequest, self).save(*args, **kwargs)
