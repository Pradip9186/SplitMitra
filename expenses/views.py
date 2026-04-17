from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from .models import Group, Expense, ExpenseShare, UserProfile 
from django.db.models import Sum
from django.conf import settings
from django.utils import timezone 
from datetime import timedelta    
import string
import random

# ✅ NAYE IMPORTS FOR QR CODE & INLINE EMAIL
import qrcode
import io
import base64
from django.core.mail import EmailMultiAlternatives
from email.mime.image import MIMEImage

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

# --- 6. ADD EXPENSE (✅ 2 DIFFERENT EMAILS: PAYER vs NON-PAYER) ---
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
                        messages.error(request, f"Error: Custom amounts do not match the total expense.")
                        return redirect('group_detail', group_id=group.id)

                # 1. Create Main Expense
                expense = Expense.objects.create(
                    group=group, paid_by=paid_by, description=description,
                    amount=amount, split_type=split_type
                )
                
                # Pre-calculate shares list to show in Payer's email
                shares_data = []
                for member in group.members.all():
                    share_amount = amount / group.members.count() if split_type == 'equal' else custom_shares[member]
                    shares_data.append({'member': member, 'amount': share_amount})
                    ExpenseShare.objects.create(expense=expense, user=member, amount_owed=share_amount)

                # General Details for Email
                sender_name = request.user.first_name or request.user.username
                paid_by_name = paid_by.first_name or paid_by.username
                sender_email_host = getattr(settings, 'EMAIL_HOST_USER')
                from_formatted = f"SplitMitra <{sender_email_host}>"
                reply_email = request.user.email if request.user.email else sender_email_host
                upi_id = paid_by.profile.upi_id if hasattr(paid_by, 'profile') else None

                # 2. SEND SEPARATE EMAILS TO EVERYONE
                for share in shares_data:
                    member = share['member']
                    share_amount = share['amount']
                    
                    if not member.email:
                        continue 
                    
                    # ==========================================
                    # TYPE A: EMAIL FOR THE PERSON WHO PAID (Summary)
                    # ==========================================
                    if member == paid_by:
                        subject = f"💰 Expense Summary: '{expense.description}' in '{group.name}'"
                        
                        owes_html = ""
                        for s in shares_data:
                            if s['member'] != paid_by:
                                m_name = s['member'].first_name or s['member'].username
                                owes_html += f"""
                                <div style="display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #e2e8f0;">
                                    <span style="font-size: 15px; color: #64748b;">{m_name} owes you:</span>
                                    <span style="font-size: 15px; font-weight: bold; color: #1e1e2f;">₹{round(s['amount'], 2)}</span>
                                </div>
                                """
                                
                        if member == request.user:
                            intro_text = f"You just added a new expense to <strong>'{group.name}'</strong>."
                        else:
                            intro_text = f"<strong>{sender_name}</strong> added a new expense to <strong>'{group.name}'</strong> and marked that YOU paid."

                        html_message = f"""
                        <html>
                        <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color: #1e1e2f; background-color: #f4f7f9; padding: 20px;">
                            <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 16px; overflow: hidden; box-shadow: 0 10px 25px rgba(0,0,0,0.05);">
                                <div style="background: linear-gradient(135deg, #10b981, #059669); color: white; padding: 25px; text-align: center;">
                                    <h2 style="margin: 0; font-size: 24px; letter-spacing: 1px;">🤝 SplitMitra</h2>
                                </div>
                                <div style="padding: 30px;">
                                    <p style="font-size: 16px; margin-top: 0;">Hello <strong>{paid_by_name}</strong>,</p>
                                    <p style="font-size: 16px; color: #64748b;">{intro_text}</p>
                                    
                                    <div style="background-color: #f0fdf4; padding: 20px; border-radius: 12px; border-left: 4px solid #10b981; margin: 25px 0;">
                                        <p style="margin: 5px 0; font-size: 15px;"><strong>🧾 Description:</strong> {expense.description}</p>
                                        <p style="margin: 5px 0; font-size: 15px;"><strong>💵 Total You Paid:</strong> ₹{expense.amount}</p>
                                    </div>
                                    
                                    <h3 style="font-size: 18px; margin-bottom: 15px; color: #1e1e2f;">Here's who owes you:</h3>
                                    <div style="background: #f8fafc; padding: 5px 20px; border-radius: 12px; border: 1px solid #e2e8f0;">
                                        {owes_html}
                                    </div>
                                    
                                    <p style="text-align: center; margin-top: 40px; margin-bottom: 20px;">
                                        <a href="http://127.0.0.1:8000/group/{group.id}/" style="background-color: #1e1e2f; color: white; padding: 14px 30px; text-decoration: none; border-radius: 50px; font-weight: bold; font-size: 16px; display: inline-block;">View Group Balances</a>
                                    </p>
                                </div>
                            </div>
                        </body>
                        </html>
                        """
                        try:
                            email_msg = EmailMultiAlternatives(subject, "Expense Summary on SplitMitra.", from_formatted, [member.email], reply_to=[reply_email])
                            email_msg.attach_alternative(html_message, "text/html")
                            email_msg.send(fail_silently=True)
                        except Exception as e:
                            print(f"Payer Email failed: {e}")

                    # ==========================================
                    # TYPE B: EMAIL FOR PEOPLE WHO NEED TO PAY (Debtors with QR)
                    # ==========================================
                    else:
                        subject = f"💰 {sender_name} added a new expense in '{group.name}'"
                        qr_html_section = ""
                        img_data = None 
                        
                        if upi_id:
                            upi_url = f"upi://pay?pa={upi_id}&pn={paid_by_name}&am={round(share_amount, 2)}&cu=INR"
                            qr = qrcode.QRCode(version=1, box_size=6, border=2)
                            qr.add_data(upi_url)
                            qr.make(fit=True)
                            img = qr.make_image(fill_color="#1e1e2f", back_color="white")
                            buffer = io.BytesIO()
                            img.save(buffer, format="PNG")
                            img_data = buffer.getvalue()
                            
                            qr_html_section = f"""
                            <div style="text-align: center; margin-top: 25px; padding: 20px; background-color: white; border-radius: 16px; border: 2px dashed #e2e8f0;">
                                <p style="font-size: 15px; color: #1e1e2f; font-weight: 800; margin-top: 0;">Scan to Pay {paid_by_name}</p>
                                <img src="cid:qr_code_image_{member.id}" alt="UPI QR Code" style="border-radius: 8px; margin: 10px 0; width: 180px; height: 180px;">
                                <p style="font-size: 13px; color: #64748b; margin-bottom: 0;">UPI ID: {upi_id}</p>
                            </div>
                            """
                        else:
                            qr_html_section = f"""
                            <div style="text-align: center; margin-top: 25px; padding: 15px; background-color: #fffbeb; border-radius: 12px; border: 1px solid #fef08a;">
                                <p style="font-size: 14px; color: #92400e; margin: 0;"><strong>Note:</strong> {paid_by_name} hasn't added their UPI ID yet. Please ask them for details.</p>
                            </div>
                            """
                        
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
                                    
                                    {qr_html_section}
                                    
                                    <p style="text-align: center; margin-top: 40px; margin-bottom: 20px;">
                                        <a href="http://127.0.0.1:8000/group/{group.id}/" style="background-color: #1e1e2f; color: white; padding: 14px 30px; text-decoration: none; border-radius: 50px; font-weight: bold; font-size: 16px; display: inline-block;">View on SplitMitra</a>
                                    </p>
                                </div>
                            </div>
                        </body>
                        </html>
                        """
                        
                        try:
                            email_msg = EmailMultiAlternatives(subject, "You owe money on SplitMitra.", from_formatted, [member.email], reply_to=[reply_email])
                            email_msg.attach_alternative(html_message, "text/html")
                            email_msg.mixed_subtype = 'related'
                            
                            if img_data:
                                inline_image = MIMEImage(img_data)
                                inline_image.add_header('Content-ID', f'<qr_code_image_{member.id}>')
                                inline_image.add_header('Content-Disposition', 'inline', filename='qr_code.png')
                                email_msg.attach(inline_image)
                                
                            email_msg.send(fail_silently=True) 
                            
                        except Exception as e:
                            print(f"Debtor Email failed: {e}")
                        
                messages.success(request, f"Expense added! Summary and QR Emails sent properly.")
            return redirect('group_detail', group_id=group.id)
    return redirect('dashboard')

# --- 7. ADD MEMBER ---
def add_member(request, group_id):
    if request.method == 'POST' and request.user.is_authenticated:
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        email = request.POST.get('email')
        upi_id = request.POST.get('upi_id') 
        
        group = get_object_or_404(Group, id=group_id)
        
        if request.user not in group.members.all():
            return redirect('dashboard')
            
        try:
            friend = User.objects.get(email=email)
            if friend not in group.members.all():
                group.members.add(friend)
                if hasattr(friend, 'profile'):
                    if phone and not friend.profile.phone_number:
                        friend.profile.phone_number = phone
                    if upi_id: 
                        friend.profile.upi_id = upi_id
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
                new_user.profile.upi_id = upi_id 
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

# --- 10. ANALYTICS VIEW ---
def analytics_view(request):
    if not request.user.is_authenticated:
        return redirect('login')

    time_filter = request.GET.get('filter', 'month')
    now = timezone.now().date()
    expenses = Expense.objects.filter(paid_by=request.user, is_settlement=False)

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

# --- 13. SETTINGS VIEW ---
def settings_view(request):
    if not request.user.is_authenticated:
        return redirect('login')
        
    if request.method == 'POST':
        phone = request.POST.get('phone')
        upi_id = request.POST.get('upi_id')
        
        if hasattr(request.user, 'profile'):
            request.user.profile.phone_number = phone
            request.user.profile.upi_id = upi_id
            request.user.profile.save()
            messages.success(request, "Settings updated successfully!")
            return redirect('settings')
            
    return render(request, 'settings.html')

# --- 14. FRIENDS VIEW ---
def friends_view(request):
    if not request.user.is_authenticated:
        return redirect('login')

    friends_data = {}
    total_you_owe = 0.0
    total_you_are_owed = 0.0

    user_groups = Group.objects.filter(members=request.user)

    for group in user_groups:
        for member in group.members.all():
            if member != request.user:
                if member not in friends_data:
                    friends_data[member] = 0.0

    for group in user_groups:
        members = group.members.all()
        expenses = Expense.objects.filter(group=group)
        net_balances = {m: 0.0 for m in members}

        for exp in expenses:
            amount = float(exp.amount)
            if exp.is_settlement:
                net_balances[exp.paid_by] += amount
                if exp.receiver: net_balances[exp.receiver] -= amount
            else:
                net_balances[exp.paid_by] += amount
                for share in exp.shares.all():
                    net_balances[share.user] -= float(share.amount_owed)

        debtors = [{'user': m, 'amount': abs(b)} for m, b in net_balances.items() if b < -0.01]
        creditors = [{'user': m, 'amount': b} for m, b in net_balances.items() if b > 0.01]

        d_idx, c_idx = 0, 0
        while d_idx < len(debtors) and c_idx < len(creditors):
            d = debtors[d_idx]
            c = creditors[c_idx]
            settle_amount = min(d['amount'], c['amount'])

            if d['user'] == request.user and c['user'] != request.user:
                friends_data[c['user']] -= settle_amount
            elif c['user'] == request.user and d['user'] != request.user:
                friends_data[d['user']] += settle_amount

            d['amount'] -= settle_amount
            c['amount'] -= settle_amount
            if d['amount'] < 0.01: d_idx += 1
            if c['amount'] < 0.01: c_idx += 1

    friends_list = []
    for friend, balance in friends_data.items():
        if balance > 0.01:
            total_you_are_owed += balance
        elif balance < -0.01:
            total_you_owe += abs(balance)
        friends_list.append({'friend': friend, 'balance': balance})

    friends_list.sort(key=lambda x: x['friend'].first_name or x['friend'].username)

    return render(request, 'friends.html', {
        'friends_list': friends_list,
        'total_you_owe': total_you_owe,
        'total_you_are_owed': total_you_are_owed,
        'total_friends': len(friends_list)
    })