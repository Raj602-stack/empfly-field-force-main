from django.contrib import admin

from member.models import Member, Profile, MemberImage

admin.site.register(Member)
admin.site.register(Profile)
admin.site.register(MemberImage)
