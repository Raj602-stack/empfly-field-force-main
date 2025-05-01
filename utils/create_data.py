from django.http import HttpResponse
from django.contrib.auth import logout
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import Q
from django.utils import crypto

from account.models import User
from member.models import Member
from organization.models import Department, Designation, Organization, OrganizationLocation, Role
from utils import email_funcs, fetch_data
from organization.models import Role

from six import text_type
import csv
import datetime as dt
import secrets
import time
import pandas as pd
import logging


logger = logging.getLogger(__name__)


def generate_token(length: int = 8) -> str:
    token = secrets.token_hex(length)
    return token[:length]


def generate_random_string(length: int = 6) -> str:
    """ Used for name files like csv files.
    """
    return crypto.get_random_string(length)


def generate_hash_value(user: User) -> str:

    timestamp = time.time()
    return text_type(user.uid) + text_type(timestamp) + text_type(user.email)


def create_organization(
    name: str,
) -> Organization:
    """ Create org
    """

    unique = False
    while unique is False:
        domain = generate_random_string(12)
        try:
            org = Organization.objects.create(name=name, domain=domain)
        except (IntegrityError) as e:
            logger.error(e)
        except Exception as e:
            logger.exception(
                f"Add exception for {e.__class__.__name__} in"
                "UserRegistrationAPIView > creating organization"
            )
            logger.error(e)

        unique = True

    return org

def validate_and_update_user(value, field_name:str=None, user_obj=None) -> bool:
    """ Update user model. Using import member csv we utilize this func.
    """
    value_type = type(value)

    if field_name == "phone_number":
        try:
            int(value)
            value_type = int
        except:
            pass
        
    if field_name == "email" and  value_type == str and value.strip() != "" :
        return not User.objects.filter(email=value).exists()
    elif value_type == str and value.strip() != "":
        return True 
    elif field_name == "phone_number" and value_type == int:
        return not User.objects.filter(phone_number=value).exists()

def create_user(email: str, phone_number: str, first_name: str, last_name: str, user_obj=None) -> User:
    if not user_obj and not email and not phone_number:
        raise ValidationError

    create = False
    if user_obj:
        user=user_obj 
    else:
        user =  User.objects.filter(Q(email=email) | Q(phone_number=phone_number))
   
    if not user_obj:
        if user.exists():
            user = user.first()
        else:
            user = User.objects.create(email=email)
            create = True

    # if created:
    #     user.first_name = first_name
    #     user.last_name = last_name
    #     if not User.objects.filter(phone_number=phone_number).exist():
    #         user.phone_number = phone_number
    #     user.save()
    #     email_funcs.send_activation_mail(user)
    # if user:
    #     if validate_and_update_user(first_name):
    #         user.first_name = first_name
    #     if validate_and_update_user(last_name):
    #         user.last_name = last_name
    #     if validate_and_update_user(phone_number):
    #         user.first_name = first_name
    #     if validate_and_update_user(email):
    #         user.email = email

    if validate_and_update_user(first_name):
        user.first_name = first_name
    if validate_and_update_user(last_name):
        user.last_name = last_name
    if validate_and_update_user(phone_number, "phone_number"):
        user.phone_number = phone_number
    if validate_and_update_user(email, "email"):
        user.email = email
    user.save()
    
    if create and email:
        email_funcs.send_activation_mail(user)

    return user


def create_member(
    org: Organization,
    user: User,
    role: Role = None, 
    designation = None, 
    department = None,
    org_location = None,
    employee_id = None,
    member_obj=None,
    manager_email=None,
    member_role=None
) -> Member:
    """ Create member in member upload csv.
    """

    create = False
    if not member_obj:
        # Create member

        if role is None:
            role = fetch_data.get_member_role()

        member = Member.objects.filter(Q(organization=org) & Q(user=user))
        if member.exists():
            logger.warning(f"Member for {user} already exists in {org}")
            member =  member.first()
        else:
            member = Member.objects.create(organization=org, user=user, role=role)
            create = True
    else:
        # update member
        member=member_obj

    # Add or Update department, designation, org location.
    if designation:
        member.designation = designation
    if department:
        member.department = department
    if org_location:
        member.organization_location = org_location
    if member_role and type(member_role) == str:
        role = Role.objects.filter(name=member_role.lower())
        if role.exists():
            member.role=role.first()

    # Update  employee_id if changes. Employee id must not be exists for other members.
    if (employee_id or employee_id == 0 ) and not Member.objects.filter(employee_id=employee_id).exists():
        member.employee_id = employee_id

    # Assign manager to member
    if manager_email:
        manager = Member.objects.filter(user__email=manager_email)
        if manager.exists():
            member.manager = manager.first()
            
    member.save()
        
    return member, create

def create_designation(org: Organization, name:str) -> Designation:

    designation = Designation.objects.filter(Q(organization=org) & Q(name=name))
    if designation.exists():
        logger.warning(f"Designation with {name} name already exists in {org}")
        return designation.first()

    designation = Designation.objects.create(
        organization=org, 
        name=name
    )

    return designation




def create_department(org: Organization, name:str, description:str = None) -> Department:

    department = Department.objects.filter(Q(organization=org) & Q(name=name))
    if department.exists():
        logger.warning(f"department with {name} name already exists in {org}")
        return department.first()

    department = Department.objects.create(
        organization=org, 
        name = name
    )

    if description:
        department.description = description
    department.save()

    return department





def convert_string_to_datetime(string: str, format: str = "%Y-%m-%d") -> dt.datetime:
    """ Convert string dt get from frontend to date time obj in python.
    """
    try:
        return dt.datetime.strptime(string, format)
    except Exception as e:
        logger.error(e)
        logger.exception(
            f"Add exception for {e.__class__.__name__} in convert_string_to_datetime"
        )
    return None


def convert_string_to_date(string: str, format: str = "%Y-%m-%d") -> dt.datetime:
    """ Convert string date get from frontend to date obj in python.
    """
    try:
        return dt.datetime.strptime(string, format).date()
    except Exception as e:
        logger.error(e)
        logger.exception(
            f"Add exception for {e.__class__.__name__} in convert_string_to_datetime"
        )
    return None


def convert_string_to_time(string: str, format: str = "%H:%M") -> dt.datetime:
    """ Convert string time get from frontend to time obj in python.
    """
    try:
        return dt.datetime.strptime(string, format).time()
    except Exception as e:
        logger.error(e)
        logger.exception(
            f"Add exception for {e.__class__.__name__} in convert_string_to_datetime"
        )
    return None


def create_csv_response(file_name: str) -> HttpResponse:
    """ Response the csv file after get the poll req.
    """
    response = HttpResponse(content_type="text/csv")
    file_name = f"{file_name}__{time.time()}"
    response["Content-Disposition"] = f'attachment; filename="{file_name}.csv"'
    return response


def create_csv_writer(response: HttpResponse) -> csv.writer:
    """ Return file as csv. For sample csv Purpose we can use this.
    """
    return csv.writer(response)


def create_pandas_dataframe(csv_file) -> pd.DataFrame:
    """ Read csv file get from frontend. Using in export csv.
    """

    try:
        df = pd.read_csv(csv_file, encoding="ISO-8859-1")
        df = df.where(pd.notnull(df), None)
        # Replaces nan values with empty string
        df = df.fillna("")
        return df
    except UnicodeDecodeError as e:
        logger.error(e)
        return None
    except Exception as e:
        logger.error(e)
        logger.exception(
            f"Add exception for {e.__class__.__name__} in create_pandas_dataframe"
        )
        return None




def create_org_location(org: Organization, name:str) -> OrganizationLocation:

    org_location = OrganizationLocation.objects.filter(Q(organization=org) & Q(name=name))
    if org_location.exists():
        logger.warning(f"org_location with {name} name already exists in {org}")
        return org_location.first()

    org_location = OrganizationLocation.objects.create(
        organization=org, 
        name = name
    )


    return org_location




def modify_member_model_data(
    filter_ins : "Object", 
    member:Member,
    Modal : "Modal_Object",
    organization : Organization,
    name = "",
    curr_val : str = "",
    field_name : str = "",
    bulk_update : bool = False,
):

    """Update member.used in upload member csv"""
    name_is_valid = True
    is_bulk_upload_have_obj = False
    if name and isinstance(name, str) and name.strip() and name != "NA":
        # print(name, "is valid")
        obj = filter_ins.filter(name=name.strip())
        # print(obj, "obj===")
        if obj.exists():
            obj = obj.first()
            is_bulk_upload_have_obj = True
        elif bulk_update:
            obj = None
        elif not bulk_update:
            obj = Modal.objects.create(name=name, organization=organization)
        # print(obj)
    else:
        name_is_valid = False
        obj = None

    # print(obj)

    logger.error(f"name = {name}, obj = {obj}, curr_val ={curr_val}, field_name = {field_name}, bulk_update={bulk_update}")
    
    # field name used for know which field we want to update
    if field_name == "department":
        if  obj:
            member.department = obj
        elif bulk_update and not is_bulk_upload_have_obj and name:
            pass
        elif name in ("", "NA"):
            member.department = None


    elif field_name == "designation":
        if  obj:
            member.designation = obj
        elif bulk_update and not is_bulk_upload_have_obj and name:
            pass
        elif name in ("", "NA"):
            member.designation = None

    elif field_name == "organization_location":
        if  obj:
            member.organization_location = obj
        elif bulk_update and not is_bulk_upload_have_obj and name:
            pass
        elif name in ("", "NA"):
            member.organization_location = None


def validate_and_save_user(
    all_users,
    user:User,
    email="",
    phone_number="",
    first_name="",
    last_name="",
    is_bulk_update=False
):
    """validate user object"""

    is_stripped = False
    if isinstance(email, str):
        is_stripped = True
        email = email.strip()

    if email and  email not in  ("", "NA") and is_stripped and isinstance(email, str) and (not all_users.filter(email=email).exists()):
        user.email = email.strip()

    if not phone_number or phone_number in  ("", "NA"):
        user.phone_number = None
    elif phone_number and phone_number.isdigit() and not all_users.filter(phone_number=phone_number).exists():
        user.phone_number = phone_number

    # if not first_name or first_name in ("", "NA"):
    #     user.first_name = None
    # else:
    #     user.first_name = first_name
    if first_name:
        user.first_name = first_name

    if not last_name or last_name in ("", "NA"):
        user.last_name = None
    else:
        user.last_name = last_name
    user.save()
