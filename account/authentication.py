from rest_framework.authentication import TokenAuthentication
from account.models import AuthToken

class TokenAuthentication(TokenAuthentication):
    model = AuthToken
