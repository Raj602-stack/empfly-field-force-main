from copyreg import add_extension
import logging
import secrets
import uuid

from account.models import SessionToken, User
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from rest_framework.response import Response

logger = logging.getLogger(__name__)


def create_email_content(
    user: User, set_token: bool = True, set_uuid: bool = True
) -> dict:
    """Creates dictionary to be used in email template

    Args:
        user (Model): User object
        token (bool, optional): Determines if token should be created.
                                Defaults to True.
        uuid (bool, optional): Determines if uuid should be created.
                              Defaults to True.

    Returns:
        dict: Dictionary containing data for email templates
    """

    token, uuid = None, None

    if set_token:
        token = secrets.token_urlsafe()
        SessionToken.objects.create(user=user, token=token)

    if set_uuid:
        uuid = user.uuid

    return {
        "email": user.email,
        "domain": settings.UI_DOMAIN_URL,
        "user": user,
        "token": token,
        "uuid": uuid,
    }


def send_activation_mail(user: User) -> bool:
    """ Send email when user is created.
    """

    subject = "Activate Your Account | Empfly"
    content = create_email_content(user)
    email_template_name = "account/email/user/user-activation.html"
    # Create email template
    email = render_to_string(email_template_name, content)

    try:
        # Send mail to user
        send_mail(
            subject,
            "",
            settings.EMAIL_SENDER,
            [user.email],
            fail_silently=False,
            html_message=email,
        )
        logger.info("Succesfully sent email")
        return True
    except Exception as e:
        logger.error(e)
        logger.exception(
            f"Add exception for {e.__class__.__name__} in send_activation_mail"
        )
        return False


def send_confirmation_mail(user: User):
    """ After user set pwd for account send confirmation email.
    """

    subject = "Account Activated | Empfly"
    content = create_email_content(user, set_token=False, set_uuid=False)
    email_template_name = "account/email/user/user-activation-confirmation.html"
    # Create email template
    email = render_to_string(email_template_name, content)

    try:
        # Send email to user
        send_mail(
            subject,
            "",
            settings.EMAIL_SENDER,
            [user.email],
            fail_silently=False,
            html_message=email,
        )
        logger.info("Succesfully sent email")
        return True
    except Exception as e:
        logger.error(e)
        logger.exception(
            f"Add exception for {e.__class__.__name__} in send_confirmation_mail"
        )
        return False


def send_password_reset_mail(user):
    """ Forgot pwd email.
    """

    subject = "Reset Your Password | Empfly"
    content = create_email_content(user)
    email_template_name = "account/email/user/password-reset.html"
    # Create email template
    email = render_to_string(email_template_name, content)

    try:
        # Send mail to user
        send_mail(
            subject,
            "",
            settings.EMAIL_SENDER,
            [user.email],
            fail_silently=False,
            html_message=email,
        )
        logger.info("Succesfully sent email")
        return True
    except Exception as e:
        logger.error(e)
        logger.exception(
            f"Add exception for {e.__class__.__name__} in send_password_reset_mail"
        )
        return False


def send_password_reset_confirmation_mail(user):

    subject = "Password Reset Successful | Empfly"
    content = create_email_content(user)
    email_template_name = "account/email/user/password-reset-confirmation.html"

    # Create email template
    email = render_to_string(email_template_name, content)

    try:
        # Send mail to user
        send_mail(
            f"{subject}",
            "",
            settings.EMAIL_SENDER,
            [user.email],
            fail_silently=False,
            html_message=email,
        )
        logger.info("Succesfully sent email")
        return True
    except Exception as e:
        logger.error(e)
        logger.exception(
            f"Add exception for {e.__class__.__name__} in send_password_reset_confirmation_mail"
        )
        return False


def send_verification_mail(user: User, email: str, token: bool = None) -> bool:

    subject = "Verify Your Email"

    if token:
        content = create_email_content(user, set_token=False, set_uid=True)
        SessionToken.objects.create(user=user, token=token)
        content["token"] = token
    else:
        content = create_email_content()

    email_template_name = "account/email/user/email-verification.html"
    email_content = render_to_string(email_template_name, content)

    try:
        send_mail(
            f"{subject} | Empfly",
            "",
            settings.EMAIL_SENDER,
            [email],
            fail_silently=False,
            html_message=email_content,
        )
        logger.info("Succesfully sent email")
        return True
    except Exception as e:
        logger.error(e)
        logger.exception(
            f"Add exception for {e.__class__.__name__} in send_verification_mail"
        )
        return False


def send_invitation_mail(user: User, org_uid: uuid.uuid4, org_name: str) -> bool:

    subject = f"Invitation from {org_name} | Empfly"
    content = create_email_content(user, set_uid=True, set_token=False)

    content["org_uid"] = org_uid
    content["org_name"] = org_name

    email_template_name = "account/email/user/user-activation.html"

    # Create email template
    email = render_to_string(email_template_name, content)

    try:
        # Send mail to user
        send_mail(
            subject,
            "",
            settings.EMAIL_SENDER,
            [user.email],
            fail_silently=False,
            html_message=email,
        )
        logger.info("Succesfully sent email")
        return True
    except Exception as e:
        logger.error(e)
        logger.exception(
            f"Add exception for {e.__class__.__name__} in send_invitation_mail"
        )
        return False
