# Customizing django org model forms

from django import forms

from account.models import User
from member.models import Member
from .models import Organization, Role
from django.contrib import admin
from datetime import datetime as dt

from django.core.exceptions import ValidationError


class OrgForm(forms.ModelForm):
    # org_location = forms.CharField()
    first_name = forms.CharField()
    last_name = forms.CharField(required=False)
    email = forms.EmailField()
    password = forms.CharField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance.pk:  # Check if the instance already exists (update scenario)
            # self.fields['org_location'].required = False
            self.fields['first_name'].required = False
            self.fields['email'].required = False
            self.fields['password'].required = False

    def clean(self):
        name = self.cleaned_data.get("name", "").lower().strip()
        # default_shift = self.cleaned_data.get("default_shift")
        # default_org_location = self.cleaned_data.get("default_org_location")

        # if Organization.objects.filter(name=name).exists() is True:
        #     raise ValidationError("org name already exists.")

        # if default_shift:
        #     raise ValidationError("Please unselect Default Shift.")

        # if default_org_location:
        #     raise ValidationError("Please unselect Default Org Location.")

    class Meta:
        # fields = ('name','default_shift', 'default_org_location')
        labels = {
            "name": "org name"
        }

    def save(self, commit: bool = ...):
        return super().save(commit)

class OrgAdmin(admin.ModelAdmin):
    """ User for create organization. From the django admin we can do this.
        The org model have organization_name, first_name, last_name, email, org_location
        this additional field. These field not included in the model for creating org we config it.
    """

    form = OrgForm

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        # Only time of creating org only this functionality works. Time of
        # edit we will skip.
        if request.get_full_path().endswith("change/") is True:
            return

        # create org location, shift and member

        name = request.POST.get("name")
        organization = Organization.objects.get(name=name)

        # org_location = request.POST.get("org_location")
        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")
        email = request.POST.get("email")
        password = request.POST.get("password")


        # create roles
        roles = ["admin", "finance", "member",]
        for role in roles:
            object, _ = Role.objects.get_or_create(name=role)


        # create user
        all_user  = User.objects.filter(email=email)
        if all_user.exists() is False:
            user = User.objects.create(email=email, first_name=first_name, last_name=last_name)
            user.is_active = True
            user.is_superuser = False
            user.is_staff = False
            print(password, "---------password----------")
            user.set_password(password)
            user.save()
        else:
            user = all_user.first()

        organization.save()

        admin_role, _ = Role.objects.get_or_create(name="admin")

        # create member
        member = Member.objects.create(user=user, organization=organization, role=admin_role)
        member.employee_id = f"EMP{member.id}{str(member.uuid)[:4]}"
        member.save()
