from django.core.exceptions import ValidationError
from account.models import User
from member.models import Member, MemberImage
from organization.models import Organization, Role
from member.serializers import TempProfileSerializer

import numpy as np
import PIL.Image
import PIL.ImageOps

import face_recognition

import json
from uuid import uuid4
import logging


logger = logging.getLogger(__name__)


# * General


def get_user(user_uuid: uuid4) -> User:

    try:
        return User.objects.get(uuid=user_uuid)
    except (User.DoesNotExist, ValidationError) as e:
        logger.error(e)
        return None
    except Exception as e:
        logger.exception(f"Add exception for {e.__class__.__name__} in get_user")
        logger.error(e)
        return None


def get_organization(user: User, organization_uuid: uuid4) -> Organization:

    if organization_uuid is None:
        try:
            member = Member.objects.get(user=user)
        except Member.DoesNotExist as e:
            logger.error("Member not foud -> get_organization")
        return member.organization

    try:
        organization = Organization.objects.get(uuid=organization_uuid)
    except (Organization.DoesNotExist, ValidationError) as e:
        logger.error(e)
        return None
    except Exception as e:
        logger.exception(f"Add exception for {e.__class__.__name__} in get_organization")
        logger.error(e)
        return None

    if organization.members.filter(user=user).exists():
        return organization
    else:
        logger.exception(f"{user} provided another organization's uuid")
        return None


# get organization details using member model
def get_organization2(user: User) -> Organization:
    try:
        member = Member.objects.get(user=user)
    except Member.DoesNotExist as e:
        logger.error("Member not foud -> get_organization")
    return member.organization


def get_member(user: User, organization_uuid: uuid4) -> Member:
    try:
        return Member.objects.get(user=user, organization__uuid=organization_uuid)
    except Member.DoesNotExist as e:
        logger.error("Member not foud -> get_member")
        logger.error(e)
        return None
    except Exception as e:
        logger.exception(f"Add exception for {e.__class__.__name__} in get_member")
        logger.error(e)
        return None


def get_member_by_uuid(
    org_uuid: uuid4,
    uuid: uuid4,
) -> Member:
    """Returns a user's associated Member object

    Args:
        user (model): User object

    Returns:
        Model: Member object
    """
    try:
        return Member.objects.get(uuid=uuid, organization__uuid=org_uuid)
    except (Member.DoesNotExist, ValidationError, ValueError) as e:
        logger.error("Member not foud -> get_member_by_uuid")
        logger.error(e)
    except Exception as e:
        logger.exception(
            f"Add exception for {e.__class__.__name__} in get_member_by_uuid"
        )
    return None


def get_user_data(user: User) -> dict:

    data = {
        "uuid": user.uuid,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "timezone": user.profile.timezone,
        "avatar_url": None,
        "organizations": [],
        "last_accessed_organization": None,
    }

    organization_ids = Member.objects.filter(user=user).values_list(
        "organization__id", flat=True
    )
    organizations = Organization.objects.filter(id__in=organization_ids)

    organization_list = []
    for organization in organizations:

        organization_dict = {
            "uuid": organization.uuid,
            "name": organization.name,
        }
        organization_list.append(organization_dict)

    data["organizations"] = organization_list

    return data


# * Role


def get_member_role() -> Role:
    role, created = Role.objects.get_or_create(name="member")
    return role


def get_finance_role() -> Role:
    role, created = Role.objects.get_or_create(name="finance")
    return role


def get_admin_role() -> Role:
    role, created = Role.objects.get_or_create(name="admin")
    return role


# * Permission


def has_access(
    organization_uuid: uuid4,
    requesting_user: User,
    resouce_type: str,
    resource: "Model",
) -> bool:
    """ Check member have the access to view.
    """

    requesting_member = get_member(requesting_user, organization_uuid)
    if requesting_member is None:
        return False

    if resouce_type == "member":
        try:
            if (
                requesting_member.id != resource.id
                and is_admin(requesting_member) is False
            ):
                return False
            return True
        except Exception as e:
            logger.exception(f"Add exception for {e.__class__.__name__} in has_access")
            logger.error(e)
            return False

    if resouce_type == "trip":
        try:
            if (
                resource.assigned_to != requesting_member
                and resource.created_by != requesting_member
                and requesting_member.role == get_member_role()
            ):
                return False
            return True
        except Exception as e:
            logger.exception(f"Add exception for {e.__class__.__name__} in has_access")
            logger.error(e)
            return False

    return False


def is_admin(member: Member) -> bool:
    if member.role == get_admin_role():
        return True
    return False


def is_finance(member: Member) -> bool:
    if member.role == get_finance_role():
        return True
    return False


def is_admin_or_finance(member: Member) -> bool:
    if member.role == get_admin_role() or member.role == get_finance_role():
        return True
    return False


# * Face Recognition


def exif_transpose(img):
    if not img:
        return img

    exif_orientation_tag = 274

    # Check for EXIF data (only present on some files)
    if (
        hasattr(img, "_getexif")
        and isinstance(img._getexif(), dict)
        and exif_orientation_tag in img._getexif()
    ):
        exif_data = img._getexif()
        orientation = exif_data[exif_orientation_tag]

        # Handle EXIF Orientation
        if orientation == 1:
            # Normal image - nothing to do!
            pass
        elif orientation == 2:
            # Mirrored left to right
            img = img.transpose(PIL.Image.FLIP_LEFT_RIGHT)
        elif orientation == 3:
            # Rotated 180 degrees
            img = img.rotate(180)
        elif orientation == 4:
            # Mirrored top to bottom
            img = img.rotate(180).transpose(PIL.Image.FLIP_LEFT_RIGHT)
        elif orientation == 5:
            # Mirrored along top-left diagonal
            img = img.rotate(-90, expand=True).transpose(PIL.Image.FLIP_LEFT_RIGHT)
        elif orientation == 6:
            # Rotated 90 degrees
            img = img.rotate(-90, expand=True)
        elif orientation == 7:
            # Mirrored along top-right diagonal
            img = img.rotate(90, expand=True).transpose(PIL.Image.FLIP_LEFT_RIGHT)
        elif orientation == 8:
            # Rotated 270 degrees
            img = img.rotate(90, expand=True)

    return img


def load_image_file(file, mode="RGB"):

    img = PIL.Image.open(file)

    if hasattr(PIL.ImageOps, "exif_transpose"):
        # Very recent versions of PIL can do exit transpose internally
        img = PIL.ImageOps.exif_transpose(img)
    else:
        # Otherwise, do the exif transpose ourselves
        img = exif_transpose(img)

    img = img.convert(mode)

    return np.array(img)


def get_image_encoding(image: "Image") -> np.ndarray:
    """ Get image encoding for face rec.
    """

    image = load_image_file(image)
    try:
        return face_recognition.face_encodings(image)[0]
    except IndexError as e:
        logger.error(f"{e}. No face detected")
        return []
    except Exception as e:
        logger.error(e)
        logger.exception(
            f"Add exception for {e.__class__.__name__} in get_image_encoding"
        )
        return []


def convert_encoding_to_json(encoding: np.ndarray) -> json:
    """Converts encoding to JSON

    Args:
        encoding (np.ndarray): Image encoding matrix

    Returns:
        JSON: JSON representation of image encoding
    """

    # Converts numpy array to python list
    encoding_arr = encoding.tolist()
    # Converts encoding to JSON
    json_data = json.dumps(encoding_arr)
    # Returns JSON object
    return json_data


def get_face_encodings(queryset: "Queryest") -> list:
    """ Get face enc data from member image model
    """

    encodings = []
    for member_image in queryset:
        encoding = np.asarray(json.loads(member_image.encoding))
        encodings.append(encoding)
    return encodings


def get_user_ids(queryset: "Queryset") -> list:
    """ Get user model id from member images model
    """

    user_ids = []
    for member_image in queryset:
        user_id = str(member_image.member.user.id)
        user_ids.append(user_id)
    return user_ids


def identify_face(org_uuid: uuid4, face_encoding: list, actual_user_id: int) -> bool:
    """ Identify face for trip scan
    """

    if len(face_encoding) == 0:
        return False

    member_images = MemberImage.objects.filter(member__organization__uuid=org_uuid)
    # Get encodings from MemberImages
    known_face_encodings = get_face_encodings(member_images)
    # Get corresponding User IDs of MemberImages
    known_face_ids = get_user_ids(member_images)

    matches = face_recognition.compare_faces(
        known_face_encodings, face_encoding, tolerance=0.4
    )
    user_id = None

    # Check if the face's encodings matches with any in the database
    face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)
    best_match_index = np.argmin(face_distances)
    if matches[best_match_index]:
        try:
            user_id = known_face_ids[best_match_index]
            return actual_user_id == int(user_id)
        except (TypeError, IndexError) as e:
            logger.error(e)
            return False
    return False


def get_user_and_profile_data(riders):
    """ Get user profile data for report page.
    """
    user_deials = []

    rider_id = []
    rider_with_count = {}
    for rider in riders:
        rider_id.append(rider["assigned_to"])
        rider_with_count[rider["assigned_to"]] = rider["count"]

    members = Member.objects.select_related(
            "user"
        ).prefetch_related(
            "profile"
        ).filter(id__in=rider_id)

    for member in members:
        temp = {}
        try:
            profile = TempProfileSerializer(member.profile, fields=["photo"]).data
            temp["count"] = rider_with_count[member.id]
            temp["profile"] = profile
            temp["user_details"] = {
                "username": member.user.username,
                "first_name": member.user.first_name,
                "last_name" : member.user.last_name,
                "email": member.user.email
            }
            user_deials.append(temp)
        except Member.DoesNotExist as e:
            logger.error(e)


    return user_deials



def identify_face_for_fr(org_uuid: uuid4, face_encoding: list, actual_user_id: int) -> bool:
    """ Identify face for trip scan
    """

    if len(face_encoding) == 0:
        return False

    member_images = MemberImage.objects.filter(
        member__organization__uuid=org_uuid, member__user__id=actual_user_id
    )
    # Get encodings from MemberImages
    known_face_encodings = get_face_encodings(member_images)
    # Get corresponding User IDs of MemberImages
    known_face_ids = get_user_ids(member_images)

    matches = face_recognition.compare_faces(
        known_face_encodings, face_encoding, tolerance=0.4
    )
    user_id = None

    # Check if the face's encodings matches with any in the database
    face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)
    best_match_index = np.argmin(face_distances)
    if matches[best_match_index]:
        try:
            user_id = known_face_ids[best_match_index]
            return actual_user_id == int(user_id)
        except (TypeError, IndexError) as e:
            logger.error(e)
            return False
    return False
