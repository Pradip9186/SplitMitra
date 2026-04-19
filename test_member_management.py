"""
Comprehensive test script for Member Management feature
Tests all backend functionality without needing browser session
"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'splitmitra.settings')
django.setup()

from django.contrib.auth.models import User
from expenses.models import Group, GroupMember, GroupActivity
from django.test.client import Client
import json

print("=" * 70)
print("SPLITMITRA - MEMBER MANAGEMENT FEATURE TESTING")
print("=" * 70)

# Get test user and group
user = User.objects.get(username='gaurav@example.com')
another_user = User.objects.get(username='another@example.com')
third_user = User.objects.get(username='third@example.com')
group = Group.objects.get(id=13)

print(f"\n✅ Test Data:")
print(f"   Group: {group.name} (ID: {group.id})")
print(f"   Admin: {user.first_name} ({user.username})")
print(f"   Members: {list(group.members.values_list('first_name', flat=True))}")

# Create test client
client = Client()

# Test 1: Login
print(f"\n\n{'='*70}")
print("TEST 1: LOGIN")
print("=" * 70)
login_success = client.login(username='gaurav@example.com', password='password123')
print(f"✅ Login: {'SUCCESS' if login_success else 'FAILED'}")

if login_success:
    # Test 2: Access Group Detail Page
    print(f"\n{'='*70}")
    print("TEST 2: ACCESS GROUP DETAIL PAGE")
    print("=" * 70)
    response = client.get(f'/group/{group.id}/')
    print(f"✅ Status Code: {response.status_code}")
    print(f"✅ Template Used: {[t.name for t in response.templates]}")
    print(f"✅ Context Variables: {list(response.context.keys()) if response.context else 'None'}")
    
    # Check if settings gear icon is in the response
    if 'bi-gear-fill' in response.content.decode():
        print(f"✅ Settings Gear Icon Found: YES")
    else:
        print(f"⚠️ Settings Gear Icon Found: NO")
    
    # Check if settings modal is in the response
    if 'id="settingsModal"' in response.content.decode():
        print(f"✅ Settings Modal HTML: YES")
    else:
        print(f"⚠️ Settings Modal HTML: NO")
    
    # Check if member list is in the response
    if 'GROUP MEMBERS' in response.content.decode():
        print(f"✅ Member List HTML: YES")
    else:
        print(f"⚠️ Member List HTML: NO")
    
    # Test 3: Make Admin Functionality
    print(f"\n{'='*70}")
    print("TEST 3: MAKE ADMIN FUNCTIONALITY")
    print("=" * 70)
    
    print(f"\n   Before: {another_user.first_name} - Role: Member")
    print(f"   Admin: {user.first_name} (ID: {user.id})")
    print(f"   Member to Promote: {another_user.first_name} (ID: {another_user.id})")
    
    # POST request to make_admin
    response = client.post(f'/group/{group.id}/make-admin/{another_user.id}/')
    print(f"\n✅ Make Admin Response Status: {response.status_code}")
    
    # Check if GroupMember entry was created
    group_member = GroupMember.objects.filter(
        group=group,
        user=another_user
    ).first()
    
    if group_member and group_member.role == 'admin':
        print(f"✅ GroupMember Role Updated: {group_member.role}")
    else:
        print(f"⚠️ GroupMember Role: {group_member.role if group_member else 'NOT FOUND'}")
    
    # Check if activity log entry was created
    activity = GroupActivity.objects.filter(
        group=group,
        action_type='ownership_transferred'
    ).last()
    
    if activity:
        print(f"✅ Activity Log Entry Created: YES")
        print(f"   Action: {activity.action_type}")
        print(f"   Description: {activity.description}")
        print(f"   By: {activity.action_by.first_name}")
    else:
        print(f"⚠️ Activity Log Entry: NOT FOUND")
    
    # Test 4: Remove Member Functionality
    print(f"\n{'='*70}")
    print("TEST 4: REMOVE MEMBER FUNCTIONALITY")
    print("=" * 70)
    
    print(f"\n   Group Members Before: {group.members.count()}")
    print(f"   Member to Remove: {third_user.first_name} (ID: {third_user.id})")
    
    # POST request to remove_member
    response = client.post(f'/group/{group.id}/remove-member/{third_user.id}/')
    print(f"\n✅ Remove Member Response Status: {response.status_code}")
    
    # Check if member was removed from group
    group.refresh_from_db()
    if third_user not in group.members.all():
        print(f"✅ Member Removed: YES")
    else:
        print(f"⚠️ Member Still in Group: YES")
    
    print(f"   Group Members After: {group.members.count()}")
    
    # Check if activity log entry was created
    activity = GroupActivity.objects.filter(
        group=group,
        action_type='member_removed'
    ).last()
    
    if activity:
        print(f"✅ Activity Log Entry Created: YES")
        print(f"   Action: {activity.action_type}")
    else:
        print(f"⚠️ Activity Log Entry: NOT FOUND")
    
    # Test 5: Member List Context
    print(f"\n{'='*70}")
    print("TEST 5: MEMBER LIST IN TEMPLATE CONTEXT")
    print("=" * 70)
    
    response = client.get(f'/group/{group.id}/')
    if response.context:
        group_obj = response.context.get('group')
        if group_obj:
            members = group_obj.members.all()
            print(f"\n✅ Members in Context: {members.count()}")
            for member in members:
                is_admin = member == group_obj.created_by
                print(f"   - {member.first_name} ({member.email}) - {'ADMIN' if is_admin else 'MEMBER'}")
        else:
            print(f"⚠️ Group object not in context")
    
    # Test 6: CSS Classes Verification
    print(f"\n{'='*70}")
    print("TEST 6: CSS CLASSES IN TEMPLATE")
    print("=" * 70)
    
    response = client.get(f'/group/{group.id}/')
    content = response.content.decode()
    
    css_classes = [
        'member-item',
        'member-avatar',
        'member-details',
        'admin-badge',
        'member-menu-btn',
        'member-context-menu',
        'add-more-members-btn'
    ]
    
    for css_class in css_classes:
        found = f'class="{css_class}"' in content or f'class="{css_class} ' in content
        print(f"{'✅' if found else '⚠️'} CSS Class '{css_class}': {'FOUND' if found else 'NOT FOUND'}")
    
    # Test 7: JavaScript Functions
    print(f"\n{'='*70}")
    print("TEST 7: JAVASCRIPT FUNCTIONS IN TEMPLATE")
    print("=" * 70)
    
    js_functions = [
        'getCSRFToken',
        'toggleMemberMenu',
        'makeAdmin',
        'removeMember',
        'toggleCustomSplit'
    ]
    
    for js_func in js_functions:
        found = f'function {js_func}' in content
        print(f"{'✅' if found else '⚠️'} JS Function '{js_func}': {'FOUND' if found else 'NOT FOUND'}")

else:
    print("⚠️ Login failed - cannot proceed with tests")

print(f"\n{'='*70}")
print("TESTING COMPLETE")
print("=" * 70)
