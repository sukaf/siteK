from django.core.management.base import BaseCommand
from users.models import User, Profile


class Command(BaseCommand):
    help = 'Create profiles for existing users'

    def handle(self, *args, **options):
        users_without_profiles = User.objects.filter(profile__isnull=True)
        for user in users_without_profiles:
            Profile.objects.create(user=user)
            self.stdout.write(f'Created profile for {user.username}')

        self.stdout.write(self.style.SUCCESS('Successfully created profiles'))

