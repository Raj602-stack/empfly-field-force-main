# myapp/management/commands/onboard.py

from django.core.management.base import BaseCommand
from organization.org_delete import delete_organization

class Command(BaseCommand):
    help = 'Delete organization'

    def handle(self, *args, **options):
        delete_organization()