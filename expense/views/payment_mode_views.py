
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.core.files.base import ContentFile
from django.db import IntegrityError
from django.db.models import Q
from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated


from api import permissions
from expense.models import PaymentMode
from expense import serializers
from expense.utils import get_payment_mode
from utils import fetch_data, read_data

import logging


logger = logging.getLogger(__name__)


class AllPaymentModesAPI(views.APIView):
    """ Like cash. Just to know the admin.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = serializers.PaymentModeSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_or_finance(member) is False:
            return read_data.get_403_response()

        payment_modes = org.payment_modes.all()
        per_page = request.GET.get("per_page", 10)
        page = request.GET.get("page", 1)
        paginator = Paginator(payment_modes, per_page)
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
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        name = request.data.get("name")
        description = request.data.get("description")

        try:
            payment_mode = PaymentMode.objects.create(
                organization=org, name=name, description=description
            )
        except IntegrityError as e:
            logger.error(e)
            return read_data.get_409_response("Payment Mode", "name")

        except Exception as e:
            logger.error(e)
            logger.exception(
                f"Add exception for {e.__class__.__name__} in AllPaymentModesAPI"
            )
            return Response(
                {"message": "Unkown error occurred"}, status=status.HTTP_400_BAD_REQUEST
            )

        serializer = self.serializer_class(payment_mode)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class PaymentModesAPI(views.APIView):

    permission_classes = [IsAuthenticated]
    serializer_class = serializers.PaymentModeSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_or_finance(member) is False:
            return read_data.get_403_response()

        uuid = self.kwargs.get("uuid")
        payment_mode = get_payment_mode(org.uuid, uuid)
        if payment_mode is None:
            return read_data.get_404_response("Payment Mode")

        serializer = self.serializer_class(payment_mode)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        uuid = self.kwargs.get("uuid")
        payment_mode = get_payment_mode(org.uuid, uuid)
        if payment_mode is None:
            return read_data.get_404_response("Payment Mode")

        name = request.data.get("name")
        description = request.data.get("description")

        payment_mode.name = name
        payment_mode.description = description

        try:
            payment_mode.save()
        except IntegrityError as e:
            logger.error(e)
            return read_data.get_409_response("Payment Mode", "name")
        except Exception as e:
            logger.error(e)
            logger.exception(
                f"Add exception for {e.__class__.__name__} in AllPaymentModesAPI"
            )
            return Response(
                {"message": "Unkown error occurred"}, status=status.HTTP_400_BAD_REQUEST
            )

        serializer = self.serializer_class(payment_mode)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        uuid = self.kwargs.get("uuid")
        payment_mode = get_payment_mode(org.uuid, uuid)
        if payment_mode is None:
            return read_data.get_404_response("Payment Mode")

        payment_mode.delete()
        return read_data.get_200_delete_response("Payment Mode")
