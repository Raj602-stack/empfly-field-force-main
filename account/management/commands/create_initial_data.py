from django.core.management.base import BaseCommand

from account.models import User, AuthToken
from member.models import Member, Profile
from organization.models import Organization, Role


class Command(BaseCommand):

    help = "Create initial data for Field Force"

    USER_UUIDS = (
        "fe4719b4-fc2d-4e28-ad29-0f5eeb7bcf9c",
        "80aba911-03fb-4647-8ed3-5cfa274b9ecb",
        "a080871e-a138-41d7-8fb3-74730123a466",
        "d378c915-8e98-4e9f-a5ee-05df59b0703a",
    )
    ORG_UUIDS = ("b3f53e54-f256-496d-84c9-48a2fc1baea1",)
    MEMBER_UUIDS = (
        "c493055f-5c46-429a-8d0c-c03af5a78808",
        "83eca79f-2c93-43ef-a0eb-d190c4d96c25",
        "957ffa85-47b1-4fbf-b54c-ffc63085c664",
        "ce9fdfdd-10f4-4c80-b67e-eeee203e769d",
    )

    def create_user(self, email, uuid):

        user = User.objects.create(uuid=uuid, email=email)

        user.is_active = True
        user.is_staff = True
        user.is_superuser = True
        user.set_password("rainpuddle")
        user.save()
        return user

    def create_django_roles(self):
        Role.objects.create(name='member')
        Role.objects.create(name='admin')
        Role.objects.create(name='finance')

    def handle(self, *args, **kwargs):

        self.create_django_roles()

        user1 = self.create_user(
            "admin@peerxp.com",
            self.USER_UUIDS[0],
        )
        user2 = self.create_user(
            "arjun.hm@peerxp.com",
            self.USER_UUIDS[1],
        )
        user3 = self.create_user(
            "mahesh.m@peerxp.com",
            self.USER_UUIDS[2],
        )
        user4 = self.create_user(
            "mehtab.multani@peerxp.com",
            self.USER_UUIDS[3],
        )

        org = Organization.objects.create(
            uuid=self.ORG_UUIDS[0], name="PeerXP", domain="peerxp__12345"
        )

        admin_role = Role.objects.get(name='admin')

        for i, user in enumerate((user2, user3, user4)):
            member = Member.objects.create(
                uuid=self.MEMBER_UUIDS[i + 1], user=user, organization=org,
                role=admin_role
            )
            Profile.objects.create(member=member)

        AuthToken.objects.create(key="123451", user=user1, name="mytoken1")
        AuthToken.objects.create(key="123452", user=user2, name="mytoken2")
        AuthToken.objects.create(key="123453", user=user3, name="mytoken3")
        AuthToken.objects.create(key="123454", user=user4, name="mytoken4")
