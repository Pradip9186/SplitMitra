from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

# --- 1. User Profile (For Phone Number) ---
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone_number = models.CharField(max_length=15, blank=True, null=True)

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


# --- 2. Group Model ---
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
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='personal')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_groups')
    members = models.ManyToManyField(User, related_name='expense_groups')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


# --- 3. Expense Model (Updated for Custom Splits) ---
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

    def __str__(self):
        if self.is_settlement:
            return f"Settlement: {self.paid_by} paid {self.receiver} - ₹{self.amount}"
        return f"{self.description} - ₹{self.amount} ({self.get_split_type_display()})"


# --- 4. NAYA MODEL: Expense Share (Custom Splits ke liye) ---
class ExpenseShare(models.Model):
    expense = models.ForeignKey(Expense, on_delete=models.CASCADE, related_name='shares')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount_owed = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.user.username} owes ₹{self.amount_owed} for '{self.expense.description}'"