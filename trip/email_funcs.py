from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

from member.models import Member
from trip.models import Trip

import secrets
import uuid
import logging


logger = logging.getLogger(__name__)


def get_email_recipients(trip: Trip, include_creator: bool = True) -> list:

    email_recipients = []

    rider = trip.assigned_to.user
    if rider.email:
        email_recipients.append(rider.email)
    else:
        logger.error(f"{rider=} does not have an email")

    if include_creator:
        creator = trip.created_by.user
        if creator.email:
            email_recipients.append(creator.email)
        else:
            logger.error(f"{creator=} does not have an email")

    return email_recipients


def create_email_content(trip: Trip) -> dict:

    rider = trip.assigned_to.user
    creator = trip.created_by.user
    start_location = trip.start_location.get("name")
    end_location = trip.end_location.get("name")

    return {
        "domain": settings.UI_DOMAIN_URL,
        # Trip
        "trip_name": trip.name,
        "trip_uuid": trip.uuid,
        "cancellation_reason": trip.trip_details.comments.get(
            "cancellation_reason", ""
        ),
        "creator_name": f"{creator.first_name} {creator.last_name}",
        "creator_username": creator.username,
        # Rider
        "rider_name": f"{rider.first_name} {rider.last_name}",
        "rider_username": rider.username,
        # Location
        "start_location": start_location,
        "end_location": end_location,
    }


def send_trip_creation_notification(trip: Trip) -> bool:

    subject = "Trip Created | Empfly"
    content = create_email_content(trip)
    email_recipients = get_email_recipients(trip, include_creator=False)

    try:
        email_template_name = "trip/email/trip/trip-creation-notification.html"
        email_message = render_to_string(email_template_name, content)
    except Exception as e:
        logger.error(e)
        logger.exception(
            f"Add exception for {e.__class__.__name__} in send_trip_creation_notification"
        )
        return False

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
            f"Add exception for {e.__class__.__name__} in send_trip_creation_notification"
        )

    return False


def send_trip_cancellation_notification(trip: Trip) -> bool:

    subject = "Trip Cancelled | Empfly"
    content = create_email_content(trip)
    email_recipients = get_email_recipients(trip)

    try:
        email_template_name = "trip/email/trip/trip-cancellation-notification.html"
        email_message = render_to_string(email_template_name, content)
    except Exception as e:
        logger.error(e)
        logger.exception(
            f"Add exception for {e.__class__.__name__} in send_trip_cancellation_notification"
        )
        return False

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
            f"Add exception for {e.__class__.__name__} in send_trip_cancellation_notification"
        )

    return False
