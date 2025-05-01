""" Constants values used in form_builder apps
"""
from utils.response import HTTP_200, HTTP_400
import re


FIELD_REPORT_FORM_CONFIG_FIELDS = [
    "field_1",
    "field_2",
    "field_3",
    "field_4",
    "field_5",
    "field_6",
    "field_7",
    "field_8",
    "field_9",
    "field_10",
    "field_11",
    "field_12",
    "field_13",
    "field_14",
    "field_15",
    "field_16",
    "field_17",
    "field_18",
    "field_19",
    "field_20",
]


FIELD_REPORT_FORM_CONFIG_FIELDS_VALUES = ("label", "constraint", "required")

FIELD_CONFIG_VALUE_CONSTRAINT = ("is_number", "is_email", "all")

FIELD_CONFIG_FIELD_TYPES = ("text", "dropdown")

FIELD_CONFIG_DEFAULT_VALUES = ("required", "label")

FIELD_CONFIG_TYPE_WITH_REQUIRED_FIELDS = {
    "dropdown": (*FIELD_CONFIG_DEFAULT_VALUES, "type", "options"),
    "text": (*FIELD_CONFIG_DEFAULT_VALUES, "constraint", "type"),
    "attachment": (*FIELD_CONFIG_DEFAULT_VALUES, "max_file_count")
}

FIELD_REPORT_FILE_ALLOWED_EXT = [".jpg", ".jpeg", ".png", ".pdf"]

FIELD_REPORT_FILE_ALLOWED_EXT_IN_STR = ", ".join(FIELD_REPORT_FILE_ALLOWED_EXT)


def validate_max_file_size(size):
    if isinstance(size, int) is False:
        return HTTP_400("max_file_size must be an integer."), True

    if not (size > 0 and size <= 50):
        return HTTP_400("max_file_size value must less than 50 MB."), True

    return None, False
    # return response.HTTP_400(
    #     f"Value must be is_email/is_number/is_text for {field_key} in {field_name}."
    # )


FIELD_CONFIG_MIN_FILE_COUNT = 1
FIELD_CONFIG_MAX_FILE_COUNT = 10


def validate_max_file_count(size):
    """
        response and is_res. is_res is used for check we are sending respone.
    """
    if isinstance(size, int) is False:
        return HTTP_400("max_file_size must be an integer."), True

    if not (size >= FIELD_CONFIG_MIN_FILE_COUNT and size <= FIELD_CONFIG_MAX_FILE_COUNT):
        return HTTP_400(f"max_file_count value must withing {FIELD_CONFIG_MIN_FILE_COUNT} to {FIELD_CONFIG_MAX_FILE_COUNT}."), True

    return None, False
    # return response.HTTP_400(
    #     f"Value must be is_email/is_number/is_text for {field_key} in {field_name}."
    # )


# Create trip config
CREATE_TRIP_CONFIG_FIELDS = [
    "field_1",
    "field_2",
    "field_3",
    "field_4",
    "field_5",
    "field_6",
    "field_7",
    "field_8",
    "field_9",
    "field_10",
]

CREATE_TRIP_FIELD_REPORT_FORM_CONFIG_FIELDS_VALUES = (
    "label", "constraint", "required")


CREATE_TRIP_FORM_CONFIG_FIELDS_VALUES = ("label", "constraint", "required")

CREATE_TRIP_CONFIG_VALUE_CONSTRAINT = (
    "is_number", "is_email", "all", "is_url")

CREATE_TRIP_CONFIG_FIELD_TYPES = ("text", "dropdown")

CREATE_TRIP_CONFIG_DEFAULT_VALUES = ("required", "label")

CREATE_TRIP_CONFIG_TYPE_WITH_REQUIRED_FIELDS = {
    "dropdown": (*FIELD_CONFIG_DEFAULT_VALUES, "type", "options"),
    "text": (*FIELD_CONFIG_DEFAULT_VALUES, "constraint", "type"),
}

EMAIL_REGEX = re.compile(r"[^@]+@[^@]+\.[^@]+")

# Regex to check valid URL
URL_REGEX = re.compile(
    r"((http|https)://)(www.)?" + "[a-zA-Z0-9@:%._\\+~#?&//=]" + "{2,256}\\.[a-z]" + "{2,6}\\b([-a-zA-Z0-9@:%" + "._\\+~#?&//=]*)"
)



# Create trip config
ADMIN_REPORT_CONFIG_FIELDS = [
    "field_1",
    "field_2",
    "field_3",
    "field_4",
    "field_5",
    "field_6",
    "field_7",
    "field_8",
    "field_9",
    "field_10",
]

ADMIN_REPORT_FIELD_REPORT_FORM_CONFIG_FIELDS_VALUES = (
    "label", "constraint", "required"
)


ADMIN_REPORT_FORM_CONFIG_FIELDS_VALUES = ("label", "constraint", "required")

ADMIN_REPORT_CONFIG_VALUE_CONSTRAINT = (
    "is_number", "is_email", "is_url", "all"
)

ADMIN_REPORT_CONFIG_FIELD_TYPES = ("text", "dropdown")

ADMIN_REPORT_CONFIG_DEFAULT_VALUES = ("required", "label")

ADMIN_REPORT_CONFIG_TYPE_WITH_REQUIRED_FIELDS = {
    "dropdown": (*FIELD_CONFIG_DEFAULT_VALUES, "type", "options"),
    "text": (*FIELD_CONFIG_DEFAULT_VALUES, "constraint", "type"),
}

EMAIL_REGEX = re.compile(r"[^@]+@[^@]+\.[^@]+")

# Regex to check valid URL
URL_REGEX = re.compile(
    r"((http|https)://)(www.)?" + "[a-zA-Z0-9@:%._\\+~#?&//=]" + "{2,256}\\.[a-z]" + "{2,6}\\b([-a-zA-Z0-9@:%" + "._\\+~#?&//=]*)"
)

CREATE_TRIP_FORM_CONFIG_FIELDS = [
    "field_1",
    "field_2",
    "field_3",
    "field_4",
    "field_5",
    "field_6",
    "field_7",
    "field_8",
    "field_9",
    "field_10",
]
