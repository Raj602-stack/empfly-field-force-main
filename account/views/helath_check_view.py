from env import HEALTH_CHECK_AUTH_TOKEN
import json
from django.http import JsonResponse
from rest_framework.renderers import JSONRenderer
from health_check.views import MainView

class CustomHealthCheckView(MainView):
    def get(self, request, *args, **kwargs):
        # Add any additional logic or customization here
    
        if "HTTP_X_HEALTH_CHECK_AUTH_TOKEN" not in request.META:
            renderer = JSONRenderer()
            response = renderer.render({'message': 'Authentication credentials were not provided..'}, renderer_context={'request': request})
            return JsonResponse(json.loads(response), status=401)

        health_check_token_in_request = request.META["HTTP_X_HEALTH_CHECK_AUTH_TOKEN"]

        if health_check_token_in_request != HEALTH_CHECK_AUTH_TOKEN:
            renderer = JSONRenderer()
            response = renderer.render({'message': 'Authentication credentials were not provided..'}, renderer_context={'request': request})
            return JsonResponse(json.loads(response), status=401)

        # Health check pkg validating the service and creating the response .
        default_response = super().get(request, *args, **kwargs)

        # Converting the health check response to python dict.
        default_data = default_response.content.decode('utf-8')
        default_data_dict: dict = json.loads(default_data)

	    # If you want to add some additional key to the response or additional logic we can add here
        # default_data_dict is just a dict if you want you can customize or add new key to default_data_dict dict.

        for _ , curr_status in default_data_dict.items():
            if curr_status == "working":
                continue

            # If some service is not working throw 500 error.
            return JsonResponse(default_data_dict, safe=False, status=500)

        return JsonResponse(default_data_dict, safe=False)
