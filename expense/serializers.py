from member.serializers import MinimalMemberSerializer
from expense.models import RideExpense, RideExpenseComment, RideExpenseDocs, PaymentMode
from organization.serializers import (
    FuelSerializer,
    OrganizationSerializer,
    VehicleSerializer,
)
from trip.temp_serializers import AlternativeTripSerializer
from serializers.dynamic_serializers import DynamicFieldsModelSerializer


class RideExpenseCommentSerializer(DynamicFieldsModelSerializer):

    member = MinimalMemberSerializer()

    class Meta:
        model = RideExpenseComment
        fields = "__all__"


class RideExpenseDocsSerializer(DynamicFieldsModelSerializer):
    class Meta:
        model = RideExpenseDocs
        fields = "__all__"


class PaymentModeSerializer(DynamicFieldsModelSerializer):

    organization = OrganizationSerializer(fields=["uuid", "name"])

    class Meta:
        model = PaymentMode
        fields = "__all__"


class RideExpenseSerializer(DynamicFieldsModelSerializer):

    fuel = FuelSerializer(fields=["uuid", "name"])
    vehicle = VehicleSerializer(fields=["uuid", "name"])
    payment_mode = PaymentModeSerializer()

    ride_expense_comments = RideExpenseCommentSerializer(many=True)
    ride_expense_docs = RideExpenseDocsSerializer(many=True)
    approved_by = MinimalMemberSerializer()
    reimbursed_by = MinimalMemberSerializer()

    class Meta:
        model = RideExpense
        fields = "__all__"


class RideExpenseAndTripSerializer(DynamicFieldsModelSerializer):

    trip = AlternativeTripSerializer()

    fuel = FuelSerializer(fields=["uuid", "name"])
    vehicle = VehicleSerializer(fields=["uuid", "name"])
    payment_mode = PaymentModeSerializer()

    ride_expense_comments = RideExpenseCommentSerializer(many=True)
    ride_expense_docs = RideExpenseDocsSerializer(many=True)
    approved_by = MinimalMemberSerializer()
    reimbursed_by = MinimalMemberSerializer()

    class Meta:
        model = RideExpense
        fields = "__all__"