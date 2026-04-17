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
    group_balances,  
    settle_up,       
    settings_view,
    friends_view     
)

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
    path('settings/', settings_view, name='settings'),
    path('friends/', friends_view, name='friends'), 
    
    # --- Group Detail & Balances (Real-time tracking) ---
    path('group/<int:group_id>/', group_detail, name='group_detail'),
    path('group/<int:group_id>/balances/', group_balances, name='group_balances'), 
    path('group/<int:group_id>/settle/<int:receiver_id>/', settle_up, name='settle_up'), 
    
    # --- Group & Expense Management ---
    path('create-group/', create_group, name='create_group'), 
    path('add-expense/', add_expense, name='add_expense'),   
    path('group/<int:group_id>/add-member/', add_member, name='add_member'),
]