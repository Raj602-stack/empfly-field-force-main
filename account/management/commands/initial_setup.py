from django.core.management.base import BaseCommand

from account.models import User
from organization.models import Organization, Role
from member.models import Member


class Command(BaseCommand):
    """ Create org and user using manage.py command.
    """
    help = "Closes the specified poll for voting"

    def add_arguments(self, parser):
        # Param send in manage.py command.
        parser.add_argument("organization_name", type=str)
        parser.add_argument("first_name", type=str)
        parser.add_argument("last_name", type=str)
        parser.add_argument("email", type=str)

    def handle(self, *args, **kwargs):

        # take values from arguments
        organization_name = kwargs.get("organization_name", None)
        first_name = kwargs.get("first_name", None)
        last_name = kwargs.get("last_name", None)
        email = kwargs.get("email", None)

        try:
            # create organization
            organization, _ = Organization.objects.get_or_create(name=organization_name)

            # create roles
            roles = ["admin", "finance", "member"]
            for role in roles:
                object, _ = Role.objects.get_or_create(name=role)

            # create user
            user = User.objects.create(
                email=email,
                first_name=first_name,
                last_name=last_name
            )
            user.is_active = True
            user.is_superuser = True
            user.is_staff = True
            user.set_password("password")
            user.save()

            admin_role, _ = Role.objects.get_or_create(name="admin")

            # create member
            member, _ = Member.objects.get_or_create(user=user, organization=organization, role=admin_role)
            member.save()

        except Exception as error:
            print(error.__class__.__name__, error)
