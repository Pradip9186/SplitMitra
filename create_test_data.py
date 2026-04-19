import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'splitmitra.settings')
django.setup()

from django.contrib.auth.models import User
from expenses.models import Group

# Check if user exists
user = User.objects.filter(username='gaurav@example.com').first()
if not user:
    user = User.objects.create_user(
        username='gaurav@example.com',
        email='gaurav@example.com',
        password='password123',
        first_name='Gaurav'
    )
    print(f"User created: {user.username}")
else:
    print(f"User already exists: {user.username}")

# Create a test group with 3 members if not exists
group = Group.objects.filter(name='Test Group').first()
if not group:
    group = Group.objects.create(
        name='Test Group',
        created_by=user,
        category='Friends'
    )
    group.members.add(user)
    print(f"Group created: {group.name}")
    
    # Add more members
    user2 = User.objects.filter(username='another@example.com').first()
    if not user2:
        user2 = User.objects.create_user(
            username='another@example.com',
            email='another@example.com',
            password='password123',
            first_name='Another'
        )
    group.members.add(user2)
    
    user3 = User.objects.filter(username='third@example.com').first()
    if not user3:
        user3 = User.objects.create_user(
            username='third@example.com',
            email='third@example.com',
            password='password123',
            first_name='Third'
        )
    group.members.add(user3)
    print(f"Members added to group: {group.members.count()}")
else:
    print(f"Group already exists: {group.name} (ID: {group.id})")

print("\nUsers in database:")
for u in User.objects.all():
    print(f"  - {u.username} ({u.first_name})")

print(f"\nGroup ID for testing: {group.id}")
