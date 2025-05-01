from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.middleware.csrf import get_token
from organization.models import Organization

from rest_framework import generics, serializers, status, views
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api import permissions
from account.models import AuthToken, SessionToken, User
from member.models import Member
from account.serializers import UserSerializer
from member.serializers import MemberSerializer, ProfileSerializer
from organization.serializers import RoleSerializer

from utils import create_data, email_funcs, fetch_data, read_data

import logging


logger = logging.getLogger(__name__)


def get_csrf(request):
    return JsonResponse({"detail": "CSRF cookie set", "X-CSRFToken": get_token(request)})


# TODO LOW: Remove this
class UserRegistrationAPI(views.APIView):
    """
    API for users who wish to setup an org and user account on FF.
    Need to provide org details. User will be added as admin in the org.
    """

    permission_classes = []

    def post(self, request, *args, **kwargs):

        email = request.data.get("email")
        first_name = request.data.get("first_name")
        last_name = request.data.get("last_name")
        phone_number = request.data.get("phone_number")
        org_name = request.data.get("organization")

        if not first_name:
            return Response({"message": "First Name is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Create User
        # user, user_created = User.objects.get_or_create(email=email)
        # if user_created is False:
        #     return Response(
        #         {"message": "User already exists"}, status=status.HTTP_400_BAD_REQUEST
        #     )

        all_users = User.objects.filter(email=email)
        if all_users.exists() is True:
            return Response({"message": "User already exists."}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.create(email=email, first_name=first_name)
        # org = create_data.create_organization(org_name)

        # Create organization
        if Organization.objects.filter(name=org_name).exists():
            return Response({"message": "Organization with this name already exists."}, status=status.HTTP_400_BAD_REQUEST) 

        org = Organization.objects.create(
            name=org_name
        )
        # Create member
        role = fetch_data.get_admin_role()
        create_data.create_member(org, user, role=role)

        user.first_name = first_name
        user.last_name = last_name
        user.phone_number = phone_number
        user.save()
        email_funcs.send_activation_mail(user)

        return Response(
            {
                "message": "Successfully created user",
            },
            status=status.HTTP_201_CREATED,
        )


class UserActivationAPI(views.APIView):

    permission_classes = []

    def get(self, request, *args, **kwargs):

        uuid = request.GET.get("uuid")
        token = request.GET.get("token")

        try:
            user = User.objects.get(uuid=uuid)
        except (ValidationError, User.DoesNotExist) as e:
            logger.error(e)
            return read_data.get_404_response("User")

        try:
            session_token = SessionToken.objects.get(user=user, token=token)
        except (SessionToken.DoesNotExist) as e:
            return read_data.get_404_response("Token")

        return Response({}, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):

        # Validation UUID and Token
        uuid = request.data.get("uuid")
        token = request.data.get("token")

        try:
            user = User.objects.get(uuid=uuid)
        except (ValidationError, User.DoesNotExist) as e:
            logger.info(e)
            return read_data.get_404_response("User")

        try:
            session_token = SessionToken.objects.get(user=user, token=token)
        except (SessionToken.DoesNotExist) as e:
            return read_data.get_404_response("Token")

        # Set password
        new_password = request.data.get("new_password")
        confirm_new_password = request.data.get("confirm_new_password")

        if new_password is None or confirm_new_password is None:
            return Response(
                {"message": "Password(s) needs to be provided"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if new_password != confirm_new_password:
            return Response(
                {"message": "Passwords do not match"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)
        user.is_active = True
        user.save()

        # Delete the token
        session_token.delete()
        email_funcs.send_confirmation_mail(user)

        return Response(
            {"message": "Successfully activated your account"},
            status=status.HTTP_200_OK,
        )


class ChangePasswordAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]

    def post(self, request, *args, **kwargs):

        user = request.user
        current_password = request.data.get("current_password")
        is_valid = user.check_password(current_password)

        if is_valid is False:
            return Response({"message": "Invalid credentials"}, status=status.HTTP_400_BAD_REQUEST)

        new_password = request.data.get("new_password")
        confirm_new_password = request.data.get("confirm_new_password")

        if new_password != confirm_new_password:
            return Response(
                {"message": "Passwords do not match"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)
        user.save()

        # TODO HIGH: Log user out of all sessions

        return Response({"message": "Successfully updated password"}, status=status.HTTP_200_OK)


class ForgotPasswordAPI(views.APIView):

    permission_classes = []

    def post(self, request, *args, **kwargs):

        email = request.data.get("email")
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist as e:
            return read_data.get_404_response("User")

        email_funcs.send_password_reset_mail(user)

        return Response(
            {"message": "Password reset link has been sent to your email address"},
            status=status.HTTP_201_CREATED,
        )


class PasswordResetAPI(views.APIView):

    permission_classes = []

    def get(self, request, *args, **kwargs):

        uuid = request.GET.get("uuid")
        token = request.GET.get("token")

        try:
            user = User.objects.get(uuid=uuid)
        except (ValidationError, User.DoesNotExist) as e:
            logger.info(e)
            return read_data.get_404_response("User")

        try:
            session_token = SessionToken.objects.get(user=user, token=token)
        except (SessionToken.DoesNotExist) as e:
            return read_data.get_404_response("Token")

        return Response({}, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):

        # Validation uuid and Token
        uuid = request.data.get("uuid")
        token = request.data.get("token")

        try:
            user = User.objects.get(uuid=uuid)
        except (ValidationError, User.DoesNotExist) as e:
            logger.info(e)
            return read_data.get_404_response("User")

        try:
            session_token = SessionToken.objects.get(user=user, token=token)
        except (SessionToken.DoesNotExist) as e:
            return read_data.get_404_response("Token")

        # Set password
        new_password = request.data.get("new_password")
        confirm_new_password = request.data.get("confirm_new_password")

        if new_password != confirm_new_password:
            return Response(
                {"message": "Passwords do not match"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)
        user.save()

        # Deactivate the token
        session_token.delete()

        # TODO HIGH: Log user out of all sessions

        return Response(
            {"message": "Password has been reset"},
            status=status.HTTP_200_OK,
        )


class SetPasswordAPI(generics.UpdateAPIView):
    """API view used for set password of members by admin"""

    permission_classes = [permissions.IsTokenAuthenticated, permissions.IsAdmin]

    def put(self, request, *args, **kwargs):

        try:
            # get org uuid from current logged in user (admin)
            logged_in_user = Member.objects.get(user=request.user)
            org_uuid = logged_in_user.organization.uuid

            # get uuid from url path
            member_uuid = self.kwargs.get("uuid")

            member = fetch_data.get_member_by_uuid(org_uuid, member_uuid)
            if member is None:
                return read_data.get_404_response("Member")

            member_role = member.role.name

            # We should not allow admin to change other admin user password
            if member_role == "admin" and logged_in_user.uuid != member_uuid:
                return read_data.get_403_response()

            user = member.user

        except (ValidationError, User.DoesNotExist) as e:
            logger.info(e)
            return read_data.get_404_response("User")

        # Set password
        new_password = request.data.get("new_password")
        confirm_new_password = request.data.get("confirm_new_password")

        if new_password != confirm_new_password:
            return Response(
                {"message": "Password does not match"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)
        user.save()

        # TODO HIGH: Log user out of all sessions
        # logout(member)

        return Response(
            {"message": "Password has been set"},
            status=status.HTTP_200_OK,
        )


class LoginAPI(views.APIView):

    permission_classes = []

    def post(self, request, *args, **kwargs):

        # User can provide either email or phone number
        username = request.data.get("username")
        password = request.data.get("password")

        if read_data.application_name_is_wrong(request) is True:
            return Response(
                {"message": "Invalid domain name. Please enter the correct domain."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if username is None:
            return Response({"message": "Username is required"}, status=status.HTTP_400_BAD_REQUEST)

        username = username.lower()

        if password is None:
            return Response({"message": "Password is required"}, status=status.HTTP_400_BAD_REQUEST)

        users = User.objects.filter(Q(email__iexact=username) | Q(phone_number=username))
        if not users.exists():
            return Response({"message": "Invalid credentials"}, status=status.HTTP_400_BAD_REQUEST)
        temp_user = users.first()

        try:
            user = authenticate(request, username=temp_user.username, password=password)
            if user is not None:

                # If remember me has been checked, set expiry time to 1 week
                if request.data.get("remember-me", None):
                    request.session.set_expiry(60 * 60 * 24 * 7)
                # Login the user
                login(request, user)

        except (User.DoesNotExist) as e:
            logger.error(e)
            return Response({"message": "Invalid credentials"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(f"Add exception for {e.__class__.__name__} in LoginAPI")
            logger.error(e)
            return Response({"message": "Invalid credentials"}, status=status.HTTP_400_BAD_REQUEST)

        if user:
            org_uuid = request.headers.get("organization-uuid")
            org = fetch_data.get_organization2(user)
            member = fetch_data.get_member(user, org.uuid)
            organization = member.organization
            if organization.status == "inactive":
                return Response({"message": "Organization inactive. Unable to login."}, status=status.HTTP_400_BAD_REQUEST)

        if user is not None:

            auth_tokens = user.auth_tokens.filter(active=True)
            if auth_tokens.count() == 0:
                auth_token = AuthToken.objects.create(
                    user=user,
                    name=create_data.generate_random_string(10),
                )
            else:
                auth_token = auth_tokens.order_by("-id").first()

            return Response({"token": auth_token.key}, status=status.HTTP_200_OK)
        else:
            return Response({"message": "Invalid credentials"}, status=status.HTTP_400_BAD_REQUEST)


class LogoutAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]

    def post(self, request, *args, **kwargs):
        logout(request)
        return Response({}, status=status.HTTP_200_OK)


class UserDataAPI(views.APIView):
    """return the data of requesting user"""

    # permission_classes = [permissions.IsTokenAuthenticated]

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        member = fetch_data.get_member(request.user, org.uuid)
        user = request.user

        role = RoleSerializer(member.role)
        member_serializer = MemberSerializer(member)

        data = {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone_number": user.phone_number,
            "role": role.data,
            "member": member_serializer.data,
        }

        return Response(data, status=status.HTTP_200_OK)


class TestAPI(views.APIView):

    permission_classes = []

    def get(self, request, *args, **kwargs):
        logger.error("hello")
        return Response({"message": "Hello"}, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        return Response({"message": "Success"}, status=status.HTTP_201_CREATED)


class FetchFileAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org.uuid)

        path = self.kwargs.get("path")
        try:
            filename = path.split("/")[-1]
            file_instance_uuid = filename.split("__")[0]

            if "profile" in path:
                logger.info(f"{path=}")
                file_member = fetch_data.get_member_by_uuid(org_uuid, file_instance_uuid)
                if file_member is None:
                    return read_data.get_404_response("Member")

                if member.organization != file_member.organization:
                    return read_data.get_403_response()

        except Exception as e:
            logger.error(e)
            logger.exception(f"Add exception for {e.__class__.__name__} in FetchFileAPI")

        file_extension = filename.split(".")[-1]
        if file_extension in ["jpeg", "jpg", "png"]:
            response = HttpResponse(content_type=f"image/{file_extension}")
            try:
                with open(path, "rb") as img:
                    read_image = img.read()
                    response.write(read_image)
            except FileNotFoundError as e:
                logger.error(e)
                return read_data.get_404_response("File")
            except Exception as e:
                logger.error(e)
                logger.exception(f"Add exception for {e.__class__.__name__} in FetchFileAPI")
                return Response(
                    {"message": "Unknown error occurred"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        elif file_extension in ["pdf"]:
            try:
                response = HttpResponse(content_type=f"application/{file_extension}")
                # response["Content-Disposition"] = f"attachment; filename={filename}"
                with open(path, "rb") as img:
                    read_image = img.read()
                    response.write(read_image)
            except Exception as e:
                logger.error(e)
                logger.exception(f"Add exception for {e.__class__.__name__} in FetchFileAPI")
                return Response(
                    {"message": "Unknown error occurred"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        elif file_extension in ["csv"]:
            try:
                response = HttpResponse(content_type=f"text/{file_extension}")
                # response["Content-Disposition"] = f"attachment; filename={filename}"
                with open(path, "rb") as csv:
                    read_csv = csv.read()
                    response.write(read_csv)
            except Exception as e:
                logger.error(e)
                logger.exception(f"Add exception for {e.__class__.__name__} in FetchFileAPI")
                return Response(
                    {"message": "Unknown error occurred"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            return Response(
                {"message": "Unknown file extension"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return response
