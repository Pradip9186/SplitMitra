from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
import uuid

# --- 1. User Profile (Updated for UPI ID) ---
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    
    # ✅ NAYA FIELD: UPI ID store karne ke liye
    upi_id = models.CharField(max_length=50, blank=True, null=True, help_text="e.g., example@upi")

    def __str__(self):
        return f"{self.user.username}'s Profile"

# Automatically create UserProfile when a User is created
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    # ERROR FIX: Agar purane user ka profile nahi hai, toh crash mat ho, naya bana do
    try:
        instance.profile.save()
    except UserProfile.DoesNotExist:
        UserProfile.objects.create(user=instance)


# --- 2. Group Model (Updated with archive feature) ---
class Group(models.Model):
    CATEGORY_CHOICES = [
        ('home', 'Home'),
        ('trip', 'Trip'),
        ('couple', 'Couple'),
        ('personal', 'Personal'),
        ('business', 'Business'),
        ('office', 'Office'),
        ('sports', 'Sports'),
        ('others', 'Others'),
    ]

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='personal')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_groups')
    members = models.ManyToManyField(User, related_name='expense_groups')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_archived = models.BooleanField(default=False)

    def __str__(self):
        return self.name


# --- 3. GroupMember Model (Role-based access) ---
class GroupMember(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('member', 'Member'),
        ('viewer', 'Viewer'),
    ]

    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='group_members')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='group_memberships')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='member')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('group', 'user')

    def __str__(self):
        return f"{self.user.username} - {self.role} in {self.group.name}"


# --- 4. InviteLink Model (Join via link) ---
class InviteLink(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='invite_links')
    token = models.CharField(max_length=32, unique=True, default=uuid.uuid4)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_invites')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    max_uses = models.IntegerField(default=0)  # 0 = unlimited
    used_count = models.IntegerField(default=0)

    def __str__(self):
        return f"Invite link for {self.group.name}"


# --- 5. GroupActivity Model (Activity log) ---
class GroupActivity(models.Model):
    ACTIVITY_CHOICES = [
        ('member_added', 'Member Added'),
        ('member_removed', 'Member Removed'),
        ('expense_added', 'Expense Added'),
        ('expense_edited', 'Expense Edited'),
        ('expense_deleted', 'Expense Deleted'),
        ('settlement_added', 'Settlement Added'),
        ('group_edited', 'Group Edited'),
        ('ownership_transferred', 'Ownership Transferred'),
    ]

    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='activities')
    action_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='group_actions')
    action_type = models.CharField(max_length=25, choices=ACTIVITY_CHOICES)
    description = models.TextField()
    related_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='activity_mentions')
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.action_by.username} - {self.get_action_type_display()} in {self.group.name}"


# --- 6. Expense Model (Updated for Custom Splits) ---
class Expense(models.Model):
    SPLIT_CHOICES = [
        ('equal', 'Equally'),
        ('custom', 'Custom Amount'),
    ]

    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='expenses')
    paid_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='paid_expenses')
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField(auto_now_add=True)
    
    # NAYA FIELD: Split ka type kya hai?
    split_type = models.CharField(max_length=10, choices=SPLIT_CHOICES, default='equal')
    
    # Settlement Fields
    is_settlement = models.BooleanField(default=False)
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_payments', null=True, blank=True)
    
    # Soft delete
    is_deleted = models.BooleanField(default=False)

    def __str__(self):
        if self.is_settlement:
            return f"Settlement: {self.paid_by} paid {self.receiver} - ₹{self.amount}"
        return f"{self.description} - ₹{self.amount} ({self.get_split_type_display()})"


# --- 7. NAYA MODEL: Expense Share (Custom Splits ke liye) ---
class ExpenseShare(models.Model):
    expense = models.ForeignKey(Expense, on_delete=models.CASCADE, related_name='shares')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount_owed = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.user.username} owes ₹{self.amount_owed} for '{self.expense.description}'"


# --- 8. BILL MODEL (Advanced Bill Upload Feature) ---
class Bill(models.Model):
    """
    Advanced bill/receipt upload system for expenses.
    Supports multiple files per expense with proper tracking.
    """
    FILE_TYPE_CHOICES = [
        ('bill', 'Bill/Receipt'),
        ('invoice', 'Invoice'),
        ('receipt', 'Receipt'),
        ('proof', 'Payment Proof'),
        ('other', 'Other'),
    ]

    # Main relationships
    expense = models.ForeignKey(Expense, on_delete=models.CASCADE, related_name='bills')
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='uploaded_bills')
    
    # File information
    file = models.FileField(
        upload_to='bills/%Y/%m/%d/',
        help_text='Upload bill/receipt (PDF, JPG, PNG, etc.)'
    )
    file_name = models.CharField(max_length=255, editable=False)
    file_size = models.BigIntegerField(editable=False, default=0)  # in bytes
    file_type = models.CharField(max_length=20, choices=FILE_TYPE_CHOICES, default='bill')
    
    # Metadata
    description = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text='Optional description (e.g., "Electricity bill for March")'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_primary = models.BooleanField(default=False, help_text='Mark as primary/main bill')
    
    # Access control
    is_public = models.BooleanField(default=True, help_text='Visible to all group members')
    
    # Audit trail
    download_count = models.IntegerField(default=0, help_text='Track how many times downloaded')
    last_downloaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='downloaded_bills'
    )
    last_downloaded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-is_primary', '-uploaded_at']
        indexes = [
            models.Index(fields=['expense', '-uploaded_at']),
            models.Index(fields=['uploaded_by', '-uploaded_at']),
        ]

    def __str__(self):
        return f"{self.file_name} - {self.expense.description}"

    def save(self, *args, **kwargs):
        """Auto-populate file_name and file_size on save"""
        if self.file:
            self.file_name = self.file.name.split('/')[-1]  # Get just the filename
            self.file_size = self.file.size
        super().save(*args, **kwargs)

    @property
    def file_size_mb(self):
        """Convert bytes to MB"""
        return round(self.file_size / (1024 * 1024), 2)

    @property
    def file_extension(self):
        """Get file extension"""
        return self.file_name.split('.')[-1].lower() if self.file_name else 'unknown'

    @property
    def is_image(self):
        """Check if file is an image"""
        image_extensions = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']
        return self.file_extension in image_extensions

    @property
    def is_pdf(self):
        """Check if file is a PDF"""
        return self.file_extension == 'pdf'