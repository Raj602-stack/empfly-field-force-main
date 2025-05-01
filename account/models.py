import uuid

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import IntegrityError, models
from django.db.models import Q
from django.utils import crypto
from django.utils.translation import gettext_lazy as _
from rest_framework.authtoken.models import Token


class UserManager(BaseUserManager):
    def create_user(self, email, password, first_name=None, last_name=None):

        if not email:
            raise ValueError("User must have an email")

        if not password:
            raise ValueError("User must have a password")

        # Normalize the email address by lowercasing the domain part of it
        user = self.model(email=self.normalize_email(email))

        user.set_password(password)
        user.first_name = first_name
        user.last_name = last_name

        user.is_active = False
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, first_name=None, last_name=None):

        if not email:
            raise ValueError("User must have an email")

        if not password:
            raise ValueError("User must have a password")

        # Normalize the email address by lowercasing the domain part of it
        user = self.model(email=self.normalize_email(email))
        # Calls the create_user method mentioned above
        user = self.create_user(email, password, first_name, last_name)

        user.is_superuser = True
        user.is_staff = True
        user.is_active = True
        user.save(using=self._db)

        return user


class User(AbstractUser):
    """View level restrictions are added for user limit."""

    username = models.CharField(max_length=200, unique=True)

    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    email = models.EmailField(null=True, blank=True, unique=True)
    # TODO LOW: Rename to phone
    phone_number = models.CharField(max_length=15, null=True, blank=True, unique=True)

    # first_name = models.CharField(max_length=200, null=True, blank=True)
    first_name = models.CharField(max_length=200)
    last_name = models.CharField(max_length=200, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    recent_organization_uid = models.CharField(max_length=200, null=True, blank=True)

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def save(self, *args, **kwargs):
        """View level restrictions are added for user limit.
        Added Max User limit for organization logic in Application level
        bulk upload & create member API has that check"""

        if not self.first_name:
            raise ValueError("First Name is required.")

        users = User.objects.all()

        self.email = self.email if self.email else None
        self.phone_number = self.phone_number if self.phone_number else None

        # If user is being created
        if self.pk is None:
            # If email exists, set username to email
            # Else set username to phone number
            if self.email:
                self.email = self.email.lower()
                self.username = self.email.lower()
            elif self.phone_number:
                self.username = self.phone_number.lower()
            elif self.username:
                self.username = self.username.lower()
            else:
                raise ValueError
        else:
            if self.email:
                self.email = self.email.lower()
                self.username = self.email.lower()
                users = users.exclude(id=self.pk)
            elif self.phone_number:
                self.username = self.phone_number
                users = users.exclude(id=self.pk)

        if self.username:
            if users.filter(username=self.username).exists():
                raise IntegrityError

        if self.email:
            if users.filter(email=self.email).exists():
                raise IntegrityError

        if self.phone_number:
            if users.filter(phone_number=self.phone_number).exists():
                raise IntegrityError

        super(User, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.username}__{self.uuid}"


class AuthToken(Token):
    """
    API tokens that allows users to make API calls
    """

    key = models.CharField(_("Key"), max_length=40, db_index=True, unique=True)
    user = models.ForeignKey(
        User,
        related_name="auth_tokens",
        on_delete=models.CASCADE,
        verbose_name=_("User"),
    )

    active = models.BooleanField(default=True)
    name = models.CharField(_("Name"), max_length=64)

    expires_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        User,
        related_name="auth_tokens_created",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        unique_together = (("user", "name"),)

    def __str__(self):
        return f"{self.user}_{self.name}"


class SessionToken(models.Model):
    """
    Unique token value used in single use links
    i.e., account activation, password reset etc
    """

    user = models.ForeignKey(User, related_name="session_tokens", on_delete=models.CASCADE)
    token = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.email}__{self.token}"
