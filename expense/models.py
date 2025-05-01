import datetime as dt
import os
import uuid

from django.db import models


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


def rename_ride_expense_docs(instance: models.Model, filename: "file") -> str:
    filename = rename_image(instance.uuid, filename)
    return os.path.join(f"trip/{instance.uuid}/docs/", filename)


class RideExpenseStatus:

    INITIAL_STAGE = ["draft"]
    MANAGER_STAGE = ["pending_approval", "approval_rejected"]
    FINANCE_STAGE = ["pending_reimbursement", "reimbursement_rejected"]
    FINAL_STAGE = ["reimbursed", "closed"]

    MANAGER_STATUS_OPTIONS = ["approval_rejected", "pending_reimbursement"]
    FINANCE_STATUS_OPTIONS = ["reimbursement_rejected", "reimbursed"]

    APPROVAL_STATUS = ["pending_reimbursement", "reimbursed"]
    REJECTION_STATUS = ["approval_rejected", "reimbursement_rejected"]


class RideExpense(models.Model):

    """
    # Stage 1
    Draft   
    # Stage 2
    Pending Approval
    # Stage 3
    Pending Reimbursement (approved) or Apporval Rejected (rejected)
    # Stage 4
    reimbursed (approved) or Reimbursement Rejected (rejected)
    """

    VEHICLE_MODE_CHOICES = (("self", "Self"), ("hire", "Hire"))
    RIDE_EXPENSE_STATUS_CHOICES = (
        ("draft", "Draft"),
        ("pending_approval", "Pending Approval"),
        ("pending_reimbursement", "Pending Reimbursement"),
        ("approval_rejected", "Approval Rejected"),
        ("reimbursement_rejected", "Reimbursement Rejected"),
        ("reimbursed", "Reimbursed"),
        # CONFIRM Manoj: Are we using this
        ("closed", "Closed"),
    )

    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    trip = models.OneToOneField(
        "trip.Trip", on_delete=models.CASCADE, related_name="ride_expense"
    )

    # description = models.CharField(max_length=200, null=True, blank=True)
    description = models.TextField(null=True, blank=True)

    vehicle_mode = models.CharField(
        max_length=200, choices=VEHICLE_MODE_CHOICES, null=True, blank=True
    )

    fuel = models.ForeignKey(
        "organization.Fuel",
        on_delete=models.PROTECT,
        related_name="ride_expenses",
        null=True,
        blank=True,
    )
    vehicle = models.ForeignKey(
        "organization.Vehicle",
        on_delete=models.PROTECT,
        related_name="ride_expenses",
        null=True,
        blank=True,
    )
    payment_mode = models.ForeignKey(
        "expense.PaymentMode",
        on_delete=models.PROTECT,
        related_name="ride_expenses",
        null=True,
        blank=True,
    )

    amount = models.FloatField(null=True, blank=True)
    amount_breakdown = models.JSONField(default=dict, null=True, blank=True)
    reimbursement_amount = models.FloatField(null=True, blank=True)

    status = models.CharField(
        max_length=200, choices=RIDE_EXPENSE_STATUS_CHOICES, default="draft"
    )
    claim_reimbursement = models.BooleanField(default=True)

    auto_approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        "member.Member",
        on_delete=models.SET_NULL,
        related_name="ride_expenses_approved_by",
        null=True,
        blank=True,
    )
    reimbursed_by = models.ForeignKey(
        "member.Member",
        on_delete=models.SET_NULL,
        related_name="ride_expenses_reimbursed_by",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.trip}"


class RideExpenseComment(models.Model):

    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    ride_expense = models.ForeignKey(
        RideExpense, on_delete=models.CASCADE, related_name="ride_expense_comments"
    )
    member = models.ForeignKey(
        "member.Member",
        on_delete=models.SET_NULL,
        related_name="ride_expense_comments",
        null=True,
        blank=True,
    )

    status = models.CharField(max_length=200)
    comments = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.ride_expense}__{self.member}"


class RideExpenseDocs(models.Model):

    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    ride_expense = models.ForeignKey(
        RideExpense, on_delete=models.CASCADE, related_name="ride_expense_docs"
    )

    image = models.ImageField(upload_to=rename_ride_expense_docs, null=True, blank=True)
    document = models.FileField(
        upload_to=rename_ride_expense_docs, null=True, blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return str(self.uuid)


class PaymentMode(models.Model):

    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    organization = models.ForeignKey(
        "organization.Organization",
        on_delete=models.CASCADE,
        related_name="payment_modes",
    )

    name = models.CharField(max_length=200)
    # description = models.CharField(max_length=200, null=True, blank=True)
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.organization}__{self.name}"

    class Meta:
        unique_together = ["organization", "name"]
