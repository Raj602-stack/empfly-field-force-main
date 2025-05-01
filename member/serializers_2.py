from member.models import Member
from account.serializers import UserSerializer
from serializers.dynamic_serializers import DynamicFieldsModelSerializer


class MinimalMemberSerializer(DynamicFieldsModelSerializer):

    user = UserSerializer(fields=["first_name", "last_name", "phone_number", "email"])

    class Meta:
        model = Member
        fields = ["uuid", "user"]
