from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from accounts.models import ApiKeyScope, Role, User, UserApiKey


class UserApiKeyPanelTests(TestCase):
    def setUp(self):
        self.super_user = User.objects.create_user(
            username='owner',
            password='pass12345',
            role=Role.SUPER_USER,
            is_superuser=True,
        )
        self.admin = User.objects.create_user(
            username='manager',
            password='pass12345',
            role=Role.ADMIN,
        )
        self.clerk = User.objects.create_user(
            username='clerk',
            password='pass12345',
            role=Role.DATA_ENTRY_CLERK,
        )

    def test_super_user_can_generate_and_revoke_api_key_from_user_panel(self):
        self.client.force_login(self.super_user)

        response = self.client.post(
            reverse('accounts:user_api_key_create', args=[self.clerk.uuid]),
            {'name': 'External sync'},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        api_key = UserApiKey.objects.get(user=self.clerk)
        self.assertEqual(api_key.name, 'External sync')
        self.assertEqual(api_key.scope, ApiKeyScope.KESCO_METER_WRITE)
        messages = [str(message) for message in get_messages(response.wsgi_request)]
        self.assertTrue(any('bmgm_' in message for message in messages))

        response = self.client.post(
            reverse('accounts:user_api_key_revoke', args=[self.clerk.uuid, api_key.uuid]),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        api_key.refresh_from_db()
        self.assertFalse(api_key.is_active)

    def test_admin_can_only_generate_key_for_data_entry_clerk(self):
        self.client.force_login(self.admin)

        allowed = self.client.post(
            reverse('accounts:user_api_key_create', args=[self.clerk.uuid]),
            {'name': 'Allowed'},
        )
        forbidden = self.client.post(
            reverse('accounts:user_api_key_create', args=[self.super_user.uuid]),
            {'name': 'Forbidden'},
        )

        self.assertEqual(allowed.status_code, 302)
        self.assertEqual(forbidden.status_code, 403)
        self.assertTrue(UserApiKey.objects.filter(user=self.clerk).exists())
        self.assertFalse(UserApiKey.objects.filter(user=self.super_user).exists())
