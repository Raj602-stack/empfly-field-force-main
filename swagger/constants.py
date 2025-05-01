from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from drf_yasg.openapi import Parameter, IN_QUERY, IN_BODY, Schema


class SchemaConstants:
    """
    Common values that occur in responses.
    Allows user to re-use these values instead of creating the values from scratch.
    """

    STANDARD_UUID = "3d33485a-3843-41ca-a31f-c2e0f4afb0b0"
    IP_ADDRESS = "49.11.123.40"


class SchemaResponse:
    """
    Standard responses that can be generated
    """

    description = ""

    def __int__(self):
        pass

    def get_200(
        response: dict = {},
        description: str = "OK",
        content_type: str = "application/json",
    ) -> openapi.Response:
        """Generates a 200 response

        Args:
            response (dict, optional): The response to be displayed as sample resonse. Defaults to {}.
            content_type (str, optional): The content-type of the response. Defaults to "application/json".
        """
        return openapi.Response(
            examples={content_type: response}, description=description
        )

    def get_200_delete(
        model: str = None, content_type: str = "application/json"
    ) -> openapi.Response:
        """Generates a standard 200 DELETE response

        Args:
            model (str, optional): The name of the model. Defaults to None
            content_type (str, optional): The content-type of the response. Defaults to "application/json".
        """
        model = model.title()
        response = {
            "message": f"Deleted {model}",
        }
        return openapi.Response(
            examples={content_type: response}, description="Deleted."
        )

    def get_response(
        response: dict = {},
        description: str = "OK",
        content_type: str = "application/json",
    ) -> openapi.Response:
        """Generates a 200 response

        Args:
            response (dict, optional): The response to be displayed as sample resonse. Defaults to {}.
            content_type (str, optional): The content-type of the response. Defaults to "application/json".
        """
        return openapi.Response(
            examples={content_type: response}, description=description
        )

    def get_403(
        model: str = "object", content_type: str = "application/json"
    ) -> openapi.Response:
        """Generates a standard 403 response

        Args:
            content_type (str, optional): The content-type of the response. Defaults to "application/json".
        """
        response = {
            "message": f"You do not have permission to perform operations on this {model}"
        }
        return openapi.Response(
            examples={content_type: response}, description="Permission denied."
        )

    def get_404(
        model: str = None, content_type: str = "application/json"
    ) -> openapi.Response:
        """Generates a standard 404 response

        Args:
            model (str, optional): The name of the model. Defaults to None
            content_type (str, optional): The content-type of the response. Defaults to "application/json".
        """
        model = model.title()
        response = {
            "message": f"{model} not found",
        }
        return openapi.Response(
            examples={content_type: response}, description="Not found."
        )

    def get_409(
        model: str = "object",
        field: str = "name",
        content_type: str = "application/json",
    ) -> openapi.Response:
        """Generates a standard 404 response

        Args:
            model (str, optional): The name of the model. Defaults to None
            content_type (str, optional): The content-type of the response. Defaults to "application/json".
        """
        model = model.title()
        response = {
            "message": f"{model} with {field} already exists",
        }
        return openapi.Response(
            examples={content_type: response}, description="Conflict."
        )

    def get_429(content_type: str = "application/json") -> openapi.Response:
        """Generates a standard 404 response

        Args:
            model (str, optional): The name of the model. Defaults to None
            content_type (str, optional): The content-type of the response. Defaults to "application/json".
        """
        response = {
            "message": "API Rate limit exceeded.",
        }
        return openapi.Response(
            examples={content_type: response}, description="API rate limit exceeded."
        )

    def get_500(content_type: str = "application/json") -> openapi.Response:
        """Generates a standard 404 response

        Args:
            model (str, optional): The name of the model. Defaults to None
            content_type (str, optional): The content-type of the response. Defaults to "application/json".
        """
        response = {
            "message": "Server error",
        }
        return openapi.Response(
            examples={content_type: response},
            description="Unexpected server-side error.",
        )

    default_responses = {
        429: get_429(),
        500: get_500(),
    }


class SchemaParameters:
    def get_per_page(default: int = 10) -> Parameter:
        """Creates parameter for per_page

        Args:
            default (int, optional): The default value of the per_page parameter. Defaults to 10.
        """
        return Parameter(
            name="per_page",
            in_=IN_QUERY,
            description="Number of items returned per page.",
            example="10",
            required=False,
            type=openapi.TYPE_INTEGER,
            default=default,
        )

    def get_page(default: int = 1) -> Parameter:
        """Creates parameter for page

        Args:
            default (int, optional): The default value of the page parameter. Defaults to 1.
        """
        return Parameter(
            name="page",
            in_=IN_QUERY,
            description="Which 'page' of paginated results to return.",
            required=False,
            type=openapi.TYPE_INTEGER,
            example="10",
            default=default,
        )

    def get_uuid(
        object: str = None, name: str = "uuid", in_: openapi = openapi.IN_PATH
    ) -> Parameter:
        object = object.lower()
        return Parameter(
            name=name,
            in_=in_,
            description=f"UUID of the {object}",
            example=SchemaConstants.STANDARD_UUID,
            type="uuid",
        )

    def get_parameter(
        name: str,
        description: str,
        required: bool = True,
        type: str = "string",
        default: str = None,
    ) -> Parameter:
        """

        Args:
            name (_type_): Name of the parameter
            description (_type_): description of the parameter
            required (bool, optional): Is the parameter required. Defaults to True.
            type (str, optional): Data type of the parameter. Defaults to "string".
            default (_type_, optional): Default value of the parameter. Defaults to None.
        """
        return Parameter(
            name=name,
            in_=IN_QUERY,
            description=description,
            required=required,
            type=type,
            default=default,
        )


class SchemaPayload:

    def get_uuid(object: str = None) -> Schema:
        object = object.title()
        return Schema(
            description=f"UUID of the {object}",
            type="uuid",
        )
