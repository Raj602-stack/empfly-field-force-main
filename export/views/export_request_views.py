from django.http import HttpResponse
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q

from rest_framework import status, views
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api import permissions
from export.models import ExportRequest
from export.utils import get_export_request
from utils import fetch_data, read_data

import logging


logger = logging.getLogger(__name__)


class PollExportRequestAPI(views.APIView):

    permission_classes = [IsAuthenticated]
    serializer_class = None

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        uuid = self.kwargs.get("uuid")
        export_request = get_export_request(member, uuid)
        if export_request is None:
            return read_data.get_404_response("Export Request")

        return Response(
            {"status": export_request.status, "link": export_request.link, "uuid": export_request.uuid},
            status=status.HTTP_200_OK,
        )
