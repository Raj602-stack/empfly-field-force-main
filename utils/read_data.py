from organization.models import Department
from rest_framework import status
from rest_framework.response import Response
from django.utils import timezone
from django.conf import settings
import datetime as dt
import json
import logging
from dateutil import tz
from field_force.settings import APPLICATION_NAME

# cryptography package for encrypt | decrypt
from cryptography.fernet import Fernet

from dateutil import parser

logger = logging.getLogger(__name__)


def get_json(response: Response, default: dict = None) -> dict:
    """Get json from requesting data."""

    try:
        return response.json()
    except json.JSONDecodeError as e:
        logger.error(e)
    except Exception as e:
        logger.error(e)
        logger.exception(f"Add exception for {e.__class__.__name__} in get_json")

    return default


def get_200_delete_response(model: str) -> Response:
    return Response(
        {"message": f"Successfully deleted {model}"},
        status=status.HTTP_200_OK,
    )


def get_404_response(object: str = None) -> Response:
    return Response(
        {"message": f"{object} not found"}, status=status.HTTP_404_NOT_FOUND
    )


def get_403_response(message: str = None) -> Response:
    if message is None:
        message = "You do not have permission to perform this action"
    return Response(
        {"message": message},
        status=status.HTTP_403_FORBIDDEN,
    )


def get_409_response(model: str, field: str = "name") -> Response:
    return Response(
        {
            "message": f"{model} with {field} already exists",
        },
        status=status.HTTP_409_CONFLICT,
    )


# def get_current_datetime() -> "current datetime in UTC":
#     return dt.datetime.now(dt.timezone.utc)


def get_current_datetime() -> dt.datetime:
    # return timezone now datetime
    # datetime.datetime(2022, 7, 13, 23, 38, 11, 386663, tzinfo=zoneinfo.ZoneInfo(key='Asia/Kolkata'))
    return timezone.localtime(timezone.now())


def get_current_datetime_as_str() -> str:
    return get_current_datetime().__str__()


# func conver seconds to Hours:Minutes:Seconds string
def convertSeconds(seconds):
    """Convert seconds to minute. convert minute to hours."""
    min, sec = divmod(seconds, 60)
    hour, min = divmod(min, 60)
    return "%d:%02d:%02d" % (hour, min, sec)


def get_difference_between_datetimes_as_time(
    start_time: dt.datetime, end_time: dt.datetime
) -> dt.datetime.time:

    # start_time = start_time.replace(tzinfo=None)
    # end_time = end_time.replace(tzinfo=None)

    # diff = end_time - start_time
    # days, seconds = diff.days, diff.seconds
    # hours = days * 24 + seconds // 3600
    # minutes = (seconds % 3600) // 60
    # seconds = seconds % 60

    # return dt.datetime.strptime(f"{hours}:{minutes}:{seconds}", "%H:%M:%S").time()

    diff = end_time - start_time

    # print(end_time - start_time, diff.total_seconds())
    # print(diff.total_seconds())

    # convert total seconds to H:M:S string
    return convertSeconds(diff.total_seconds())


# print(get_difference_between_datetimes_as_time(dt.datetime(2022, 7, 14, 18, 00, 00, 000000), dt.datetime(2022, 7, 15, 0, 00, 00, 00000)))


def convert_seconds_to_datetime(seconds: str) -> str:
    try:
        return str(dt.timedelta(seconds=seconds))
    except Exception as e:
        logger.error(e)
        logger.exception(
            f"Add exception for {e.__class__.__name__} in "
            "convert_seconds_to_datetime"
        )
        return None


def get_cipher_key():
    """cipher_key used for encrypt"""
    return bytes(settings.CIPHER_KEY, "utf-8")


def encrypt_text(text):
    """Encrypt API keys."""

    key = get_cipher_key()

    try:
        text = Fernet(key).encrypt(bytes(text, "utf-8")).decode("utf-8")
    except TypeError:
        logging.error(f"Cannot encrypt text of type {type(text)}")
    except Exception as e:
        logging.critical(f"Add exception {e.__class__.__name__} " f"in encrypt_text")
        logging.error(f"Failed to encrypt text: {e}")
        return None

    return text


def decrypt_text(text):

    key = get_cipher_key()

    try:
        text = Fernet(key).decrypt(bytes(text, "utf-8")).decode("utf-8")
    except TypeError:
        logging.error(f"Cannot decrypt text of type {type(text)}")
    except Exception as e:
        logging.critical(f"Add exception {e.__class__.__name__} " f"in decrypt_text")
        logging.error(f"Failed to decrypt text: {e}")
        return None

    return text


def convertGoogleAPIKeyShort(key):
    """ex: 123*********91
    Convert API key into above form.
    """
    middle = len(key) // 3
    temp = [key[:middle], key[middle : middle * 2], key[middle * 2 :]]
    temp[1] = "*" * len(temp[1])
    return "".join(temp)


def extract_data_from_object(query_set, lookup: list) -> str:
    """get specific field from inside the queryset.
    queryset can be any model lookup in the
    relation to that target field
    """
    for field in lookup:
        if not hasattr(query_set, field):
            return
        query_set = getattr(query_set, field)
    return query_set


def extract_data_from_dict(data, lookup: list) -> str:
    """get specific field from inside the queryset.
    queryset can be any model lookup in the
    relation to that target field
    """
    if not isinstance(data, dict):
        return ""

    for field in lookup:
        data = data.get(field)
        if not data:
            return ""

    if not data:
        return ""

    return data


def empty_or_data(data):
    """
    Given data to the fun is null return empty string other wise return the same data
    """
    if data:
        return data

    if data in (0,):
        return data

    return ""


def conv_to_float(value):
    try:
        return float(value), None
    except ValueError:
        return None, ValueError
    except Exception as e:
        print(e)

    return None, None


def string_to_dt(datetime_str):

    try:
        return parser.parse(datetime_str)
    except Exception as err:
        print("Error in string_to_dt function")
        print(err)
    return datetime_str


def remove_dt_millie_sec(date_time: dt):
    """Remove millie sec from date time obj"""
    try:
        print(type(date_time))
        if isinstance(date_time, str):
            date_time = string_to_dt(date_time)
            print("#################################")
            print(date_time)
            print(type(date_time))
        return date_time.replace(microsecond=0)
    except Exception as err:
        print("Error in remove_dt_millie_sec function")
        print(err)

    return date_time


def convert_dt_to_another_tz(
    dt_for_convert: dt.datetime, to_zone: str = "Asia/Kolkata"
):
    """Convert a datetime to diff datetime or tz.

    Args:
        dt_for_convert (datetime): _description_
        to_zone (str, optional): _description_. Defaults to 'Asia/Kolkata'.

    Returns:
        _type_: _description_
    """

    if not dt_for_convert:
        return dt_for_convert
    try:
        to_zone = tz.gettz(to_zone)
        print(f"to_zone: {to_zone}")

        print(f"dt_for_convert tz: {dt_for_convert.astimezone().tzinfo}")

        converted_dt = dt_for_convert.astimezone(to_zone)
        print(f"converted_dt: {converted_dt}")
        print(f"dt_for_convert tz: {converted_dt.astimezone().tzinfo}")
        return converted_dt
    except Exception as err:
        print(err)
        return dt_for_convert


def get_department(uuid, org) -> Department:
    try:
        return Department.objects.get(uuid=uuid, organization=org)
    except Department.DoesNotExist:
        return None


def convert_submission_data_to_str(data):
    if isinstance(data, dict) is False:
        return
    label = data.get("label", "")
    value = data.get("value", "")

    if value:
        str_values = str(value)
        if str_values.endswith(".0") and len(str_values) > 2:
            value = str_values[:-2]

    if value is None:
        value = ""

    return f"{label} && {value}"



def convert_dt_to_another_tz(dt_for_convert: dt.datetime, to_zone : str = 'Asia/Kolkata'):
    """Convert a datetime to diff datetime or tz.

    Args:
        dt_for_convert (datetime): _description_
        to_zone (str, optional): _description_. Defaults to 'Asia/Kolkata'.

    Returns:
        _type_: _description_
    """

    if not dt_for_convert:
        return dt_for_convert

    try:
        to_zone = tz.gettz(to_zone)
        print(f"to_zone: {to_zone}")

        print(f"dt_for_convert tz: {dt_for_convert.astimezone().tzinfo}")

        converted_dt = dt_for_convert.astimezone(to_zone)
        print(f"converted_dt: {converted_dt}")
        print(f"dt_for_convert tz: {converted_dt.astimezone().tzinfo}")
        return converted_dt
    except Exception as err:
        print(err)
        return dt_for_convert


def application_name_is_wrong(request) -> bool:
    """
        For resolving the cross app login issue we are adding this function
        From frontend we will get the application name if that mismatch with
        Our application name in the settings we will throw error
    """
    try:
        requesting_application_name: str = request.data.get("application_name")

        # Application not found
        if not requesting_application_name:
            return False

        if APPLICATION_NAME.lower() == requesting_application_name.lower():
            return False

        return True
    except Exception as err:
        print(err)
        return False
