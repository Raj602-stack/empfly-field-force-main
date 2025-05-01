from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

from account.views import helath_check_view


urlpatterns = [
    path("api/admin/", admin.site.urls),
    path("api/", include("api.urls")),
    path('api/health-check/7uYERLmLeXR_VxUn5JOG3DxGHlYNtBcwIiXGqOsYMyc/', helath_check_view.CustomHealthCheckView.as_view()),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += staticfiles_urlpatterns()

schema_view = get_schema_view(
    openapi.Info(
        title="Field Force API",
        default_version="v1",
        description="API Documentation for Field Force",
        terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email="support@empfly.com"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
    authentication_classes=None,
)

urlpatterns += [
    re_path(
        r"^swagger(?P<format>\.json|\.yaml)$",
        schema_view.without_ui(cache_timeout=0),
        name="schema-json",
    ),
    re_path(
        r"^swagger/$",
        schema_view.with_ui("swagger", cache_timeout=0),
        name="schema-swagger-ui",
    ),
    re_path(r"^redoc/$", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),
]
