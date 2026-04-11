from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from .models import Group, Expense, ExpenseShare, UserProfile 
from django.db.models import Sum
from django.core.mail import EmailMessage
from django.conf import settings
from django.utils import timezone # <-- NAYA IMPORT: Time filter ke liye
from datetime import timedelta    # <-- NAYA IMPORT: Time filter ke liye
import string
import random

# --- 1. LOGIN VIEW ---
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        user = authenticate(request, username=email, password=password)
        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            return render(request, 'login.html', {'error': 'Invalid Email or Password'})
    return render(request, 'login.html')

# --- 2. REGISTRATION VIEW ---
def register_view(request):
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        email = request.POST.get('email')
        pass1 = request.POST.get('pass1')
        pass2 = request.POST.get('pass2')

        if pass1 != pass2:
            return render(request, 'register.html', {'error': 'Passwords do not match!'})
        if User.objects.filter(username=email).exists():
            return render(request, 'register.html', {'error': 'Email already registered!'})

        user = User.objects.create_user(username=email, email=email, password=pass1)
        user.first_name = first_name
        user.save()
        login(request, user)
        return redirect('dashboard')
    return render(request, 'register.html')

# --- 3. DYNAMIC DASHBOARD ---
def dashboard(request):
    if not request.user.is_authenticated:
        return redirect('login')
    
    user_groups = Group.objects.filter(members=request.user).order_by('-created_at')
    
    will_get = 0.0
    will_pay = 0.0
    
    for group in user_groups:
        my_paid = float(Expense.objects.filter(group=group, paid_by=request.user, is_settlement=False).aggregate(Sum('amount'))['amount__sum'] or 0)
        my_share = float(ExpenseShare.objects.filter(expense__group=group, user=request.user).aggregate(Sum('amount_owed'))['amount_owed__sum'] or 0)
        
        settlements_paid = float(Expense.objects.filter(group=group, paid_by=request.user, is_settlement=True).aggregate(Sum('amount'))['amount__sum'] or 0)
        settlements_received = float(Expense.objects.filter(group=group, receiver=request.user, is_settlement=True).aggregate(Sum('amount'))['amount__sum'] or 0)
        
        my_balance = (my_paid + settlements_paid) - (my_share + settlements_received)
        
        if my_balance > 0.01:
            will_get += my_balance
        elif my_balance < -0.01:
            will_pay += abs(my_balance) 

    total_balance = will_get - will_pay
    recent_activities = Expense.objects.filter(group__members=request.user).order_by('-date')[:5]

    context = {
        'groups': user_groups,
        'total_balance': total_balance,
        'will_get': will_get,
        'will_pay': will_pay,
        'recent_activities': recent_activities,
    }
    return render(request, 'index.html', context)

# --- 4. GROUP DETAIL ---
def group_detail(request, group_id):
    if not request.user.is_authenticated:
        return redirect('login')
    
    group = get_object_or_404(Group, id=group_id)
    if request.user not in group.members.all():
        return redirect('dashboard')

    expenses = Expense.objects.filter(group=group, is_settlement=False).order_by('-date')
    total_group_expense = float(expenses.aggregate(Sum('amount'))['amount__sum'] or 0)
    
    my_paid = float(expenses.filter(paid_by=request.user).aggregate(Sum('amount'))['amount__sum'] or 0)
    my_share = float(ExpenseShare.objects.filter(expense__in=expenses, user=request.user).aggregate(Sum('amount_owed'))['amount_owed__sum'] or 0)
    
    settlements = Expense.objects.filter(group=group, is_settlement=True)
    settlements_paid = float(settlements.filter(paid_by=request.user).aggregate(Sum('amount'))['amount__sum'] or 0)
    settlements_received = float(settlements.filter(receiver=request.user).aggregate(Sum('amount'))['amount__sum'] or 0)
    
    my_balance = (my_paid + settlements_paid) - (my_share + settlements_received)
    
    context = {
        'group': group,
        'expenses': expenses,
        'total_group_expense': total_group_expense,
        'my_balance': my_balance,
    }
    return render(request, 'group_detail.html', context)

# --- 5. CREATE GROUP ---
def create_group(request):
    if request.method == 'POST' and request.user.is_authenticated:
        name = request.POST.get('group_name')
        category = request.POST.get('category', 'others') 
        
        if name:
            new_group = Group.objects.create(
                name=name, 
                category=category, 
                created_by=request.user
            )
            new_group.members.add(request.user)
            return redirect('group_detail', group_id=new_group.id)
    return redirect('dashboard')

# --- 6. ADD EXPENSE (HTML EMAIL SYSTEM) ---
def add_expense(request):
    if request.method == 'POST' and request.user.is_authenticated:
        description = request.POST.get('description')
        amount_str = request.POST.get('amount')
        group_id = request.POST.get('group_id')
        paid_by_id = request.POST.get('paid_by_id')
        split_type = request.POST.get('split_type', 'equal')
        
        if description and amount_str and group_id and paid_by_id:
            amount = float(amount_str)
            group = get_object_or_404(Group, id=group_id)
            paid_by = get_object_or_404(User, id=paid_by_id)
            
            if request.user in group.members.all() and paid_by in group.members.all():
                
                custom_shares = {}
                if split_type == 'custom':
                    total_custom = 0.0
                    for member in group.members.all():
                        val = request.POST.get(f'custom_amount_{member.id}', 0)
                        val = float(val) if val else 0.0
                        custom_shares[member] = val
                        total_custom += val
                    
                    if abs(total_custom - amount) > 0.01:
                        messages.error(request, f"Error: Custom amounts (₹{total_custom}) do not match the total expense (₹{amount}).")
                        return redirect('group_detail', group_id=group.id)

                # 1. Create Main Expense
                expense = Expense.objects.create(
                    group=group,
                    paid_by=paid_by,
                    description=description,
                    amount=amount,
                    split_type=split_type
                )
                
                # 2. Create Shares AND SEND EMAILS
                for member in group.members.all():
                    if split_type == 'equal':
                        share_amount = amount / group.members.count()
                    else:
                        share_amount = custom_shares[member]
                        
                    ExpenseShare.objects.create(expense=expense, user=member, amount_owed=share_amount)
                    
                    # HTML EMAIL LOGIC
                    if member.email and member != request.user: 
                        sender_name = request.user.first_name or request.user.username
                        paid_by_name = paid_by.first_name or paid_by.username
                        
                        subject = f"💰 {sender_name} added a new expense in '{group.name}'"
                        
                        html_message = f"""
                        <html>
                        <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color: #1e1e2f; background-color: #f4f7f9; padding: 20px;">
                            <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 16px; overflow: hidden; box-shadow: 0 10px 25px rgba(0,0,0,0.05);">
                                <div style="background: linear-gradient(135deg, #6366f1, #4f46e5); color: white; padding: 25px; text-align: center;">
                                    <h2 style="margin: 0; font-size: 24px; letter-spacing: 1px;">🤝 SplitMitra</h2>
                                </div>
                                <div style="padding: 30px;">
                                    <p style="font-size: 16px; margin-top: 0;">Hello <strong>{member.first_name or member.username}</strong>,</p>
                                    <p style="font-size: 16px; color: #64748b;"><strong>{sender_name}</strong> has just added a new expense to your group <strong>'{group.name}'</strong>.</p>
                                    <div style="background-color: #f8fafc; padding: 20px; border-radius: 12px; border-left: 4px solid #6366f1; margin: 25px 0;">
                                        <p style="margin: 5px 0; font-size: 15px;"><strong>🧾 Description:</strong> {expense.description}</p>
                                        <p style="margin: 5px 0; font-size: 15px;"><strong>💵 Total Amount:</strong> ₹{expense.amount}</p>
                                        <p style="margin: 5px 0; font-size: 15px;"><strong>👤 Paid By:</strong> {paid_by_name}</p>
                                    </div>
                                    <div style="text-align: center; margin: 30px 0;">
                                        <p style="margin: 0; font-size: 14px; color: #64748b; text-transform: uppercase; font-weight: bold;">Your Share</p>
                                        <h1 style="color: #e63946; margin: 5px 0; font-size: 36px;">₹{round(share_amount, 2)}</h1>
                                    </div>
                                    <p style="text-align: center; margin-top: 40px; margin-bottom: 20px;">
                                        <a href="http://127.0.0.1:8000/group/{group.id}/" style="background-color: #1e1e2f; color: white; padding: 14px 30px; text-decoration: none; border-radius: 50px; font-weight: bold; font-size: 16px; display: inline-block;">View on SplitMitra</a>
                                    </p>
                                </div>
                                <div style="background-color: #f8fafc; padding: 20px; text-align: center; font-size: 12px; color: #94a3b8; border-top: 1px solid #e2e8f0;">
                                    <p style="margin: 0;">This email was sent via SplitMitra by {sender_name}.</p>
                                    <p style="margin: 5px 0 0 0;">If you reply to this email, it will go directly to {sender_name}.</p>
                                </div>
                            </div>
                        </body>
                        </html>
                        """
                        try:
                            reply_email = request.user.email if request.user.email else getattr(settings, 'EMAIL_HOST_USER')
                            email_msg = EmailMessage(
                                subject=subject, 
                                body=html_message, 
                                from_email=getattr(settings, 'EMAIL_HOST_USER', 'noreply@splitmitra.com'), 
                                to=[member.email],
                                reply_to=[reply_email]
                            )
                            email_msg.content_subtype = "html"
                            email_msg.send(fail_silently=True)
                        except Exception as e:
                            print(f"Email sending failed: {e}")
                        
                messages.success(request, f"Expense '{description}' added successfully & members have been notified!")
            return redirect('group_detail', group_id=group.id)
    return redirect('dashboard')

# --- 7. ADD MEMBER ---
def add_member(request, group_id):
    if request.method == 'POST' and request.user.is_authenticated:
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        email = request.POST.get('email')
        
        group = get_object_or_404(Group, id=group_id)
        
        if request.user not in group.members.all():
            return redirect('dashboard')
            
        try:
            friend = User.objects.get(email=email)
            if friend not in group.members.all():
                group.members.add(friend)
                if hasattr(friend, 'profile') and not friend.profile.phone_number:
                    friend.profile.phone_number = phone
                    friend.profile.save()
                messages.success(request, f"{friend.first_name or friend.username} has been added to the group!")
            else:
                messages.warning(request, f"{friend.first_name or friend.username} is already in the group.")
                
        except User.DoesNotExist:
            random_password = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
            first_name = name.split()[0] if name else email.split('@')[0]
            
            new_user = User.objects.create_user(
                username=email, 
                email=email, 
                password=random_password,
                first_name=first_name
            )
            
            if hasattr(new_user, 'profile'):
                new_user.profile.phone_number = phone
                new_user.profile.save()
            
            group.members.add(new_user)
            messages.success(request, f"{name} has been added! An invite email will be sent shortly.")
            
        return redirect('group_detail', group_id=group.id)
    return redirect('dashboard')

# --- 8. LOGOUT ---
def logout_view(request):
    logout(request)
    return redirect('login')

# --- 9. MY GROUPS PAGE ---
def my_groups(request):
    if not request.user.is_authenticated:
        return redirect('login')
    user_groups = Group.objects.filter(members=request.user).order_by('-created_at')
    return render(request, 'my_groups.html', {'groups': user_groups})

# --- 10. ANALYTICS VIEW (UPDATED FOR TIME FILTERS) ---
def analytics_view(request):
    if not request.user.is_authenticated:
        return redirect('login')

    # User ne kaunsa filter select kiya hai wo get karo (Default: 'month')
    time_filter = request.GET.get('filter', 'month')
    now = timezone.now().date()

    # Base Query: Sirf wo kharche jo user ne kiye hain (Settlements ko hatakar)
    expenses = Expense.objects.filter(paid_by=request.user, is_settlement=False)

    # Filter logic apply karo
    if time_filter == 'week':
        expenses = expenses.filter(date__gte=now - timedelta(days=7))
        filter_label = 'This Week'
    elif time_filter == 'month':
        expenses = expenses.filter(date__gte=now - timedelta(days=30))
        filter_label = 'This Month'
    elif time_filter == 'year':
        expenses = expenses.filter(date__gte=now - timedelta(days=365))
        filter_label = 'This Year'
    else:
        filter_label = 'All Time'

    # 8 Categories ke hisaab se data nikaalo
    categories = ['home', 'trip', 'couple', 'personal', 'business', 'office', 'sports', 'others']
    category_labels = ['Home', 'Trip', 'Couple', 'Personal', 'Business', 'Office', 'Sports', 'Others']
    category_data = []

    for cat in categories:
        amount = expenses.filter(group__category=cat).aggregate(Sum('amount'))['amount__sum'] or 0
        category_data.append(float(amount))

    total_spent = sum(category_data)

    context = {
        'category_labels': category_labels,
        'category_data': category_data,
        'total_spent': total_spent,
        'current_filter': time_filter,
        'filter_label': filter_label
    }
    return render(request, 'analytics.html', context)

# --- 11. GROUP BALANCES LOGIC ---
def group_balances(request, group_id):
    if not request.user.is_authenticated:
        return redirect('login')
    
    group = get_object_or_404(Group, id=group_id)
    members = group.members.all()
    expenses = Expense.objects.filter(group=group)
    
    net_balances = {member: 0.0 for member in members}
    
    for exp in expenses:
        amount = float(exp.amount)
        if exp.is_settlement:
            net_balances[exp.paid_by] += amount
            if exp.receiver:
                net_balances[exp.receiver] -= amount
        else:
            net_balances[exp.paid_by] += amount
            for share in exp.shares.all():
                net_balances[share.user] -= float(share.amount_owed)

    debtors = []
    creditors = []
    for member, bal in net_balances.items():
        if bal < -0.01: debtors.append({'user': member, 'amount': abs(bal)})
        elif bal > 0.01: creditors.append({'user': member, 'amount': bal})

    final_debts = []
    d_idx, c_idx = 0, 0
    temp_debtors = [d.copy() for d in debtors]
    temp_creditors = [c.copy() for c in creditors] 

    while d_idx < len(temp_debtors) and c_idx < len(temp_creditors):
        d = temp_debtors[d_idx]
        c = temp_creditors[c_idx]
        settle_amount = min(d['amount'], c['amount'])
        final_debts.append({'from_user': d['user'], 'to_user': c['user'], 'amount': settle_amount})
        d['amount'] -= settle_amount
        c['amount'] -= settle_amount
        if d['amount'] < 0.01: d_idx += 1
        if c['amount'] < 0.01: c_idx += 1

    return render(request, 'group_balances.html', {
        'group': group, 
        'final_debts': final_debts, 
        'my_net_balance': net_balances.get(request.user, 0)
    })

# --- 12. SETTLE UP ACTION ---
def settle_up(request, group_id, receiver_id):
    if request.method == "POST" and request.user.is_authenticated:
        group = get_object_or_404(Group, id=group_id)
        receiver = get_object_or_404(User, id=receiver_id)
        amount = request.POST.get('amount')
        Expense.objects.create(
            group=group, paid_by=request.user, receiver=receiver,
            description=f"Settle: Paid {receiver.username}",
            amount=amount, is_settlement=True
        )
        messages.success(request, f"Settled ₹{amount} with {receiver.username}")
    return redirect('group_balances', group_id=group_id)