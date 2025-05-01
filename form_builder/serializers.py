from serializers.dynamic_serializers import DynamicFieldsModelSerializer
from .models import FieldReportFormSubmissions, FieldReportFormConfig, FieldReportFile, CreateTripFormConfig, CreateTripFormSubmissions, AdminReportFormConfig, AdminReportFormSubmissions


class FieldReportFileSerializer(DynamicFieldsModelSerializer):
    class Meta:
        model = FieldReportFile
        exclude = ["id"]


class FieldReportFormSubmissionsSerializer(DynamicFieldsModelSerializer):

    field_report_file = FieldReportFileSerializer(many=True)
    class Meta:
        model = FieldReportFormSubmissions
        exclude = ["id"]

class FieldReportFormConfigSerializer(DynamicFieldsModelSerializer):
    class Meta:
        model = FieldReportFormConfig
        exclude = ["id"]




class FieldReportFileValidationSerializer(DynamicFieldsModelSerializer):
    class Meta:
        model = FieldReportFile
        fields = ["file"]


class CreateTripFormConfigSerializer(DynamicFieldsModelSerializer):
    class Meta:
        model = CreateTripFormConfig
        exclude = ["id"]


class CreateTripFormSubmissionsSerializer(DynamicFieldsModelSerializer):
    class Meta:
        model = CreateTripFormSubmissions
        exclude = ["id"]

class AdminReportFormConfigSerializer(DynamicFieldsModelSerializer):
    class Meta:
        model = AdminReportFormConfig
        exclude = ["id"]


class AdminReportFormSubmissionsSerializer(DynamicFieldsModelSerializer):
    class Meta:
        model = AdminReportFormSubmissions
        exclude = ["id"]