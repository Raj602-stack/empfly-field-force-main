from typing import Dict, List, Union
from rest_framework.response import Response
from rest_framework import views, status

def HTTP_200(data : Union[Dict, List[Dict]] ) -> Response:
    return Response({"data": data})

def HTTP_400(data : Union[Dict, List[Dict], str] = None) -> Response:


    if isinstance(data, str):
        data = {"message": data}
    return Response(
        data,
        status=status.HTTP_400_BAD_REQUEST
    )
