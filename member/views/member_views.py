from genericpath import exists
import re
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from organization.models import Organization, Role, OrganizationLocation, Designation
from utils.create_data import modify_member_model_data
from rest_framework import status, views
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from organization.models import Department
from api import permissions
from account.models import User
from trip.models import Trip
from member import search, serializers
from member.filter import filter_members, convert_query_params_to_dict
from member.models import Member, MemberImage
from organization.email import send_limit_exceeded_notification
from django.db.models import ProtectedError
from organization.utils import (
    get_vehicle,
    get_fuel,
    get_designation,
    get_department,
    is_allowed_to_add_members,
    get_organization_location,
)
from export.utils import create_export_request
from utils import create_data, email_funcs, fetch_data, read_data
from utils.create_data import validate_and_save_user
import base64
import csv
import pandas as pd
import logging

from django.http import JsonResponse
from member.models import Profile

logger = logging.getLogger(__name__)


class AllMembersAPI(views.APIView):
    """API View to list all member and create new member account"""

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.MemberSerializer

    # CONFIRM: Mahesh is this Admins only?
    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        members = org.members.all()

        filter_query = convert_query_params_to_dict(request.GET)
        members = filter_members(members, filter_query)

        search_query = request.GET.get("search")
        members = search.search_members(members, search_query)

        member_status = request.GET.get("status")
        if member_status in ("active", "inactive"):
            member_status = {"active": True, "inactive": False}.get(member_status, True)
            members = members.filter(user__is_active=member_status)

        if bool(request.GET.get("export_csv")) is True:
            member_ids = members.values_list("id", flat=True)
            export_request = create_export_request(member, "member", list(member_ids))
            if export_request is None:
                return Response({"export_request_uuid": None}, status=status.HTTP_400_BAD_REQUEST)
            return Response({"export_request_uuid": export_request.uuid}, status=status.HTTP_200_OK)

        per_page = request.GET.get("per_page", 10)
        page = request.GET.get("page", 1)

        paginator = Paginator(members, per_page)
        page_obj = paginator.get_page(page)
        serializer = self.serializer_class(page_obj.object_list, many=True)

        return Response(
            {
                "data": serializer.data,
                "pagination": {"total_pages": paginator.num_pages, "page": page},
            },
            status=status.HTTP_200_OK,
        )

    # ! Admins only
    def post(self, request, *args, **kwargs):

        try:
            org = fetch_data.get_organization2(request.user)
            req_member = fetch_data.get_member(request.user, org.uuid)

            if fetch_data.is_admin(req_member) is False:
                return read_data.get_403_response()

            # Check if org has reached its member limit
            if is_allowed_to_add_members(org) is False:
                send_limit_exceeded_notification(org, request.user)
                return Response(
                    {"message": "Organization member limit reached. Please contact Empfly support."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            email = request.data.get("email") if request.data.get("email", None) else None
            phone_number = request.data.get("phone_number") if request.data.get("phone_number") else None
            first_name = request.data.get("first_name", "")
            last_name = request.data.get("last_name", "")

            # check email is None and phone number is None
            # return field required error as response
            if email is None and phone_number is None:
                return Response(
                    {"message": "Email or Phone number is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # check first name is not None
            # if None return field required as response
            if not first_name:
                return Response(
                    {"message": "First Name is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            unknown_error_response = Response(
                {"message": "Unknown error occurred, please try again."},
                status=status.HTTP_400_BAD_REQUEST,
            )

            # assign lookup
            lookup = Q()

            # if email is not empty or None
            # assign a email lookup Query object
            if email:
                lookup = Q(email=email)
            # if phone_number is not empty or None
            # assign a phone lookup Query object
            if phone_number:
                lookup |= Q(phone_number=phone_number)

            # check user with email or phone_number already exists in table
            users = User.objects.filter(lookup)

            # if user exists
            if users.exists():
                # Can be Email or phone number for throw error
                existing_field = ""

                if users.filter(email=email).exists():
                    existing_field = "Email"
                else:
                    existing_field = "Phone Number"

                # return email or phone number already exists message as error response
                return Response(
                    {"message": f"{existing_field} already exists"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # if user with same phone number or email does not exists
            # create new user
            else:
                try:
                    user = User.objects.create(
                        email=email, phone_number=phone_number, first_name=first_name, last_name=last_name
                    )
                except Exception as error:
                    logger.error(error)
                    return unknown_error_response
            try:
                # check user exist and user has email
                if user and user.email:
                    # send account activation by email
                    email_funcs.send_activation_mail(user)
                # TODO phone number activation
            except Exception as error:
                logger.error(error)
                return Response(
                    {"message": "Error occurred while sending activation email"}, status=status.HTTP_400_BAD_REQUEST
                )

            # assign employee_id from payload
            employee_id = request.data.get("employee_id")

            # check member account exists with same organization and user
            member = Member.objects.filter(Q(organization=org) & Q(user=user))
            if member.exists():
                return Response({"message": "Member already exists"}, status=status.HTTP_409_CONFLICT)
            else:
                try:
                    # create new member
                    member, created = create_data.create_member(org, user)
                    if employee_id:
                        member.employee_id = employee_id
                    member.save()
                except IntegrityError as error:
                    # while creating member account, if their is any error occurred
                    # delete user
                    user.delete()
                    logger.error(error)
                    return Response({"message": "Employee ID already exists"}, status=status.HTTP_409_CONFLICT)

            serializer = self.serializer_class(member)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as error:
            logger.error(error)
            return unknown_error_response


class MemberAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.MemberSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        requesting_member = fetch_data.get_member(request.user, org_uuid)

        member_uuid = self.kwargs.get("uuid")
        member = fetch_data.get_member_by_uuid(org_uuid, member_uuid)
        if member is None:
            return read_data.get_404_response("Member")

        if fetch_data.has_access(org_uuid, request.user, "member", member) is False:
            return read_data.get_403_response()

        serializer = self.serializer_class(member)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        requesting_member = fetch_data.get_member(request.user, org_uuid)

        member_uuid = self.kwargs.get("uuid")
        member = fetch_data.get_member_by_uuid(org_uuid, member_uuid)
        if member is None:
            return read_data.get_404_response("Member")

        if fetch_data.has_access(org_uuid, request.user, "member", member) is False:
            return read_data.get_403_response()

        first_name = request.data.get("first_name", member.user.first_name)
        last_name = request.data.get("last_name", member.user.last_name)
        email = request.data.get("email")
        phone_number = request.data.get("phone_number")
        photo = request.data.get("photo")
        employee_id = request.data.get("employee_id")
        is_active = request.data.get("is_active", member.user.is_active)

        if member.user.is_active is False and is_active is True:
            if is_allowed_to_add_members(org) is False:
                send_limit_exceeded_notification(org, request.user)
                return Response(
                    {"message": "Organization member limit reached for active member. Please contact Empfly support."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        dob = request.data.get("dob")
        gender = request.data.get("gender")

        profile, _ = Profile.objects.get_or_create(member=member)

        if dob:
            dob = create_data.convert_string_to_date(dob)
            if not dob:
                return Response(
                    {"message": "DOB is not valid. Date must in yy-mm-dd format."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            profile.dob = dob

        if gender:
            profile.gender = gender
        else:
            profile.gender = None

        if not first_name:
            return Response(
                {"message": "First Name is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if isinstance(is_active, bool) is False:
            return Response(
                {"message": "Status should be true/false"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # * Manager
        manager_uuid = request.data.get("manager_uuid")
        if manager_uuid:

            manager_member = fetch_data.get_member_by_uuid(org_uuid, manager_uuid)
            if manager_member is None:
                return read_data.get_404_response("Manager")

            if member == manager_member:
                return Response(
                    {"message": "A member cannot be assigned as manager to themselves."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if manager_member.manager == member:
                return Response(
                    {
                        "message": f"Cannot assign {manager_member.user.email} as manager when "
                        f"{member.user.email} is already a manager of {manager_member.user.email}"
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            # To remove a manager for a Member
            manager_member = None

        if employee_id:
            if (
                member.employee_id != employee_id
                and Member.objects.filter(organization=org, employee_id=employee_id).exists()
            ):
                return Response(
                    {"message": f"Employee id already exists."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # * Designation
        designation_uuid = request.data.get("designation_uuid")
        designation = get_designation(org_uuid, designation_uuid)

        # if designation is None:
        #     return read_data.get_404_response("Designation")

        # * Department
        department_uuid = request.data.get("department_uuid")
        if department_uuid:
            department = get_department(org_uuid, department_uuid)
            if department is None:
                return read_data.get_404_response("Department")
        else:
            department = None

        organization_location = request.data.get("organization_location_uuid")
        if organization_location:
            organization_location = get_organization_location(organization_location)
            if organization_location is None:
                return read_data.get_404_response("organization location")
        else:
            organization_location = None

        member.user.first_name = first_name
        member.user.last_name = last_name
        member.user.is_active = is_active
        member.employee_id = employee_id
        member.manager = manager_member
        member.department = department
        member.organization_location = organization_location

        if designation:
            member.designation = designation

        if email:
            member.user.email = email
            try:
                member.save()
            except IntegrityError as e:
                logger.error(e)
                return Response(
                    {"message": "Email already exists"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # TODO Send email verification mail

        # if phone_number:
        try:
            if (
                phone_number
                and member.user.phone_number != phone_number
                and User.objects.filter(phone_number=phone_number).exists() is True
            ):
                return Response(
                    {"message": f"Phone number already exists."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if phone_number:
                member.user.phone_number = phone_number
            member.save()
        except IntegrityError as e:
            logger.error(e)
            return Response(
                {"message": "Phone number already exists"},
                status=status.HTTP_400_BAD_REQUEST,
            )

            # TODO Send verification SMS

        if photo:
            try:
                # Split the string into file format and image string
                format, imgstr = photo.split(";base64,")
                # Get file extension
                ext = format.split("/")[-1]
                # Decoding the base64 encoded text and converting it into a ContentFile
                photo = ContentFile(base64.b64decode(imgstr), name="temp." + ext)
                member.profile.photo = photo
                member.profile.save()
            except Exception as e:
                logger.error(e)
                logger.exception(f"Add exception for {e.__class__.__name__} in MemberAPI")
                return Response(
                    {"message": "Invalid image"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        member.user.save()
        profile.save()

        try:
            member.save()
        except IntegrityError as e:
            logger.error(e)
            if "unique_employee_id" in str(e):
                message = "Employee ID must be unique"
            else:
                message = "Integrity Error"
            return Response({"message": message}, status=status.HTTP_409_CONFLICT)
        except Exception as e:
            logger.error(e)
            logger.exception(f"Add exception for {e.__class__.__name__} in MemberAPI")
            return Response({"message": "Unkown error occurred"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.serializer_class(member)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid

        member_uuid = self.kwargs.get("uuid")
        member = fetch_data.get_member_by_uuid(org_uuid, member_uuid)
        if member is None:
            return read_data.get_404_response("Member")

        if fetch_data.has_access(org_uuid, request.user, "member", member) is False:
            return read_data.get_403_response()

        if not Trip.objects.filter(assigned_to__user__id=member.user.id).exists():
            try:
                member.user.delete()
                return Response(
                    {"message": "Successfully deleted member"},
                    status=status.HTTP_200_OK,
                )
            except ProtectedError as e:
                return Response(
                    {"message": "Employee is a Manager. You can deactivate the employee instead."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            except Exception as e:
                logger.error(e)
                logger.exception(f"Add exception for {e.__class__.__name__} in MemberAPI delete method")
                return Response(
                    {"message": "Something went wrong"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return Response(
            {"message": "Cannot perform this action . member have trips"},
            status=status.HTTP_400_BAD_REQUEST,
        )


class MemberManagerAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.MemberSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid

        member_uuid = self.kwargs.get("uuid")
        member = fetch_data.get_member_by_uuid(org_uuid, member_uuid)
        if member is None:
            return read_data.get_404_response("Member")

        if fetch_data.has_access(org_uuid, request.user, "member", member) is False:
            return read_data.get_403_response()

        serializer = self.serializer_class(member)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # ! Admin only
    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        requesting_member = fetch_data.get_member(request.user, org_uuid)

        if fetch_data.is_admin(requesting_member) is False:
            return read_data.get_403_response()

        member_uuid = self.kwargs.get("uuid")
        member = fetch_data.get_member_by_uuid(org_uuid, member_uuid)
        if member is None:
            return read_data.get_404_response("Member")

        manager_uuid = request.data.get("manager_uuid")
        if manager_uuid:

            manager_member = fetch_data.get_member_by_uuid(org_uuid, manager_uuid)
            if manager_member is None:
                return read_data.get_404_response("Manager")

            if member == manager_member:
                return Response(
                    {"message": "A member cannot be assigned as manager to themselves."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if manager_member.manager == member:
                return Response(
                    {
                        "message": f"Cannot assign {manager_member.user.email}"
                        f"as manager when {member.user.email} is already a "
                        f"manager of {manager_member.user.email}"
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            # To remove a manager for a Member
            manager_member = None

        member.manager = manager_member
        member.save()

        serializer = self.serializer_class(member)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AssignedMembersAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.MemberSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        requesting_member = fetch_data.get_member(request.user, org_uuid)

        lookup = Q(organization=org) & ~Q(id=requesting_member.id)

        # If member is not admin
        if fetch_data.is_admin(requesting_member) is False:
            # If member has sub-ordinates
            if requesting_member.managed_members.all().count() >= 1:
                lookup &= Q(manager=requesting_member)
            else:
                return Response(
                    {"data": [], "pagination": {"total_pages": 0, "page": 0}},
                    status=status.HTTP_200_OK,
                )

        members = Member.objects.filter(lookup)
        search_query = request.GET.get("search")
        members = search.search_members(members, search_query)

        per_page = request.GET.get("per_page", 10)
        page = request.GET.get("page", 1)
        paginator = Paginator(members, per_page)
        page_obj = paginator.get_page(page)
        serializer = self.serializer_class(page_obj.object_list, many=True)

        return Response(
            {
                "data": serializer.data,
                "pagination": {"total_pages": paginator.num_pages, "page": page},
            },
            status=status.HTTP_200_OK,
        )


class MembersAllImagesAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.MemberImageSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        member_images = member.member_images.all()
        per_page = request.GET.get("per_page", 10)
        page = request.GET.get("page", 1)
        paginator = Paginator(member_images, per_page)
        page_obj = paginator.get_page(page)
        serializer = self.serializer_class(page_obj.object_list, many=True)

        return Response(
            {
                "data": serializer.data,
                "pagination": {"total_pages": paginator.num_pages, "page": page},
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        if member.member_images.count() >= 5:
            return Response(
                {"message": "FR image limit is reached. Cannot capture more than 5 FR images."},
                status=status.HTTP_400_BAD_REQUEST
            )

        image = request.data.get("image")
        if image is None:
            return Response({"message": "Image required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Split the string into file format and image string
            format, imgstr = image.split(";base64,")
            # Get file extension
            ext = format.split("/")[-1]
            # Decoding the base64 encoded text and
            # converting it into a ContentFile
            image = ContentFile(base64.b64decode(imgstr), name="temp." + ext)
        except Exception as e:
            logger.error(e)
            logger.exception(f"Add exception for {e.__class__.__name__} in MemberImagesAPI")
            return Response({"message": "Invalid image"}, status=status.HTTP_400_BAD_REQUEST)

        encoding = fetch_data.get_image_encoding(image)
        if len(encoding) == 0:
            return Response(
                {"message": "No face detected. Try again."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if member.member_images.exists():
            try:
                face_matched = fetch_data.identify_face(org_uuid, encoding, member.user.id)
            except AttributeError as e:
                face_matched = False
            except Exception as e:
                face_matched = False

            if not face_matched:
                return Response(
                    {"message": "The face does not match your previous FR images. Please try again."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        encoding = fetch_data.convert_encoding_to_json(encoding)
        member_image = MemberImage.objects.create(member=member, image=image, encoding=encoding)

        serializer = self.serializer_class(member_image)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class MemberImageAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.MemberImageSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        uuid = self.kwargs.get("uuid")
        try:
            member_image = MemberImage.objects.get(uuid=uuid, member=member)
        except (MemberImage.DoesNotExist, ValidationError) as e:
            logger.error(e)
            return read_data.get_404_response("Member Image")
        except Exception as e:
            logger.error(e)
            logger.exception(f"Add exception for {e.__class__.__name__} in MemberImageAPI")
            return read_data.get_404_response("Member Image")

        serializer = self.serializer_class(member_image)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        uuid = self.kwargs.get("uuid")
        try:
            member_image = MemberImage.objects.get(uuid=uuid, member=member)
        except (MemberImage.DoesNotExist, ValidationError) as e:
            logger.error(e)
            return read_data.get_404_response("Member Image")
        except Exception as e:
            logger.error(e)
            logger.exception(f"Add exception for {e.__class__.__name__} in MemberImageAPI")
            return read_data.get_404_response("Member Image")

        member_image.delete()
        return read_data.get_200_delete_response("Member Image")


class MemberProfileAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.ProfileSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        requesting_member = fetch_data.get_member(request.user, org_uuid)

        uuid = request.GET.get("uuid")
        if uuid:
            member = fetch_data.get_member_by_uuid(org_uuid, uuid)
            if member is None:
                return read_data.get_404_response("Member")

            if requesting_member != member and fetch_data.is_admin(requesting_member) is False:
                return read_data.get_403_response()
        else:
            member = requesting_member

        serializer = self.serializer_class(member.profile)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        requesting_member = fetch_data.get_member(request.user, org_uuid)

        uuid = request.data.get("uuid")
        member = fetch_data.get_member_by_uuid(org_uuid, uuid)
        if member is None:
            return read_data.get_404_response("Member")

        if requesting_member != member and requesting_member.role == fetch_data.get_member_role():
            return read_data.get_403_response()

        profile = member.profile
        # first_name = request.data.get("first_name", member.user.first_name)
        # last_name = request.data.get("last_name", member.user.last_name)
        photo = request.data.get("photo")
        # dob = request.data.get("dob", profile.dob)
        address = request.data.get("address", profile.address)
        # gender = request.data.get("gender", profile.gender)
        language = request.data.get("language", profile.language)
        theme = request.data.get("theme", profile.theme)
        fuel_uuid = request.data.get("fuel_uuid")
        vehicle_uuid = request.data.get("vehicle_uuid")

        # member.user.first_name = first_name
        # member.user.last_name = last_name

        if photo:
            try:
                # Split the string into file format and image string
                format, imgstr = photo.split(";base64,")
                # Get file extension
                ext = format.split("/")[-1]
                # Decoding the base64 encoded text and converting it into a ContentFile
                photo = ContentFile(base64.b64decode(imgstr), name="temp." + ext)
                profile.photo = photo
            except Exception as e:
                logger.error(e)
                logger.exception(f"Add exception for {e.__class__.__name__} in MemberProfileAPI")
                return Response({"message": "Invalid image"}, status=status.HTTP_400_BAD_REQUEST)

        # profile.dob = dob
        # profile.gender = gender
        profile.address = address
        profile.language = language
        profile.theme = theme

        ride_preferences = {}

        if fuel_uuid:
            fuel = get_fuel(org_uuid, fuel_uuid)
            if fuel is None:
                return read_data.get_404_response("Fuel")
            ride_preferences["fuel"] = {"uuid": str(fuel.uuid), "name": fuel.name}

        if vehicle_uuid:
            vehicle = get_vehicle(org_uuid, vehicle_uuid)
            if object is None:
                return read_data.get_404_response("Vehicle")
            ride_preferences["vehicle"] = {
                "uuid": str(vehicle.uuid),
                "name": vehicle.name,
            }

        profile.settings["preferences"] = ride_preferences

        member.save()
        profile.save()

        serializer = self.serializer_class(member.profile)
        return Response(serializer.data, status=status.HTTP_200_OK)


class MembersUploadCSVAPI(views.APIView):

    permission_classes = [IsAuthenticated]
    serializer_class = serializers.MemberSerializer

    def get(self, request, *args, **kwargs):
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        schema = [
            {
                "email": "user1@gmail.com",
                "phone_number": "9876543210",
                "first_name": "user1",
                "last_name": "user",
                "designation": "desingation1",
                "department": "department1",
                "organization_location": "org_location_1",
                "employee_id": "01",
                "role": "member",
                "status": "active"
            },
            {
                "email": "user2@gmail.com",
                "phone_number": "9876543211",
                "first_name": "user2",
                "last_name": "user",
                "designation": "desingation2",
                "department": "department2",
                "organization_location": "org_location_2",
                "employee_id": "02",
                "role": "finance",
                "status": "inactive"
            },
        ]

        return JsonResponse(schema, safe=False, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        requesting_member = fetch_data.get_member(request.user, org_uuid)

        if fetch_data.is_admin(requesting_member) is False:
            return read_data.get_403_response()

        csv_file = request.data.get("csv_file")
        df = create_data.create_pandas_dataframe(csv_file)
        failed_members = []

        member_role = fetch_data.get_member_role()

        created_members_count = 0
        update_members_count = 0
        failed_rows = []
        row_count = 1

        all_users = User.objects.all()
        all_members = Member.objects.filter(organization=org)
        all_department = Department.objects.filter(organization=org)
        all_designation = Designation.objects.filter(organization=org)
        all_organization_location = OrganizationLocation.objects.filter(organization=org)
        all_roles = Role.objects.all()

        # keys = [
        #     "email",
        #     "phone",
        #     "first_name",
        #     "last_name",
        #     "designation",
        #     "department",
        #     "organization_location",
        #     "employee_id",
        #     "manager",
        #     "role"
        # ]

        avil_status = {"active": True, "inactive": False}

        for row in df.values:
            row_count += 1
            is_update = 0
            row_length = len(row)
            is_create = False

            if row_length == 12:
                is_update = 1


            try:
                email = row[0 + is_update]
                phone_number = (str(row[1 + is_update])).split(".", maxsplit=1)[0]
                first_name = row[2 + is_update]
                last_name = row[3 + is_update]
                designation = str(row[4 + is_update])
                department = str(row[5 + is_update])
                org_location = str(row[6 + is_update])
                employee_id = row[7 + is_update]

                print("## row_length ", row_length)

                if row_length == 10:  # Import
                    if not email and not phone_number:
                        raise ValidationError("email or phone number is required")

                    # check user exist with email or phone number
                    users = all_users.filter(Q(email=email) | Q(phone_number=phone_number))
                    if users.exists():
                        with_email_exists = users.filter(email=email)
                        if with_email_exists.exists():
                            users = with_email_exists
                        else:
                            with_email_phone_number = users.filter(phone_number=phone_number)
                            if with_email_phone_number.exists():
                                users = with_email_phone_number

                    if not users.exists():
                        # Check if org has reached its member limit
                        if is_allowed_to_add_members(org) is False:
                            send_limit_exceeded_notification(org, request.user)
                            return Response(
                                {"message": "Organization member limit reached. Please contact Empfly support."},
                                status=status.HTTP_400_BAD_REQUEST,
                            )

                        # create user, set password and send activation email
                        if not first_name:
                            raise ValidationError("First Name is required")
                        
                        if email:
                            user = User.objects.create(email=email, first_name=first_name)
                        else:
                            user = User.objects.create(phone_number=phone_number, first_name=first_name)

                        user.set_password("password")
                        email_funcs.send_activation_mail(user)
                    else:
                        user = users.first()

                    validate_and_save_user(
                        all_users=all_users,
                        user=user,
                        email=email,
                        phone_number=phone_number,
                        first_name=first_name,
                        last_name=last_name,
                    )

                    member_role = row[8]
                    user_status = row[9]

                    if member_role not in  ("admin", "finance", "member"):
                        raise ValidationError("Member role must be admin/finance/member.")

                    if user_status not in ("active", "inactive"):
                        raise ValidationError("User status must be active/inactive.")

                    print(member_role)
                    print(user_status)
                    print("%%%%%%%%%%%")

                    role_obj = all_roles.get(name=member_role)
                    user_bool_status = avil_status.get(user_status, True)

                    print("@@@@@@@@@@@@@@@@@@@@@@@@")
                    print(user_bool_status)
                    print(user.is_active)
                    print("@@@@@@@@@@@@@@@@@@@@@@@@")

                    if user.is_active != user_bool_status and user_bool_status is True:
                        if is_allowed_to_add_members(org) is False:
                            send_limit_exceeded_notification(org, request.user)
                            return Response(
                                {"message": "Organization member limit reached. Please contact Empfly support."},
                                status=status.HTTP_400_BAD_REQUEST,
                            )

                    user.is_active = user_bool_status
                    user.save()

                    # check member is exist or not. if not create member
                    members = all_members.filter(user=user)
                    if not members.exists():
                        # role = fetch_data.get_member_role()
                        member = Member.objects.create(organization=org, user=user, role=role_obj)
                        created_members_count += 1
                        is_create = True
                    else:
                        member = members.first()
                        member.role = role_obj

                if row_length == 12:  # Update
                    if not row[0] and row[0] != 0:
                        raise ValidationError("id is required")
                    member = all_members.filter(id=row[0]).get()

                    user = member.user

                    validate_and_save_user(
                        all_users=all_users,
                        user=user,
                        email=email,
                        phone_number=phone_number,
                        first_name=first_name,
                        last_name=last_name,
                        is_bulk_update=True,
                    )

                    user_status = row[11]

                    bool_of_available_status = avil_status.get(user_status, True)
                    if user.is_active != bool_of_available_status and bool_of_available_status is True:
                        if is_allowed_to_add_members(org) is False:
                            send_limit_exceeded_notification(org, request.user)
                            return Response(
                                {"message": "Organization member limit reached. Please contact Empfly support."},
                                status=status.HTTP_400_BAD_REQUEST,
                            )

                    user.is_active = avil_status.get(user_status, True)
                    user.save()

                    manager = row[9]  # email
                    role = row[10]

                    if manager in ("", "NA"):
                        member.manager = None
                    elif manager:
                        managers = all_members.filter(user__email=manager).exclude(id=member.id)
                        if managers.exists():
                            manager = managers.first()
                            if member.id != manager.id and not manager.manager == member:
                                member.manager = manager

                    if role and member.id != requesting_member.id:
                        roles = Role.objects.filter(name=role)
                        if roles.exists():
                            member.role = roles.first()

                bulk_update = bool(is_update)

                modify_member_model_data(
                    filter_ins=all_department,
                    member=member,
                    Modal=Department,
                    organization=org,
                    name=department,
                    field_name="department",
                    bulk_update=bulk_update,
                    curr_val=member.department.name if member.department else "",
                )

                modify_member_model_data(
                    filter_ins=all_designation,
                    member=member,
                    Modal=Designation,
                    organization=org,
                    name=designation,
                    field_name="designation",
                    bulk_update=bulk_update,
                    curr_val=member.designation.name if member.designation else "",
                )

                modify_member_model_data(
                    filter_ins=all_organization_location,
                    member=member,
                    Modal=OrganizationLocation,
                    organization=org,
                    name=org_location,
                    field_name="organization_location",
                    bulk_update=bulk_update,
                    curr_val=member.organization_location.name if member.organization_location else "",
                )

                if employee_id in ("", "NA"):
                    member.employee_id = None
                elif member.employee_id != employee_id and not Member.objects.filter(employee_id=employee_id).exists():
                    member.employee_id = employee_id

                member.save()
                if not is_create:
                    update_members_count += 1

            except Exception as e:
                failed_rows.append(row_count)
                try:
                    failed_members.append(
                        {
                            "email": row[0],
                            "reason": str(e.__class__.__name__),
                            "detailed_reason": str(e),
                        }
                    )
                except Exception as e:
                    pass
                logger.error(e)
                logger.exception(f"Add exception for {e.__class__.__name__} in MembersUploadCSVAPI")

        return Response(
            {
                "failed_members": failed_rows,
                "created_member": created_members_count,
                "updated_count": update_members_count,
                "failed_members_reason": failed_members,
            },
            status=status.HTTP_201_CREATED,
        )


class DepartmentUploadCSVAPI(views.APIView):

    permission_classes = [IsAuthenticated]
    serializer_class = serializers.MemberSerializer

    def get(self, request, *args, **kwargs):

        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        schema = [
            {
                "department": "department1",
                "desciption": "desciption1",
            },
            {
                "department": "department2",
                "desciption": "desciption2",
            },
        ]

        return JsonResponse(schema, safe=False, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        csv_file = request.data.get("csv_file")
        df = create_data.create_pandas_dataframe(csv_file)

        member_role = fetch_data.get_member_role()

        failed_departments = []
        failed_rows = []
        row_count = 1
        created_departments = 0
        updated_count = 0

        all_departments = Department.objects.filter(organization=org)

        for row in df.values:
            row_count += 1
            is_update = 0
            row_length = len(row)

            try:

                if row_length == 2:  # import
                    dep_name = str(row[0]).strip()
                    if not dep_name:
                        raise ValidationError("department name is required")

                    department = all_departments.filter(name=dep_name)

                    if not department.exists():
                        Department.objects.create(name=dep_name, organization=org, description=row[1])
                        created_departments += 1
                        continue
                    else:
                        department = department.first()

                if row_length == 3 or row_length == 4:  # Update

                    if not row[0]:
                        raise ValidationError("uuid is required")

                    department = all_departments.filter(uuid=row[0]).get()
                    is_update = 1

                    if row[1]:
                        department.name = row[1]

                if row[1 + is_update] in ("", "NA"):
                    department.description = None
                else:
                    department.description = row[1 + is_update]

                department.save()
                updated_count += 1

            except Exception as e:
                failed_rows.append(row_count)
                try:
                    failed_departments.append(
                        {
                            "reason": str(e.__class__.__name__),
                            "detailed_reason": str(e),
                        }
                    )
                except Exception as e:
                    pass
                logger.error(e)
                logger.exception(f"Add exception for {e.__class__.__name__} in DepartmentUploadCSVAPI")

        return Response(
            {
                "failed_departments": failed_departments,
                "created_count": created_departments,
                "failed_rows": failed_rows,
                "updated_count": updated_count,
            },
            status=status.HTTP_201_CREATED,
        )


class AllMembersV2API(views.APIView):
    """List member who belongs to the department they are as head"""

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.MemberSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        departments = Department.objects.filter(organization=org)
        if fetch_data.is_admin(member) is False:
            departments = departments.filter(department_head=member)

        members = Member.objects.filter(department__in=departments, organization=org)

        filter_query = convert_query_params_to_dict(request.GET)
        members = filter_members(members, filter_query)

        search_query = request.GET.get("search")
        members = search.search_members(members, search_query)

        # member_status = request.GET.get("status")
        # if member_status in ("active", "inactive"):
        #     member_status = {"active": True, "inactive": False}.get(member_status, True)
        #     members = members.filter(user__is_active=member_status)

        per_page = request.GET.get("per_page", 10)
        page = request.GET.get("page", 1)

        paginator = Paginator(members, per_page)
        page_obj = paginator.get_page(page)
        serializer = self.serializer_class(page_obj.object_list, many=True, exclude=["organization", "department", "organization_location", "profile", "designation", "created_at", "updated_at", "role", "id"])

        return Response(
            {
                "data": serializer.data,
                "pagination": {"total_pages": paginator.num_pages, "page": page},
            },
            status=status.HTTP_200_OK,
        )
