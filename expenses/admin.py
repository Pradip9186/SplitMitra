from django.contrib import admin
from .models import Group, Expense

# --- 1. GROUP ADMIN CONFIGURATION ---
@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    # Admin list me ye columns dikhenge
    list_display = ('name', 'category', 'created_by', 'member_count', 'created_at')
    
    # Search bar se aap group ka naam search kar payenge
    search_fields = ('name',)
    
    # Right side me category wise filter aayega
    list_filter = ('category', 'created_at')

    # Custom function: Group me kitne members hain wo dikhane ke liye
    def member_count(self, obj):
        return obj.members.count()
    member_count.short_description = 'Total Members'


# --- 2. EXPENSE ADMIN CONFIGURATION ---
@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    # Kaunsa kharcha, kitna, aur kisne kiya
    list_display = ('description', 'amount', 'group', 'paid_by', 'date')
    
    # Expenses ko group aur date ke hisaab se filter karne ke liye
    list_filter = ('group', 'date', 'paid_by')
    
    # Description aur Group name se search karne ke liye
    search_fields = ('description', 'group__name')
    
    # Dashboard par list ko date ke hisaab se sort rakhega (Naya pehle)
    ordering = ('-date',)