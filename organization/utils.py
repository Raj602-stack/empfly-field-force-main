from django.core.exceptions import ValidationError

from organization.models import (
    Department,
    Designation,
    Fuel,
    Location,
    Organization,
    OrganizationLocation,
    RideExpenseCostMatrix,
    Role,
    Vehicle,
)
from form_builder.models import CreateTripFormConfig
from uuid import uuid4
import logging

logger = logging.getLogger(__name__)


def get_role(uuid: uuid4) -> Role:

    try:
        return Role.objects.get(uuid=uuid)
    except (ValidationError, Role.DoesNotExist) as e:
        logger.error(e)
    except Exception as e:
        logger.error(e)
        logger.exception(f"Add exception for {e.__class__.__name__} in get_role")
    return None


def get_location(org_uuid: uuid4, uuid: uuid4) -> Location:

    try:
        return Location.objects.get(organization__uuid=org_uuid, uuid=uuid)
    except (Location.DoesNotExist, ValidationError, ValueError) as e:
        logger.error(e)
    except Exception as e:
        logger.exception(f"Add exception for {e.__class__.__name__} in get_location")
    return None


def get_organization_location(uuid: uuid4) -> OrganizationLocation:
    try:
        return OrganizationLocation.objects.get(uuid=uuid)
    except (OrganizationLocation.DoesNotExist, ValidationError, ValueError) as e:
        logger.error(e)
    except Exception as e:
        logger.exception(
            f"Add exception for {e.__class__.__name__} in get_organization_location"
        )
    return None


def get_fuel(org_uuid: uuid4, uuid: uuid4) -> Fuel:

    try:
        return Fuel.objects.get(organization__uuid=org_uuid, uuid=uuid)
    except (Fuel.DoesNotExist, ValidationError, ValueError) as e:
        logger.error(e)
    except Exception as e:
        logger.exception(f"Add exception for {e.__class__.__name__} in get_fuel")
    return None


def get_vehicle(org_uuid: uuid4, uuid: uuid4) -> Vehicle:

    try:
        return Vehicle.objects.get(organization__uuid=org_uuid, uuid=uuid)
    except (Vehicle.DoesNotExist, ValidationError, ValueError) as e:
        logger.error(e)
    except Exception as e:
        logger.exception(f"Add exception for {e.__class__.__name__} in get_vehicle")
    return None


def get_cost_matrix(org_uuid: uuid4, uuid: uuid4) -> RideExpenseCostMatrix:

    try:
        return RideExpenseCostMatrix.objects.get(organization__uuid=org_uuid, uuid=uuid)
    except (RideExpenseCostMatrix.DoesNotExist, ValidationError, ValueError) as e:
        logger.error(e)
    except Exception as e:
        logger.exception(f"Add exception for {e.__class__.__name__} in get_cost_matrix")
    return None


def get_department(org_uuid: uuid4, department_uuid: uuid4) -> Department:

    try:
        return Department.objects.get(uuid=department_uuid, organization__uuid=org_uuid)
    except (Department.DoesNotExist, ValidationError, ValueError) as e:
        logger.error(e)
    except Exception as e:
        logger.exception(f"Add exception for {e.__class__.__name__} in get_department")
    return None


def get_designation(org_uuid: uuid4, designation_uuid: uuid4) -> Designation:

    try:
        return Designation.objects.get(
            uuid=designation_uuid, organization__uuid=org_uuid
        )
    except (Designation.DoesNotExist, ValidationError, ValueError) as e:
        logger.error(e)
    except Exception as e:
        logger.exception(f"Add exception for {e.__class__.__name__} in get_designation")
    return None


def is_allowed_to_add_members(org: Organization) -> bool:
    """ Org have limit to add member. Using identify the count is passed.
    """
    member_limit = org.limit.get("member")
    all_org_member = org.members.all()
    all_org_active_member = all_org_member.filter(user__is_active=True)
    if member_limit != 0 and all_org_active_member.count() >= member_limit:
        return False
    return True

def get_create_trip_config_field(org_uuid: uuid4, department_uuid: uuid4) -> Designation:

    try:
        return CreateTripFormConfig.objects.get(
            department__uuid=department_uuid, organization__uuid=org_uuid
        )
    except Designation.DoesNotExist as err:
        print(err)
        return
    return
