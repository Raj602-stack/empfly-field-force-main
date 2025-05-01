from member.models import Member, MemberImage, Profile
from account.serializers import UserSerializer
from organization.serializers import (
    OrganizationLocationSerializer,
    RoleSerializer,
    OrganizationSerializer,
    DesignationSerializer,
    DepartmentSerializer,
)
from serializers.dynamic_serializers import DynamicFieldsModelSerializer

class TempProfileSerializer(DynamicFieldsModelSerializer):
    class Meta:
        model = Profile
        exclude = ["id"]

class TempMemberSerializer(DynamicFieldsModelSerializer):

    user = UserSerializer()
    role = RoleSerializer()
    profile = TempProfileSerializer(fields=["photo"])

    class Meta:
        model = Member
        fields = "__all__"


class MemberSerializer(DynamicFieldsModelSerializer):

    user = UserSerializer()
    role = RoleSerializer()
    organization = OrganizationSerializer()
    manager = TempMemberSerializer()
    designation = DesignationSerializer()
    department = DepartmentSerializer()
    organization_location = OrganizationLocationSerializer()
    profile = TempProfileSerializer()

    class Meta:
        model = Member
        fields = "__all__"


class TempMemberSerializer(DynamicFieldsModelSerializer):

    user = UserSerializer()
    role = RoleSerializer()
    organization = OrganizationSerializer()
    manager = UserSerializer()

    class Meta:
        model = Member
        fields = "__all__"


class ProfileSerializer(DynamicFieldsModelSerializer):

    member = MemberSerializer(exclude=["organization"])

    class Meta:
        model = Profile
        fields = "__all__"


class MemberImageSerializer(DynamicFieldsModelSerializer):

    member = MemberSerializer()

    class Meta:
        model = MemberImage
        fields = "__all__"


class MinimalMemberSerializer(DynamicFieldsModelSerializer):

    user = UserSerializer()

    class Meta:
        model = Member
        fields = ["uuid", "user"]
