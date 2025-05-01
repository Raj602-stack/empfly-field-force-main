from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.paginator import Paginator
from django.db import DataError
from django.db.models import Q
from django.utils import timezone

from rest_framework import status, views
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


from drf_yasg import openapi
from drf_yasg.openapi import IN_BODY, IN_QUERY, Parameter, Schema
from drf_yasg.utils import swagger_auto_schema
from organization.email import send_trip_ended_email
from swagger.constants import (
    SchemaConstants,
    SchemaParameters,
    SchemaPayload,
    SchemaResponse,
)

from api import permissions
from expense.models import RideExpense
from organization.models import Organization, RideExpenseCostMatrix
from organization.utils import get_vehicle, get_fuel
from trip import serializers
from trip.models import Trip, TripDetails, TripEstimation, TripScan
from trip.utils import (
    create_trip_err_msg,
    get_my_trip,
    get_trip,
    has_access_to_trip,
    extract_coordinates,
    extract_coordinates_as_str,
    calculate_distance,
    round_off_value,
    save_scan_err,
    extract_coordinates_from_scan_obj_as_str
)
from utils import fetch_data, google_api, read_data

import base64
import datetime as dt
import logging
import pytz

logger = logging.getLogger("app.log")


class TripDetailsAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.TripDetailsSerializer

    @swagger_auto_schema(
        tags=["Trip Details"],
        operation_id="Get a trip",
        responses={
            200: serializer_class(),
            404: SchemaResponse.get_404("Trip"),
        },
        manual_parameters=[SchemaParameters.get_uuid("trip")],
    )
    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid

        member = fetch_data.get_member(request.user, org_uuid)

        uuid = self.kwargs.get("uuid")
        trip = get_trip(org_uuid, uuid)

        if has_access_to_trip(trip, member) is False:
            return read_data.get_403_response()

        trip_details = trip.trip_details
        serializer = self.serializer_class(trip_details)
        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )


class TripScansAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.TripScanSerializer

    def get(self, request, *args, **kwargs):

        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        uuid = self.kwargs.get("uuid")
        trip = get_trip(org_uuid, uuid)
        if has_access_to_trip(trip, member) is False:
            return read_data.get_403_response()

        trip_scans = []
        trip_details = trip.trip_details

        if trip_details.start_scan:
            trip_scans.append(trip_details.start_scan)
        if trip_details.end_scan:
            trip_scans.append(trip_details.end_scan)

        serializer = self.serializer_class(trip_scans, many=True)
        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    def post(self, request, *args, **kwargs):
        """ Create trip start scan and end scan.
            While creating scan face rec and geo fencing will check.
            TripScan model hold member scan details. The start scan
            and end scan is saved in TripDetails model.

            if TripDetails.start_scan is None member is creating first scan
            else member is creating last scan

            After end scan duration, distance, estimated_duration, estimated_distance these field
            will be filled in trip details model
        """

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        uuid = self.kwargs.get("uuid")
        trip = get_trip(org_uuid, uuid)
        if trip is None:
            return read_data.get_404_response("Trip")

        # * Scan settings
        scan_settings = org.settings.get("scan_settings", {})
        online_scan_settings = scan_settings.get("online", {})
        offline_scan_settings = scan_settings.get("offline", {})

        online_face_recognition = online_scan_settings.get("face_recognition", True)
        online_geo_fencing = online_scan_settings.get("geo_fencing", True)

        offline_face_recognition = offline_scan_settings.get("face_recognition", True)
        offline_geo_fencing = offline_scan_settings.get("geo_fencing", True)

        # Only rider can add scans to the Trip
        if trip.assigned_to != member:
            logger.error("The trip is not assigned to you")
            return read_data.get_403_response("The trip is not assigned to you")

        # Check if there is another ongoing trip
        trips = Trip.objects.filter(Q(assigned_to=member) & Q(status__in=["started"]) & ~Q(id=trip.id))
        if trips.exists():
            logger.error("Cannot start a new trip when another trip is in progress")
            return read_data.get_403_response("Cannot start a new trip when another trip is in progress")

        trip_details = trip.trip_details

        scan_err_msg = None

        scan_type = "start_scan"
        if trip_details.start_scan is not None:
            scan_type = "end_scan"

        image = request.data.get("image")
        if image:
            # format, imgstr = image.split(";base64,")
            # # Get file extension
            # ext = format.split("/")[-1]
            image = ContentFile(base64.b64decode(image), name="temp." + "png")

        # Formatted Address
        name = request.data.get("name")
        latitude = request.data.get("latitude")
        longitude = request.data.get("longitude")
        time = request.data.get("time")
        offline = request.data.get("offline", False)
        user_notes = request.data.get("user_notes")
        remarks = request.data.get("remarks")

        is_force_sync = request.data.get("force_sync", False)

        if not isinstance(is_force_sync, bool):
            return Response(
                {"message": "Force Sync must a boolean."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        force_sync_logs = []

        # * Face Recognition
        try:
            face_encoding = fetch_data.get_image_encoding(image)
            face_matched = fetch_data.identify_face(org_uuid, face_encoding, member.user.id)
        except AttributeError as e:
            face_matched = False
        except Exception as e:
            logger.error(e)
            logger.exception(f"Add exception for {e.__class__.__name__}" " in TripScansAPI > Face Scan")
            face_matched = False

        logger.info(f"{face_matched=}")
        # face_matched = True

        if offline and org.settings.get("allow_offline_trips", True) is False:
            if is_force_sync is False:
                scan_err_msg = "Offline trips are not allowed"
                scan_errors = create_trip_err_msg(msg=scan_err_msg, scan_type=scan_type)
                save_scan_err(trip, scan_errors)

                return Response(
                    {"message": "Offline trips are not allowed"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if scan_type == "start_scan":
                force_sync_logs.append("Trip start scan created in offline mode but offline trips are not allowed in the organization.")
            elif scan_type == "end_scan":
                force_sync_logs.append("Trip end scan created in offline mode but offline trips are not allowed in the organization.")

        # If face does not match and is in online mode
        if face_matched is False:
            if (offline is True and offline_face_recognition) or (offline is False and online_face_recognition):
                if is_force_sync is False:
                    scan_err_msg = "Face cannot be identified"
                    scan_errors = create_trip_err_msg(msg=scan_err_msg, scan_type=scan_type)
                    save_scan_err(trip, scan_errors)

                    return Response(
                        {"message": "Face cannot be identified"},
                        status=status.HTTP_404_NOT_FOUND,
                    )

                if scan_type == "start_scan":
                    force_sync_logs.append("Start scan face cannot be identified.")
                elif scan_type == "end_scan":
                    force_sync_logs.append("End scan face cannot be identified.")

        # create trip scan object
        trip_scan = TripScan.objects.create(name=name, image=image, latitude=latitude, longitude=longitude)

        # save trip scan notes
        if face_matched is False:
            trip_scan.notes["face_recognition"] = "Face cannot be identified"
            trip_scan.save()
        if user_notes:
            trip_scan.notes["user_notes"] = user_notes
            trip_scan.save()

        # If face does not match and is in offline mode
        if face_matched is False and offline is True:
            trip_scan.notes["face_recognition"] = "Face cannot be identified."
            # save trip scan notes
            trip_scan.save()

            if offline_face_recognition and is_force_sync is False:
                scan_err_msg = "Face cannot be identified"
                scan_errors = create_trip_err_msg(msg=scan_err_msg, scan_type=scan_type)
                save_scan_err(trip, scan_errors)

                return Response(
                    {"message": "Face cannot be identified"},
                    status=status.HTTP_404_NOT_FOUND,
                )
        # if payload data has trip scan time take that value as scan time
        # else take current time as scan time
        if time:
            scan_time = timezone.make_aware(dt.datetime.strptime(time, "%Y-%m-%d %H:%M:%S.%f"))
        else:
            scan_time = read_data.get_current_datetime()

        logger.info("_________________________________________")
        logger.info(f"trip_uuid: {trip.uuid}")
        logger.info(f"time in request: {time}")
        logger.info(f"scan_time: {scan_time}")

        trip_scan.time = scan_time
        trip_scan.save()

        scan_coords = f"{latitude},{longitude}"

        # *  Trip started
        # if trip details object does not have start scan object
        # save this trip scan object as start scan
        if trip_details.start_scan is None:
            # system location or location added by google map api search
            start_location = trip.start_location
            start_location_coords = extract_coordinates(start_location)
            # current live latitude & longitude (Actual)
            start_scan_coords = (latitude, longitude)

            # calculate distance between trip start location and current location (Actual)
            geo_fencing_distance = calculate_distance(start_location_coords, start_scan_coords)

            # if calculated distance is less than geo fencing radius
            if geo_fencing_distance <= float(start_location.get("radius")):
                trip_details.start_scan = trip_scan
            # else save notes as Outside geofencing area &
            # retun Response
            else:
                if (
                    offline is True and offline_geo_fencing is False
                ) or (
                    offline is False and online_geo_fencing is False
                ):
                    trip_scan.notes["geo_fencing"] = "Outside geofencing area."
                    trip_scan.save()
                    trip_details.start_scan = trip_scan
                elif is_force_sync is True:
                    trip_scan.notes["geo_fencing"] = "Outside geofencing area."
                    trip_scan.save()
                    trip_details.start_scan = trip_scan

                    force_sync_logs.append("Start scan created outside of geofencing area.")
                else:
                    # ! Not deleting for debugging purposes
                    # trip_scan.delete()
                    return Response(
                        {"message": "Outside geofencing area"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            trip.status = "started"
            trip.save()
            trip_details.save()

        # Trip completed
        # if trip details object does not have end scan object
        # save this trip scan object as end scan
        elif trip_details.end_scan is None:
            # Start Scan Time
            trip_first_scan_utc_time = trip_details.start_scan.time
            trip_end_scan_ist_time = trip_scan.time
            # print(f"trip_first_scan_utc_time: {trip_first_scan_utc_time}")
            # print(f"trip_end_scan_time ist: {trip_end_scan_ist_time}")

            utc = pytz.timezone('UTC')
            trip_end_scan_utc_time = trip_end_scan_ist_time.astimezone(utc)
            # print(f"trip_end_scan_utc_time: {trip_end_scan_utc_time}")

            logger.info(f"trip_first_scan_utc_time: {trip_first_scan_utc_time}")
            logger.info(f"trip_end_scan_ist_time: {trip_end_scan_ist_time}")
            logger.info(f"trip_end_scan_utc_time: {trip_end_scan_utc_time}")

            if trip_first_scan_utc_time and trip_end_scan_utc_time and trip_end_scan_utc_time <= trip_first_scan_utc_time:
                logger.error("=================== Trip end scan time is less than start scan time ===================")

                trip_scan.delete()
                return Response(
                    {"message": "Trip start scan time and end scan time cannot be same. Please upload end scan again."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # system location or location added by google map api search
            start_location = trip.start_location
            start_location_coords = extract_coordinates_as_str(start_location)

            end_location = trip.end_location
            end_location_coords = extract_coordinates(end_location)

            # calculate distance between trip end location and current location (Actual)
            geo_fencing_distance = calculate_distance(end_location_coords, scan_coords)

            is_outside_geo_fencing = False
            # if calculated distance is less than geo fencing radius
            if geo_fencing_distance <= float(end_location.get("radius")):
                trip_details.end_scan = trip_scan
            else:

                if (
                    offline is True and offline_geo_fencing is False
                ) or (
                    offline is False and online_geo_fencing is False
                ):
                    trip_scan.notes["geo_fencing"] = "Outside geo fencing area."
                    is_outside_geo_fencing = True
                    trip_scan.save()
                    trip_details.end_scan = trip_scan
                elif is_force_sync is True:
                    trip_scan.notes["geo_fencing"] = "Outside geo fencing area."
                    is_outside_geo_fencing = True
                    trip_scan.save()
                    trip_details.end_scan = trip_scan

                    force_sync_logs.append("End scan created outside of geofencing area.")
                else:
                    # ! Not deleting for debugging purposes
                    # trip_scan.delete()
                    scan_err_msg = "Outside geofencing area"
                    scan_errors = create_trip_err_msg(msg=scan_err_msg, scan_type=scan_type)
                    save_scan_err(trip, scan_errors)

                    return Response(
                        {"message": "Outside geo fencing area"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            # save remarks
            trip_details.remarks = remarks
            trip.status = "ended"
            if is_outside_geo_fencing:
                trip.is_outside_geo_fencing = True
            trip.save()

            # * Calculate actual time (Total duration)
            # * by end scan time - start scan time
            start_scan = trip_details.start_scan
            start_time = start_scan.time
            end_time = trip_scan.time
            duration = read_data.get_difference_between_datetimes_as_time(start_time, end_time)
            print(f"duration: {duration}, type:{type(duration)}")
            # * save duration as HH:MM:SS Format
            trip_details.duration = duration
            trip_details.save()

            # * Calculate Estimated Distance by google Distance Matrix API
            # check google api key is active
            # if active calculate distance
            if google_api.get_gcp_api_key_is_active(request):

                trip_start_scan = trip_details.start_scan
                trip_end_scan = trip_details.end_scan

                start_location_lat_and_long = extract_coordinates_from_scan_obj_as_str(trip_start_scan)
                end_location_lat_and_long = extract_coordinates_from_scan_obj_as_str(trip_end_scan)
                end_location_coords = extract_coordinates_as_str(end_location)
                # estimated distance in meters
                # https://developers.google.com/maps/documentation/distance-matrix/distance-matrix#DistanceMatrixElement-distance
                # estimated duration in seconds
                # https://developers.google.com/maps/documentation/distance-matrix/distance-matrix#DistanceMatrixElement-duration
                (
                    _,
                    estimated_duration_in_seconds,
                ) = google_api.calculate_distance_and_duration(request, start_location_coords, end_location_coords)

                (
                    estimated_distance,
                    _,
                ) = google_api.calculate_distance_and_duration(request, start_location_lat_and_long, end_location_lat_and_long)

                print(f"estimated_distance: {estimated_distance}, type:{type(estimated_distance)}")

                if estimated_distance is not None:
                    # convert meters to KMs
                    kms = estimated_distance / 1000
                    # estimated distance in KMS
                    trip_details.estimated_distance = kms
                    # Actual distance in KMS
                    # * We will save estimated distance as actual distance
                    # * In Ride expense form this actual distance value is editable
                    # trip_details.distance = kms
                if estimated_duration_in_seconds is not None:
                    estimated_duration = read_data.convert_seconds_to_datetime(estimated_duration_in_seconds)
                    trip_details.estimated_duration = estimated_duration
                    # save trip details
                    trip_details.save()

            # send email
            send_trip_ended_email(trip)

        else:
            trip_scan.delete()
            return Response(
                {"message": "Trip already has start and end scan"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        force_trip_sync_logs = trip.force_trip_sync_logs
        if force_sync_logs:
            if isinstance(force_trip_sync_logs, list):
                trip.force_trip_sync_logs += force_sync_logs
                trip.save()
            else:
                trip.force_trip_sync_logs = force_sync_logs
                trip.save()

        serializer = serializers.TripDetailsSerializer(trip_details)
        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )


class TripFuelCostAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]

    def get_response_200():
        return {
            "distance": "6000",
            "duration": "2:40",
            "distance_unit": "kilometer",
            "cost_per_unit": "30",
            "fuel_cost": "180",
        }

    @swagger_auto_schema(
        tags=["Trip Details"],
        operation_id="Get a trip's fuel cost",
        responses={
            200: SchemaResponse.get_200(get_response_200()),
            404: SchemaResponse.get_404("Trip"),
        },
        manual_parameters=[SchemaParameters.get_uuid("trip")],
    )
    def get(self, request, *args, **kwargs):
        """ Define cost according to fuel and vehicle type.
        """

        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        trip_uuid = self.kwargs.get("uuid")
        vehicle_uuid = request.GET.get("vehicle_uuid")
        fuel_uuid = request.GET.get("fuel_uuid")

        vehicle = get_vehicle(org_uuid, vehicle_uuid)
        if vehicle is None:
            return read_data.get_404_response("Vehicle")

        fuel = get_fuel(org_uuid, fuel_uuid)
        if fuel is None:
            return read_data.get_404_response("Fuel")

        trip = get_trip(org_uuid, trip_uuid)
        if trip is None:
            return read_data.get_404_response("Trip")

        try:
            cost_matrix = RideExpenseCostMatrix.objects.get(vehicle=vehicle, fuel=fuel)
        except RideExpenseCostMatrix.DoesNotExist as e:
            logger.error(e)
            return read_data.get_404_response("Cost Matrix")
        except Exception as e:
            logger.error(e)
            logger.exception(f"Add exception for {e.__class__.__name__} in TripFuelCostAPI")
            return read_data.get_404_response("Cost Matrix")

        trip_details = trip.trip_details
        try:
            distance = float(trip_details.estimated_distance)
        except TypeError as e:
            logger.error(e)
            distance = 0
        except Exception as e:
            logger.error(e)
            logger.exception(f"Add exception for {e.__class__.__name__} in TripFuelCostAPI")

        # if cost_matrix.distance_unit == "kilometer":
        #     distance = distance
        # elif cost_matrix.distance_unit == "mile":
        #     distance = distance * 0.000621371


        cost = distance * cost_matrix.cost_per_unit
        cost = round_off_value(cost)

        data = {
            "distance": trip_details.distance,
            "estimated_distance": trip_details.estimated_distance,
            "duration": trip_details.duration,
            "distance_unit": cost_matrix.distance_unit,
            "cost_per_unit": cost_matrix.cost_per_unit,
            "fuel_cost": cost,
        }
        return Response(data, status=status.HTTP_200_OK)


class TripRemarksAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.TripDetailsSerializer

    def get(self, request, *args, **kwargs):
        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        uuid = self.kwargs.get("uuid")
        trip = get_trip(org_uuid, uuid)
        if trip is None:
            return read_data.get_404_response("Trip")

        if has_access_to_trip(trip, member) is False:
            return read_data.get_403_response()

        trip_details = trip.trip_details

        serializer = self.serializer_class(trip_details)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        uuid = self.kwargs.get("uuid")
        trip = get_trip(org_uuid, uuid)
        if trip is None:
            return read_data.get_404_response("Trip")

        if has_access_to_trip(trip, member) is False:
            return read_data.get_403_response()

        remarks = request.data.get("remarks")
        trip_details = trip.trip_details
        trip_details.comments["remarks"] = remarks
        trip_details.save()

        serializer = self.serializer_class(trip_details)
        return Response(serializer.data, status=status.HTTP_200_OK)
