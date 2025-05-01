from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Q
from django.template.loader import render_to_string

from member.models import Member
from expense.models import RideExpense

from utils import fetch_data

import logging


logger = logging.getLogger(__name__)


def get_converted_status(status: str) -> str:

    for status_tuple in RideExpense.RIDE_EXPENSE_STATUS_CHOICES:
        if status == status_tuple[0]:
            return status_tuple[1]

    return status


def get_email_recipients(
    ride_expense: RideExpense, include_others: bool = True
) -> list:

    email_recipients = []
    rider = ride_expense.trip.assigned_to.user
    manager = ride_expense.trip.assigned_to.manager

    # If Rider has email
    if rider.email:
        email_recipients.append(rider.email)
    else:
        logger.error(f"{rider=} does not have an email")

    if include_others:
        # If Rider has manager
        if manager:
            # If Manager has email
            if manager.user.email:
                email_recipients.append(manager.user.email)
            else:
                logger.error(f"{manager=} does not have an email")

        # Add Admins
        else:

            admin_role = fetch_data.get_admin_role()
            admins = Member.objects.filter(
                Q(organization=ride_expense.trip.organization) & Q(role=admin_role)
            )

            for admin in admins:
                # If Admin has email
                if admin.user.email:
                    email_recipients.append(admin.user.email)

    return email_recipients


def create_email_content(ride_expense: RideExpense, status: str = "Pending") -> dict:

    trip = ride_expense.trip
    rider = trip.assigned_to.user

    if status in ["Pending Reimbursement", "Approval Rejected"]:
        action_taken_by = ride_expense.approved_by.user
    elif status in ["Reimbursement Rejected", "Reimbursed"]:
        action_taken_by = ride_expense.reimbursed_by.user
    else:
        action_taken_by = None

    if status == "Approval Rejected":
        ride_expense_comment = ride_expense.ride_expense_comments.filter(
            member=ride_expense.approved_by
        ).first()
    elif status == "Reimbursement Rejected":
        ride_expense_comment = ride_expense.ride_expense_comments.filter(
            member=ride_expense.reimbursed_by
        ).first()
    else:
        ride_expense_comment = None

    email_content = {
        "domain": settings.UI_DOMAIN_URL,
        # Trip
        "trip_name": trip.name,
        "trip_uuid": trip.uuid,
        # Rider
        "rider_name": f"{rider.first_name} {rider.last_name}",
        "rider_username": rider.username,
        # Expense
        "amount": ride_expense.amount,
        "status": status,
    }

    if action_taken_by:
        email_content.update(
            {
                "action_taken_by_name": f"{action_taken_by.first_name} {action_taken_by.last_name}",
                "action_taken_by_username": action_taken_by.username,
            }
        )

    if ride_expense_comment:
        comments = ride_expense_comment.comments
        email_content.update({"comments": comments})

    return email_content


def send_expense_creation_notification(ride_expense: RideExpense) -> bool:

    subject = "Ride Expense Created | Empfly"
    content = create_email_content(ride_expense)

    try:
        email_template_name = "trip/email/trip/expense-creation-notification.html"
        email_message = render_to_string(email_template_name, content)
    except Exception as e:
        logger.error(e)
        logger.exception(
            f"Add exception for {e.__class__.__name__} in "
            "send_expense_creation_notification"
        )

    email_recipients = get_email_recipients(ride_expense)

    try:

        send_mail(
            subject,
            "",
            settings.EMAIL_SENDER,
            email_recipients,
            fail_silently=False,
            html_message=email_message,
        )

        logger.info("Succesfully sent email")
        return True

    except Exception as e:
        logger.error(e)
        logger.exception(
            f"Add exception for {e.__class__.__name__} in "
            "send_expense_creation_notification"
        )

    return False


def send_expense_update_notification(ride_expense: RideExpense) -> bool:

    status = get_converted_status(ride_expense.status)
    status_title = status.title()

    subject = f"Ride Expense {status_title} | Empfly"
    content = create_email_content(ride_expense, status_title)

    try:
        email_template_name = "trip/email/trip/expense-update-notification.html"
        email_message = render_to_string(email_template_name, content)
    except Exception as e:
        logger.error(e)
        logger.exception(
            f"Add exception for {e.__class__.__name__} in "
            "send_expense_update_notification"
        )

    email_recipients = get_email_recipients(ride_expense, include_others=False)
    try:

        send_mail(
            subject,
            "",
            settings.EMAIL_SENDER,
            email_recipients,
            fail_silently=False,
            html_message=email_message,
        )
        return True

    except Exception as e:
        logger.error(e)
        logger.exception(
            f"Add exception for {e.__class__.__name__} in send_expense_update_notification"
        )

    return False


def send_expense_notification_to_finance(ride_expense: RideExpense) -> bool:

    status_title = ride_expense.status.title()
    subject = "Ride Expense - Action Required | Empfly"
    content = create_email_content(ride_expense, status_title)

    try:
        email_template_name = "trip/email/trip/finance-expense-notification.html"
        email_message = render_to_string(email_template_name, content)
    except Exception as e:
        logger.error(e)
        logger.exception(
            f"Add exception for {e.__class__.__name__} in "
            "send_expense_notification_to_finance"
        )

    email_recipients = []
    finance_role = fetch_data.get_finance_role()
    finance_members = Member.objects.filter(
        Q(organization=ride_expense.trip.organization) & Q(role=finance_role)
    )
    for finance_member in finance_members:
        if finance_member.user.email:
            email_recipients.append(finance_member.user.email)

    try:

        send_mail(
            subject,
            "",
            settings.EMAIL_SENDER,
            email_recipients,
            fail_silently=False,
            html_message=email_message,
        )
        return True

    except Exception as e:
        logger.error(e)
        logger.exception(
            f"Add exception for {e.__class__.__name__} in send_expense_notification_to_finance"
        )

    return False
