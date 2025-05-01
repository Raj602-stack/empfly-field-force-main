from django.core.exceptions import ValidationError
from django.db.models import Q

from member.models import Member
from organization.models import Organization
from expense.models import (
    RideExpense,
    RideExpenseDocs,
    RideExpenseComment,
    RideExpenseStatus,
    PaymentMode,
)
from trip.models import Trip
from utils import fetch_data

from uuid import uuid4
import logging


logger = logging.getLogger(__name__)


def get_payment_mode(org_uuid: uuid4, uuid: uuid4) -> PaymentMode:
    try:
        return PaymentMode.objects.get(organization__uuid=org_uuid, uuid=uuid)
    except (PaymentMode.DoesNotExist, ValidationError) as e:
        logger.error(e)
    except Exception as e:
        logger.error(e)
        logger.exception(f"Add exception for {e.__class__.__name__} in get_payment_mode")
    return None


def create_ride_expense_comment(
    ride_expense: RideExpense, expense_status: str, member: Member, comments: dict
) -> RideExpenseComment:

    RideExpenseComment.objects.create(
        ride_expense=ride_expense,
        member=member,
        comments=comments,
        status=expense_status,
    )


def get_ride_expense_by_trip(trip: Trip) -> RideExpense:
    """ Get ride expenses created for trip
    """
    try:
        return RideExpense.objects.get(trip=trip)
    except (RideExpense.DoesNotExist) as e:
        logger.error(e)
    except Exception as e:
        logger.error(e)
        logger.exception(
            f"Add exception for {e.__class__.__name__} in get_ride_expense_by_trip"
        )
    return None


def get_my_ride_expenses(member: Member) -> RideExpense:
    """
    if member is req he will get own ride exp.
    if finance get ride exp in the finance stage and final stage
    if admin get ride exp in pending_approval stage.
    """

    org = member.organization

    # If Admin
    if member.role == fetch_data.get_admin_role():
        # Get all expenses (except draft)
        return RideExpense.objects.filter(
            Q(trip__organization=org) & Q(status__in=["pending_approval"])
        )

    # If Finance
    elif member.role == fetch_data.get_finance_role():
        expense_status = [
            *RideExpenseStatus.FINANCE_STAGE,
            *RideExpenseStatus.FINAL_STAGE,
        ]
        # Get all expenses in finance or final stage
        return RideExpense.objects.filter(
            Q(trip__organization=org)
            & (Q(trip__assigned_to=member) | Q(trip__created_by=member))
            & Q(status__in=expense_status)
        )

    else:
        # Get all expenses belonging to the member/manager
        return RideExpense.objects.filter(
            Q(trip__organization=org)
            & (Q(trip__assigned_to=member) | Q(trip__assigned_to__manager=member))
        )
