from account.models import User
from serializers.dynamic_serializers import DynamicFieldsModelSerializer


class UserSerializer(DynamicFieldsModelSerializer):
    class Meta:
        model = User
        fields = ["uuid", "email", "first_name", "last_name", "phone_number", "is_active"]
