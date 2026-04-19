"""
URL configuration for SplitMitra project.

This module defines the routing for the application.
It maps URLs to their corresponding view functions in the 'expenses' app.
"""

from django.contrib import admin
from django.urls import path
from expenses.views import (
    login_view, 
    register_view,  
    dashboard, 
    logout_view, 
    create_group, 
    add_expense,
    group_detail,
    add_member,
    my_groups,
    analytics_view,
    profile_view,
    group_balances,  
    settle_up,       
    group_settings,
    invite_link_api,
    settings_view,
    friends_view,
    send_reminder,
    settle_all_with_friend,
    activity_view,
    # ✅ ADVANCED GROUP MANAGEMENT VIEWS
    delete_group,
    edit_group,
    transfer_ownership,
    remove_member,
    make_admin,
    generate_invite_link,
    join_group_via_link,
    revoke_invite_link,
    group_activity_log,
    get_group_members,
    get_group_details,
    # ✅ BILL MANAGEMENT VIEWS
    upload_bill,
    download_bill,
    delete_bill,
    get_bill_details,
    get_expense_bills,
)
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # --- Django Administrative Interface ---
    path('admin/', admin.site.urls),

    # --- User Authentication Flow ---
    path('', login_view, name='login'),                
    path('register/', register_view, name='register'),  
    path('logout/', logout_view, name='logout'),        
    
    # --- Core Application Pages ---
    path('dashboard/', dashboard, name='dashboard'),  
    path('my-groups/', my_groups, name='my_groups'), 
    path('analytics/', analytics_view, name='analytics'),
    path('profile/', profile_view, name='profile'),
    path('settings/', settings_view, name='settings'),
    path('activity/', activity_view, name='activity'),
    # --- Friends Management ---
    path('friends/', friends_view, name='friends'), 
    path('friends/remind/<int:friend_id>/', send_reminder, name='send_reminder'),
    path('friends/settle_all/<int:friend_id>/', settle_all_with_friend, name='settle_all_with_friend'),
    
    # --- Group Detail & Balances (Real-time tracking) ---
    path('group/<int:group_id>/', group_detail, name='group_detail'),
    path('group/<int:group_id>/balances/', group_balances, name='group_balances'), 
    path('group/<int:group_id>/settings/', group_settings, name='group_settings'),
    path('group/<int:group_id>/invite-link/api/', invite_link_api, name='invite_link_api'),
    path('group/<int:group_id>/settle/<int:receiver_id>/', settle_up, name='settle_up'), 
    
    # --- Group & Expense Management ---
    path('create-group/', create_group, name='create_group'), 
    path('add-expense/', add_expense, name='add_expense'),   
    path('group/<int:group_id>/add-member/', add_member, name='add_member'),
    
    # ✅ ADVANCED GROUP MANAGEMENT URLS
    path('group/<int:group_id>/delete/', delete_group, name='delete_group'),
    path('group/<int:group_id>/edit/', edit_group, name='edit_group'),
    path('group/<int:group_id>/transfer-ownership/', transfer_ownership, name='transfer_ownership'),
    path('group/<int:group_id>/remove-member/<int:member_id>/', remove_member, name='remove_member'),
    path('group/<int:group_id>/make-admin/<int:member_id>/', make_admin, name='make_admin'),
    path('group/<int:group_id>/invite-link/', generate_invite_link, name='generate_invite_link'),
    path('group/<int:group_id>/activity/', group_activity_log, name='group_activity_log'),
    path('invite/<str:token>/join/', join_group_via_link, name='join_group_via_link'),
    path('invite/<int:invite_id>/revoke/', revoke_invite_link, name='revoke_invite_link'),
    
    # --- AJAX Endpoints ---
    path('api/group/<int:group_id>/members/', get_group_members, name='api_get_members'),
    path('api/group/<int:group_id>/details/', get_group_details, name='api_get_details'),
    
    # ✅ BILL MANAGEMENT ENDPOINTS
    path('expense/<int:expense_id>/upload-bill/', upload_bill, name='upload_bill'),
    path('bill/<int:bill_id>/download/', download_bill, name='download_bill'),
    path('bill/<int:bill_id>/delete/', delete_bill, name='delete_bill'),
    path('api/bill/<int:bill_id>/details/', get_bill_details, name='api_bill_details'),
    path('api/expense/<int:expense_id>/bills/', get_expense_bills, name='api_expense_bills'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)