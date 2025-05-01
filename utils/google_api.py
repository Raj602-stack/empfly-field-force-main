import json
import logging

import requests
from django.conf import settings
from rest_framework.response import Response

from utils import read_data

logger = logging.getLogger(__name__)


def send_request(request, url: str, params: dict = {}, method: str = "GET") -> Response:
    """ send req to urls. for check distance using google map we can use this.
    """

    api_params = get_api_key(request)
    params.update(api_params)

    try:
        response = requests.request(method, url, params=params, timeout=10)
    except ConnectionError as e:
        logger.error(e)
        return Response({"message": "Failed to send request"}, status=500)
    except Exception as e:
        logger.error(e)
        logger.exception(f"Add exception for {e.__class__.__name__} in send_request")
        return Response({"message": "Failed to send request"}, status=500)

    logger.info(f"Status code: {response.status_code}")
    return response


def get_api_key(request) -> dict:
    """ get org google api key.
    """
    member = request.user.members.first()
    if member and member.organization:
        try:
            external_connection = member.organization.external_connections.first()
            if external_connection.status:
                return {"key": read_data.decrypt_text(external_connection.gcp_api_key)}
        except Exception as e:
            logger.error(e)
    return {"key": ""}


def get_gcp_api_key_is_active(request):
    """ Check google api key is active.
    """
    member = request.user.members.first()
    if member and member.organization:
        try:
            external_connection = member.organization.external_connections.first()
            if external_connection.status:
                return True
        except Exception as e:
            logger.error(e)
    return False


def calculate_distance_and_duration(request, point1: tuple, point2: tuple) -> tuple:
    """ calculate distance and duration for trips details.
    """

    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {"origins": point1, "destinations": point2}

    response = send_request(request, url, params=params)
    json_response = read_data.get_json(response, {})

    if response.status_code == 200:
        try:
            distance = json_response.get("rows")[0].get("elements")[0].get("distance", {}).get("value")
        except (KeyError, IndexError) as e:
            logger.error(e)
            distance = None
        try:
            duration = json_response.get("rows")[0].get("elements")[0].get("duration", {}).get("value")
        except (KeyError, IndexError) as e:
            logger.error(e)
            distance = None

        # distance in meters
        # https://developers.google.com/maps/documentation/distance-matrix/distance-matrix#DistanceMatrixElement-distance
        # duration in seconds
        # https://developers.google.com/maps/documentation/distance-matrix/distance-matrix#DistanceMatrixElement-duration
        return distance, duration

    else:
        logger.error(f"Status code: {response.status_code}")
        return None, None


def search_location(request, query_params) -> dict:
    """ search location from google map.
    """

    url = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
    params = query_params.copy()

    response = send_request(request, url, params=params)
    json_response = read_data.get_json(response, [])
    if response is None:
        return Response({"message": "Unknown error occurred"}, status=400)
    return json_response


def get_geo_code(request, query_params):

    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = query_params.copy()

    response = send_request(request, url, params=params)
    json_response = read_data.get_json(response, [])
    if response is None:
        return Response({"message": "Unknown error occurred"}, status=400)
    return json_response


def check_google_map_api_is_valid(key: str, input="bangalore"):
    """ Check API key provided is valid. For that req to google API.
    """
    url = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
    params = {"input": input, "radius": 50000, "key": key}

    response = requests.request("GET", url, params=params, timeout=10)
    return response
