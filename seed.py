#!/usr/bin/env python
"""
Seed script to create initial users.
Run with: docker compose exec web python seed.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')
django.setup()

from accounts.models import User, Role

def seed():
    # Create super user
    if not User.objects.filter(username='admin').exists():
        superuser = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='admin123',
            role=Role.SUPER_USER,
        )
        print(f'Created superuser: {superuser.username}')
    else:
        print('Superuser already exists.')

    # Create admin user
    if not User.objects.filter(username='manager').exists():
        admin = User.objects.create_user(
            username='manager',
            email='manager@example.com',
            password='manager123',
            role=Role.ADMIN,
        )
        print(f'Created admin: {admin.username}')
    else:
        print('Admin user already exists.')

    # Create data entry clerk
    if not User.objects.filter(username='clerk').exists():
        clerk = User.objects.create_user(
            username='clerk',
            email='clerk@example.com',
            password='clerk123',
            role=Role.DATA_ENTRY_CLERK,
        )
        print(f'Created data entry clerk: {clerk.username}')
    else:
        print('Clerk user already exists.')

    print('\nSeed complete!')
    print('\nLogin credentials:')
    print('  Super User: admin / admin123')
    print('  Admin:      manager / manager123')
    print('  Clerk:      clerk / clerk123')

if __name__ == '__main__':
    seed()
