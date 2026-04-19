from django.contrib import admin
from .models import Group, Expense, UserProfile, GroupMember, InviteLink, GroupActivity, ExpenseShare, Bill

# --- 1. USER PROFILE ADMIN ---
@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone_number', 'upi_id')
    search_fields = ('user__username', 'user__email', 'upi_id')


# --- 2. GROUP ADMIN CONFIGURATION ---
@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'created_by', 'member_count', 'is_archived', 'created_at')
    search_fields = ('name', 'description')
    list_filter = ('category', 'created_at', 'is_archived')
    readonly_fields = ('created_at', 'updated_at')

    def member_count(self, obj):
        return obj.group_members.count()
    member_count.short_description = 'Total Members'


# --- 3. GROUP MEMBER ADMIN ---
@admin.register(GroupMember)
class GroupMemberAdmin(admin.ModelAdmin):
    list_display = ('user', 'group', 'role', 'joined_at')
    search_fields = ('user__username', 'group__name')
    list_filter = ('role', 'joined_at')


# --- 4. INVITE LINK ADMIN ---
@admin.register(InviteLink)
class InviteLinkAdmin(admin.ModelAdmin):
    list_display = ('group', 'created_by', 'is_active', 'used_count', 'max_uses', 'created_at')
    search_fields = ('group__name', 'token')
    list_filter = ('is_active', 'created_at')
    readonly_fields = ('token', 'created_at')


# --- 5. GROUP ACTIVITY ADMIN ---
@admin.register(GroupActivity)
class GroupActivityAdmin(admin.ModelAdmin):
    list_display = ('group', 'action_by', 'action_type', 'timestamp')
    search_fields = ('group__name', 'action_by__username', 'description')
    list_filter = ('action_type', 'timestamp')
    readonly_fields = ('timestamp',)


# --- 6. EXPENSE ADMIN CONFIGURATION ---
@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('description', 'amount', 'group', 'paid_by', 'date', 'is_deleted')
    list_filter = ('group', 'date', 'paid_by', 'is_deleted')
    search_fields = ('description', 'group__name')
    ordering = ('-date',)


# --- 7. EXPENSE SHARE ADMIN ---
@admin.register(ExpenseShare)
class ExpenseShareAdmin(admin.ModelAdmin):
    list_display = ('user', 'expense', 'amount_owed')
    search_fields = ('user__username', 'expense__description')
    list_filter = ('expense__group',)


# --- 8. BILL ADMIN (Advanced File Upload Management) ---
@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    list_display = (
        'file_name',
        'expense',
        'uploaded_by',
        'file_type',
        'file_size_mb',
        'is_primary',
        'is_public',
        'download_count',
        'uploaded_at'
    )
    list_filter = ('file_type', 'is_primary', 'is_public', 'uploaded_at')
    search_fields = ('file_name', 'expense__description', 'uploaded_by__username', 'description')
    readonly_fields = ('file_name', 'file_size', 'uploaded_at', 'download_count', 'last_downloaded_by', 'last_downloaded_at')
    
    fieldsets = (
        ('File Information', {
            'fields': ('file', 'file_name', 'file_size', 'file_type', 'description')
        }),
        ('Relationship', {
            'fields': ('expense', 'uploaded_by')
        }),
        ('Settings', {
            'fields': ('is_primary', 'is_public')
        }),
        ('Audit Trail', {
            'fields': ('uploaded_at', 'download_count', 'last_downloaded_by', 'last_downloaded_at'),
            'classes': ('collapse',)
        }),
    )
    
    def file_size_mb(self, obj):
        return f"{obj.file_size_mb} MB"
    file_size_mb.short_description = 'File Size'
    
    def get_readonly_fields(self, request, obj=None):
        """Make certain fields read-only after creation"""
        readonly = list(self.readonly_fields)
        if obj:  # Editing existing object
            readonly.extend(['expense', 'uploaded_by', 'file'])
        return readonly