from expense.serializers import RideExpenseSerializer
from member.serializers import MemberSerializer
from organization.serializers import LocationSerializer

from trip.models import Trip, TripDetails, TripEstimation, TripScan, TripTemplate
from serializers.dynamic_serializers import DynamicFieldsModelSerializer
from form_builder import serializers as form_builder_serializer

class TripEstimationSerializer(DynamicFieldsModelSerializer):

    class Meta:
        model = TripEstimation
        fields = "__all__"

class TripScanSerializer(DynamicFieldsModelSerializer):

    class Meta:
        model = TripScan
        fields = "__all__"


class TripDetailsSerializer(DynamicFieldsModelSerializer):

    start_scan = TripScanSerializer()
    end_scan = TripScanSerializer()

    class Meta:
        model = TripDetails
        fields = "__all__"


class TripSerializer(DynamicFieldsModelSerializer):

    start_location_ptr = LocationSerializer()
    end_location_ptr = LocationSerializer()

    trip_estimation = TripEstimationSerializer()
    trip_details = TripDetailsSerializer()
    ride_expense = RideExpenseSerializer()

    field_report_form_submission = form_builder_serializer.FieldReportFormSubmissionsSerializer()
    create_trip_form_submissions = form_builder_serializer.CreateTripFormSubmissionsSerializer()
    admin_report_form_submissions = form_builder_serializer.AdminReportFormSubmissionsSerializer()

    assigned_to = MemberSerializer()
    created_by = MemberSerializer()

    class Meta:
        model = Trip
        fields = "__all__"


class TripTemplateSerializer(DynamicFieldsModelSerializer):

    created_by = MemberSerializer()
    updated_by = MemberSerializer()

    class Meta:
        model = TripTemplate
        fields = "__all__"
