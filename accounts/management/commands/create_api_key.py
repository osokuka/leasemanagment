from django.core.management.base import BaseCommand, CommandError

from accounts.models import ApiKeyScope, User, UserApiKey


class Command(BaseCommand):
    help = 'Create a scoped API key for a user. The raw key is printed once.'

    def add_arguments(self, parser):
        parser.add_argument('username', help='Owner username')
        parser.add_argument(
            '--name',
            default='External KESCO tool',
            help='Human-readable key name',
        )
        parser.add_argument(
            '--scope',
            default=ApiKeyScope.KESCO_METER_WRITE,
            choices=[choice[0] for choice in ApiKeyScope.choices],
            help='API key scope',
        )

    def handle(self, *args, **options):
        username = options['username'].strip().lower()
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist as exc:
            raise CommandError(f'User "{username}" does not exist.') from exc

        key, raw_key = UserApiKey.create_key(
            user=user,
            name=options['name'],
            scope=options['scope'],
        )
        self.stdout.write(self.style.SUCCESS(f'Created API key {key.uuid} for {user.username}.'))
        self.stdout.write('Copy this key now; it will not be shown again:')
        self.stdout.write(raw_key)
