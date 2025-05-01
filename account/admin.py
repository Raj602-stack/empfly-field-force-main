from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from account.models import User, AuthToken, SessionToken

admin.site.register(User, UserAdmin)
# admin.site.register(User)
admin.site.register(AuthToken)
admin.site.register(SessionToken)
