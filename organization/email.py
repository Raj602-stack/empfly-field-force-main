from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

import logging

from organization.models import Organization
from trip.constants import END_EMAIL_REQUIRED_ORG, SEND_TRIPS_ENDED_EMAIL
from utils.read_data import convert_dt_to_another_tz


logger = logging.getLogger(__name__)


def create_email_content(org: Organization, email) -> dict:
    return {"org_name": org.name, "users_allowed_limit": org.limit.get("member"), "email": email}


def send_limit_exceeded_notification(org: Organization, user) -> bool:

    subject = f"Users Limit Exceeded for {org.name} | Empfly"
    content = create_email_content(org, user.email)
    email_recipients = ["bs@empfly.com", "mk@peerxp.com"]

    try:
        email_template_name = "organization/email/limit_exceeded.html"
        email_message = render_to_string(email_template_name, content)
    except Exception as e:
        logger.error(e)
        logger.exception(
            f"Add exception for {e.__class__.__name__} in send_limit_exceeded_notification"
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
            f"Add exception for {e.__class__.__name__} in send_limit_exceeded_notification"
        )

    return False




def send_trip_ended_email(trip) -> bool:
    try:
        if trip.status != "ended":
            return

        org_name = trip.organization.name.lower()

        if END_EMAIL_REQUIRED_ORG not in org_name:
            return

        user_full_name = ""
        system_location_name = ""
        formatted_dt = ""

        assigned_member = trip.assigned_to
        if assigned_member:
            first_name = assigned_member.user.first_name
            last_name = assigned_member.user.last_name

            if first_name:
                user_full_name += first_name
            if last_name:
                user_full_name += f" {last_name}"

        end_system_location = trip.end_location_ptr

        if not end_system_location:
            return

        system_location_name = end_system_location.name
        system_location_email = end_system_location.email

        if not system_location_email:
            return

        trip_details = trip.trip_details
        if trip_details.end_scan:
            end_scan_dt = trip_details.end_scan.time

            org_tz = trip.organization.timezone

            # DD-MM-YYYY HH:MM am/pm>
            end_scan_dt = convert_dt_to_another_tz(end_scan_dt)

            try:
                formatted_dt = end_scan_dt.strftime("%d-%m-%y %I:%M %p")
            except Exception as err:
                print(err)
                am_or_pm = end_scan_dt.strftime("%p")
                formatted_dt = f"{end_scan_dt.day}-{end_scan_dt.month}-{end_scan_dt.year} {end_scan_dt.hour}:{end_scan_dt.minute} {am_or_pm}"

        content = {
            "system_location": system_location_name,
            "username": user_full_name,
            "completed_at": formatted_dt
        }

        print(content)

        subject = "Site visit completion notification via Empfly"
        # email_recipients = [SEND_TRIPS_ENDED_EMAIL]
        email_recipients = [system_location_email]

        try:
            email_template_name = "organization/email/trip_ended.html"
            email_message = render_to_string(email_template_name, content)
        except Exception as e:
            logger.error(e)
            logger.exception(
                f"Add exception for {e.__class__.__name__} in send_trip_ended_email"
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
                f"Add exception for {e.__class__.__name__} in send_limit_exceeded_notification"
            )

        return False
    except Exception as err:
        logger.error(err)
        logger.exception(
            f"Add exception for {err.__class__.__name__} in send_trip_ended_email"
        )
        return False
