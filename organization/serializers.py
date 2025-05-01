from organization.models import (
    Department,
    Designation,
    ExternalConnection,
    Fuel,
    Location,
    Organization,
    OrganizationLocation,
    RideExpenseCostMatrix,
    Role,
    Vehicle,
)
from serializers.dynamic_serializers import DynamicFieldsModelSerializer
from form_builder import serializers as form_builder_serializer
from member.serializers_2 import MinimalMemberSerializer



class OrganizationSerializer(DynamicFieldsModelSerializer):
    class Meta:
        model = Organization
        fields = "__all__"


class RoleSerializer(DynamicFieldsModelSerializer):
    class Meta:
        model = Role
        fields = ["uuid", "name"]


class FuelSerializer(DynamicFieldsModelSerializer):
    class Meta:
        model = Fuel
        # fields = "__all__"
        exclude = ["id"]



class VehicleSerializer(DynamicFieldsModelSerializer):
    class Meta:
        model = Vehicle
        # fields = "__all__"
        exclude = ["id"]


class RideExpenseCostMatrixSerializer(DynamicFieldsModelSerializer):

    fuel = RoleSerializer(fields=["uuid", "name"])
    vehicle = VehicleSerializer(fields=["uuid", "name"])

    class Meta:
        model = RideExpenseCostMatrix
        fields = "__all__"




class DesignationSerializer(DynamicFieldsModelSerializer):
    class Meta:
        model = Designation
        exclude = ["id"]


class DepartmentSerializer(DynamicFieldsModelSerializer):
    field_report_form_config = form_builder_serializer.FieldReportFormConfigSerializer()
    create_trip_form_config = form_builder_serializer.FieldReportFormConfigSerializer()
    admin_report_form_config = form_builder_serializer.AdminReportFormConfigSerializer()

    department_head = MinimalMemberSerializer(many=True)

    class Meta:
        model = Department
        exclude = ["id"]


class OrganizationLocationSerializer(DynamicFieldsModelSerializer):
    class Meta:
        model = OrganizationLocation
        exclude = ["id"]


class ExternalConnectionSerializer(DynamicFieldsModelSerializer):

    class Meta:
        model = ExternalConnection
        exclude = ["id"]


class LocationSerializer(DynamicFieldsModelSerializer):
    department = DepartmentSerializer(fields=["name", "uuid"])

    class Meta:
        model = Location
        fields = "__all__"
