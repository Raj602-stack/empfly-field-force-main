from django.core.management.base import BaseCommand

from account.models import User, AuthToken
from member.models import Member
from organization.models import Organization, Role


class Command(BaseCommand):

    help = "View UUIDs of objects"

    def handle(self, *args, **kwargs):

        print("USERS")
        for user in User.objects.all():
            print(f"{user.email} ----- {user.uuid}")

        print("\n\nMEMBERS")
        for member in Member.objects.all():
            print(f"{member.user.email} ----- {member.user.uuid}")

        print("\n\nORGANIZATIONS")
        for org in Organization.objects.all():
            print(f"{org.name} ----- {org.uuid}")
