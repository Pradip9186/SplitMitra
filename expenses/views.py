from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from .models import Group, Expense, ExpenseShare, UserProfile, GroupMember, InviteLink, GroupActivity, Bill
from django.db.models import Sum, Q
from django.conf import settings
from django.utils import timezone 
from datetime import timedelta, datetime    
import string
import random

# ✅ NAYE IMPORTS FOR QR CODE, PDF EXPORT, & INLINE EMAIL
import qrcode
import io
import base64
from django.core.mail import EmailMultiAlternatives, send_mail
from email.mime.image import MIMEImage
from django.http import JsonResponse, HttpResponse
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
import json

# --- 1. LOGIN VIEW ---
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')
        user = None

        if email:
            found_user = User.objects.filter(email__iexact=email).first()
            if found_user:
                user = authenticate(request, username=found_user.username, password=password)
            else:
                user = authenticate(request, username=email, password=password)

        if user is not None:
            login(request, user)
            return redirect('dashboard')
        return render(request, 'login.html', {'error': 'Invalid Email or Password'})
    return render(request, 'login.html')

# --- 2. REGISTRATION VIEW ---
def register_view(request):
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        email = request.POST.get('email', '').strip().lower()
        pass1 = request.POST.get('pass1', '')
        pass2 = request.POST.get('pass2', '')

        if pass1 != pass2:
            return render(request, 'register.html', {'error': 'Passwords do not match!'})
        if User.objects.filter(Q(username__iexact=email) | Q(email__iexact=email)).exists():
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

# --- 3b. PROFILE VIEW ---
def profile_view(request):
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

    return render(request, 'profile.html', {
        'user_groups': user_groups,
        'total_groups': user_groups.count(),
        'total_balance': total_balance,
        'will_get': will_get,
        'will_pay': will_pay,
    })

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
    user_groups = Group.objects.filter(members=request.user, is_archived=False).order_by('-created_at')
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
    total_expenses_count = expenses.count()
    active_groups = Group.objects.filter(members=request.user, is_archived=False).count()
    days_period = 1
    if time_filter == 'week':
        days_period = 7
    elif time_filter == 'month':
        days_period = 30
    elif time_filter == 'year':
        days_period = 365
    else:
        earliest = expenses.order_by('date').first()
        days_period = max((timezone.now().date() - earliest.date).days + 1, 1) if earliest else 1

    average_per_day = round(total_spent / days_period, 2) if days_period else 0.0
    top_category_label = 'No spending yet'
    if category_data and max(category_data) > 0:
        top_category_index = category_data.index(max(category_data))
        top_category_label = category_labels[top_category_index]

    context = {
        'category_labels': category_labels,
        'category_data': category_data,
        'total_spent': total_spent,
        'current_filter': time_filter,
        'filter_label': filter_label,
        'average_per_day': average_per_day,
        'active_groups': active_groups,
        'top_category_label': top_category_label,
        'total_expenses_count': total_expenses_count,
    }
    return render(request, 'analytics.html', context)

# --- 11. ANALYTICS DOWNLOAD PDF ---
def analytics_download_pdf(request):
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

    active_groups = Group.objects.filter(members=request.user, is_archived=False).count()
    top_category_label = 'No spending yet'
    if category_data and max(category_data) > 0:
        top_category_index = category_data.index(max(category_data))
        top_category_label = category_labels[top_category_index]

    group_totals = []
    for group in Group.objects.filter(members=request.user, is_archived=False):
        group_amount = expenses.filter(group=group).aggregate(Sum('amount'))['amount__sum'] or 0
        if group_amount > 0:
            group_totals.append((group.name, float(group_amount)))

    total_spent = sum(category_data)
    total_expenses_count = expenses.count()
    recent_expenses = expenses.select_related('group').order_by('-date')[:50]

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'titleStyle', parent=styles['Heading1'], fontSize=20, leading=24, spaceAfter=14
    )
    header_style = ParagraphStyle(
        'headerStyle', parent=styles['Heading2'], fontSize=14, leading=18, spaceAfter=10
    )
    normal_style = ParagraphStyle('normalStyle', parent=styles['Normal'], fontSize=10, leading=14)

    elements = []
    elements.append(Paragraph('SplitMitra Financial Report', title_style))
    elements.append(Paragraph(f'Report generated for: {request.user.first_name or request.user.username}', normal_style))
    elements.append(Paragraph(f'Period: {filter_label}', normal_style))
    elements.append(Paragraph(f'Date: {timezone.now().strftime("%Y-%m-%d %H:%M")}', normal_style))
    elements.append(Spacer(1, 16))

    summary_data = [
        ['Metric', 'Value'],
        ['Total Spent', f'₹ {total_spent:.2f}'],
        ['Expenses Count', str(total_expenses_count)],
        ['Active Groups', str(Group.objects.filter(members=request.user, is_archived=False).count())],
        ['Top Category', top_category_label if total_spent > 0 else 'N/A'],
    ]
    summary_table = Table(summary_data, colWidths=[3*inch, 3*inch], hAlign='LEFT')
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4f46e5')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 20))

    elements.append(Paragraph('Category Breakdown', header_style))
    category_table_data = [['Category', 'Amount (₹)']]
    for label, amount in zip(category_labels, category_data):
        category_table_data.append([label, f'{amount:.2f}'])
    category_table = Table(category_table_data, colWidths=[3*inch, 3*inch], hAlign='LEFT')
    category_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8fafc')),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
    ]))
    elements.append(category_table)
    elements.append(Spacer(1, 20))

    if group_totals:
        elements.append(Paragraph('Spending by Group', header_style))
        group_table_data = [['Group', 'Amount (₹)']]
        for name, amount in group_totals:
            group_table_data.append([name, f'{amount:.2f}'])
        group_table = Table(group_table_data, colWidths=[3*inch, 3*inch], hAlign='LEFT')
        group_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8fafc')),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
        ]))
        elements.append(group_table)
        elements.append(Spacer(1, 20))

    if recent_expenses.exists():
        elements.append(Paragraph('Recent Expense Details', header_style))
        expenses_table_data = [['Date', 'Group', 'Category', 'Description', 'Amount (₹)']]
        for expense in recent_expenses:
            expenses_table_data.append([
                expense.date.strftime('%Y-%m-%d'),
                expense.group.name,
                expense.group.get_category_display(),
                expense.description,
                f'{float(expense.amount):.2f}'
            ])
        expenses_table = Table(expenses_table_data, colWidths=[1*inch, 1.5*inch, 1*inch, 2*inch, 1*inch], repeatRows=1)
        expenses_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4f46e5')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.grey),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('ALIGN', (4, 1), (-1, -1), 'RIGHT'),
        ]))
        elements.append(expenses_table)

    doc.build(elements)
    buffer.seek(0)

    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="SplitMitra_Report_{time_filter}_{timezone.now().strftime("%Y%m%d")}.pdf"'
    return response

# --- 11. GROUP BALANCES LOGIC ---
def group_balances(request, group_id):
    if not request.user.is_authenticated:
        return redirect('login')
    
    group = get_object_or_404(Group, id=group_id, members=request.user)
    members = group.members.all()
    expenses = Expense.objects.filter(group=group)
    total_group_expense = float(expenses.filter(is_settlement=False).aggregate(Sum('amount'))['amount__sum'] or 0)
    
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

    members_stats = []
    for member in members:
        paid = float(expenses.filter(is_settlement=False, paid_by=member).aggregate(Sum('amount'))['amount__sum'] or 0)
        owed = float(ExpenseShare.objects.filter(expense__group=group, user=member).aggregate(Sum('amount_owed'))['amount_owed__sum'] or 0)
        settlements_paid = float(expenses.filter(is_settlement=True, paid_by=member).aggregate(Sum('amount'))['amount__sum'] or 0)
        settlements_received = float(expenses.filter(is_settlement=True, receiver=member).aggregate(Sum('amount'))['amount__sum'] or 0)
        net_balance = (paid + settlements_paid) - (owed + settlements_received)
        members_stats.append({
            'id': member.id,
            'name': member.first_name or member.username,
            'email': member.email,
            'is_admin': member == group.created_by,
            'paid': paid,
            'owed': owed,
            'net_balance': net_balance,
        })

    max_value = max((abs(item['net_balance']) for item in members_stats), default=1)
    for item in members_stats:
        item['bar_percent'] = int((abs(item['net_balance']) / max_value) * 100) if max_value else 0

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
        'my_net_balance': net_balances.get(request.user, 0),
        'total_group_expense': total_group_expense,
        'members': members,
        'member_chart_data': members_stats,
    })

# --- 12. GROUP SETTINGS VIEW ---
def group_settings(request, group_id):
    if not request.user.is_authenticated:
        return redirect('login')

    group = get_object_or_404(Group, id=group_id)
    if request.user not in group.members.all():
        return redirect('dashboard')

    members = group.members.all()
    is_admin = group.created_by == request.user

    return render(request, 'group_settings.html', {
        'group': group,
        'members': members,
        'is_admin': is_admin,
    })

# --- 13. SETTLE UP ACTION ---
def settle_up(request, group_id, receiver_id):
    if request.method == "POST" and request.user.is_authenticated:
        group = get_object_or_404(Group, id=group_id, members=request.user)
        receiver = get_object_or_404(User, id=receiver_id)
        if receiver not in group.members.all():
            messages.error(request, "Invalid settlement user for this group.")
            return redirect('group_balances', group_id=group_id)

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

# --- 14. FRIENDS VIEW (✅ UPDATED FOR PREMIUM UI) ---
def friends_view(request):
    if not request.user.is_authenticated:
        return redirect('login')

    friends_data = {}
    total_you_owe = 0.0
    total_you_are_owed = 0.0

    # Saare groups jisme user hai
    user_groups = Group.objects.filter(members=request.user)

    # Initialize all friends
    for group in user_groups:
        for member in group.members.all():
            if member != request.user:
                if member not in friends_data:
                    friends_data[member] = 0.0

    # Calculate net balance across ALL groups
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

    # Frontend ke liye list prepare karna
    friends_list = []
    for friend, balance in friends_data.items():
        upi = friend.profile.upi_id if hasattr(friend, 'profile') else ""
        
        if balance > 0.01:
            total_you_are_owed += balance
            status = 'owes_you'
            display_amt = balance
        elif balance < -0.01:
            total_you_owe += abs(balance)
            status = 'you_owe'
            display_amt = abs(balance)
        else:
            status = 'settled'
            display_amt = 0.0

        friends_list.append({
            'obj': friend,
            'name': friend.first_name or friend.username,
            'email': friend.email,
            'status': status,
            'amount': display_amt,
            'upi_id': upi
        })

    # Sort alphabetical
    friends_list.sort(key=lambda x: x['name'].lower())

    return render(request, 'friends.html', {
        'friends_list': friends_list,
        'total_you_owe': total_you_owe,
        'total_you_are_owed': total_you_are_owed,
        'total_friends': len(friends_list)
    })

# --- 15. SEND REMINDER EMAIL (✅ ADVANCED FEATURE) ---
def send_reminder(request, friend_id):
    if not request.user.is_authenticated:
        return redirect('login')
        
    if request.method == "POST":
        friend = get_object_or_404(User, id=friend_id)
        amount = request.POST.get('amount', '0')
        
        if friend.email:
            subject = f"🔔 Reminder: You owe ₹{amount} to {request.user.first_name or request.user.username}"
            
            # Aapki UPI ID (agar hai toh)
            upi_id = request.user.profile.upi_id if hasattr(request.user, 'profile') else "Not Added"
            
            message = f"""
            Hello {friend.first_name or friend.username},
            
            This is a gentle reminder from {request.user.first_name or request.user.username} regarding your pending balance on SplitMitra.
            
            Total Amount Due: ₹{amount}
            
            You can pay them directly using their UPI ID: {upi_id}
            
            Please settle up soon!
            
            Regards,
            Team SplitMitra
            """
            
            try:
                send_mail(
                    subject,
                    message,
                    getattr(settings, 'EMAIL_HOST_USER', 'noreply@splitmitra.com'),
                    [friend.email],
                    fail_silently=False,
                )
                messages.success(request, f"Reminder successfully sent to {friend.first_name or friend.username}!")
            except Exception as e:
                messages.error(request, "Failed to send reminder email. Please try again.")
        else:
            messages.warning(request, f"{friend.first_name or friend.username} does not have an email address saved.")
            
    return redirect('friends')

# --- 16. SETTLE ALL WITH FRIEND (✅ ADVANCED FEATURE) ---
def settle_all_with_friend(request, friend_id):
    if not request.user.is_authenticated:
        return redirect('login')
        
    if request.method == "POST":
        friend = get_object_or_404(User, id=friend_id)
        amount_str = request.POST.get('amount')
        
        if amount_str:
            amount = float(amount_str)
            # Find groups where you owe this friend money
            shared_groups = Group.objects.filter(members=request.user).filter(members=friend)
            
            if shared_groups.exists():
                target_group = shared_groups.first()
                
                # Record the settlement
                Expense.objects.create(
                    group=target_group, 
                    paid_by=request.user, 
                    receiver=friend,
                    description=f"Settled all balances with {friend.username}",
                    amount=amount, 
                    is_settlement=True
                )
                messages.success(request, f"Successfully settled ₹{amount} with {friend.first_name or friend.username}!")
            else:
                messages.error(request, "Could not find a shared group to record the settlement.")
                
    return redirect('friends')

# --- 17. ACTIVITY VIEW (✅ NAYA FEATURE TIMELINE KE LIYE) ---
def activity_view(request):
    if not request.user.is_authenticated:
        return redirect('login')

    user_groups = Group.objects.filter(members=request.user)
    all_activities = Expense.objects.filter(group__in=user_groups).select_related('group', 'paid_by', 'receiver').order_by('-date')

    filter_type = request.GET.get('filter', 'all')
    if filter_type == 'expenses':
        activities = all_activities.filter(is_settlement=False)
    elif filter_type == 'settlements':
        activities = all_activities.filter(is_settlement=True)
    else:
        activities = all_activities

    summary = all_activities.aggregate(
        total_amount=Sum('amount'),
        total_expenses=Sum('amount', filter=Q(is_settlement=False)),
        total_settlements=Sum('amount', filter=Q(is_settlement=True)),
    )

    return render(request, 'activity.html', {
        'activities': activities[:50],
        'group_count': user_groups.count(),
        'total_activity_count': all_activities.count(),
        'activity_summary': {
            'total_amount': summary['total_amount'] or 0,
            'total_expenses': summary['total_expenses'] or 0,
            'total_settlements': summary['total_settlements'] or 0,
        },
        'filter_type': filter_type,
    })# ============================================
# ADVANCED GROUP MANAGEMENT FEATURES
# ============================================

# --- 18. DELETE/ARCHIVE GROUP (Admin Only) ---
def delete_group(request, group_id):
    """Permanently delete a group (admin only)"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    group = get_object_or_404(Group, id=group_id)
    
    if group.created_by != request.user:
        messages.error(request, "Only group admins can delete groups!")
        return redirect('my_groups')
    
    if request.method == 'POST':
        action = request.POST.get('action', 'delete')
        if action == 'delete':
            group_name = group.name
            group.delete()
            messages.success(request, f"Group '{group_name}' has been deleted permanently.")
        return redirect('my_groups')
    
    return render(request, 'delete_group_confirm.html', {'group': group})


# --- 19. EDIT GROUP (Admin Only) ---
def edit_group(request, group_id):
    """Edit group details like name, description, category"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    group = get_object_or_404(Group, id=group_id)
    
    # Check if user is admin
    if group.created_by != request.user:
        messages.error(request, "Only group admins can edit groups!")
        return redirect('my_groups')
    
    if request.method == 'POST':
        old_name = group.name
        old_category = group.category
        
        name = request.POST.get('name')
        description = request.POST.get('description')
        category = request.POST.get('category')
        
        if name and name.strip():
            group.name = name.strip()
            group.description = description or ""
            group.category = category or group.category
            group.save()
            
            # Log activity
            changes = []
            if old_name != group.name:
                changes.append(f"Name: '{old_name}'     '{group.name}'")
            if old_category != group.category:
                changes.append(f"Category: '{old_category}'     '{group.category}'")
            
            GroupActivity.objects.create(
                group=group,
                action_by=request.user,
                action_type='group_edited',
                description=f"Updated group details: {', '.join(changes)}"
            )
            
            messages.success(request, "Group updated successfully!")
            return redirect('group_detail', group_id=group.id)
        else:
            messages.error(request, "Group name cannot be empty!")
    
    context = {'group': group}
    return render(request, 'edit_group.html', context)


# --- 20. TRANSFER GROUP OWNERSHIP ---
def transfer_ownership(request, group_id):
    """Transfer group ownership to another member"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    group = get_object_or_404(Group, id=group_id)
    
    # Check if user is current admin
    if group.created_by != request.user:
        messages.error(request, "Only current group admin can transfer ownership!")
        return redirect('group_detail', group_id=group.id)
    
    if request.method == 'POST':
        new_admin_id = request.POST.get('new_admin_id')
        new_admin = get_object_or_404(User, id=new_admin_id)
        
        if new_admin not in group.members.all():
            messages.error(request, "New admin must be a group member!")
            return redirect('group_detail', group_id=group.id)
        
        # Transfer ownership
        old_admin = group.created_by
        group.created_by = new_admin
        group.save()
        
        # Log activity
        GroupActivity.objects.create(
            group=group,
            action_by=request.user,
            action_type='ownership_transferred',
            description=f"Transferred ownership from {old_admin.first_name or old_admin.username} to {new_admin.first_name or new_admin.username}",
            related_user=new_admin
        )
        
        # Send email to new admin
        try:
            subject = f"You're now the admin of '{group.name}' on SplitMitra"
            message = f"""
Hello {new_admin.first_name or new_admin.username},

Congratulations! {request.user.first_name or request.user.username} has transferred the admin rights of the group '{group.name}' to you.

You now have full control over this group including ability to:
- Edit group details
- Add/Remove members  
- Manage expenses
- Archive or delete the group

Visit your group: http://127.0.0.1:8000/group/{group.id}/

Best regards,
Team SplitMitra
            """
            send_mail(subject, message, getattr(settings, 'EMAIL_HOST_USER'), [new_admin.email], fail_silently=True)
        except:
            pass
        
        messages.success(request, f"Group ownership transferred to {new_admin.first_name or new_admin.username}!")
        return redirect('group_detail', group_id=group.id)
    
    context = {'group': group, 'members': group.members.exclude(id=request.user.id)}
    return render(request, 'transfer_ownership.html', context)


# --- 21. REMOVE MEMBER ---
def remove_member(request, group_id, member_id):
    """Remove a member from the group (admin only)"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    group = get_object_or_404(Group, id=group_id)
    member = get_object_or_404(User, id=member_id)
    
    # Check if user is admin
    if group.created_by != request.user:
        messages.error(request, "Only group admins can remove members!")
        return redirect('group_detail', group_id=group.id)
    
    if member not in group.members.all():
        messages.error(request, "Member not in this group!")
        return redirect('group_detail', group_id=group.id)
    
    if member == group.created_by:
        messages.error(request, "Cannot remove the group admin!")
        return redirect('group_detail', group_id=group.id)
    
    if request.method == 'POST':
        group.members.remove(member)
        
        # Log activity
        GroupActivity.objects.create(
            group=group,
            action_by=request.user,
            action_type='member_removed',
            description=f"Removed member: {member.first_name or member.username}",
            related_user=member
        )
        
        # Send notification email
        try:
            subject = f"You've been removed from '{group.name}' on SplitMitra"
            message = f"""
Hello {member.first_name or member.username},

You've been removed from the group '{group.name}' by {request.user.first_name or request.user.username}.

If you believe this was done by mistake, please contact the group admin.

Best regards,
Team SplitMitra
            """
            send_mail(subject, message, getattr(settings, 'EMAIL_HOST_USER'), [member.email], fail_silently=True)
        except:
            pass
        
        messages.success(request, f"{member.first_name or member.username} has been removed from the group!")
        return redirect('group_detail', group_id=group.id)
    
    return render(request, 'remove_member_confirm.html', {'group': group, 'member': member})


# --- 21B. MAKE MEMBER ADMIN ---
def make_admin(request, group_id, member_id):
    """Make a member an admin of the group (admin only)"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    group = get_object_or_404(Group, id=group_id)
    member = get_object_or_404(User, id=member_id)
    
    # Check if user is admin
    if group.created_by != request.user:
        messages.error(request, "Only group admins can change member roles!")
        return redirect('group_detail', group_id=group.id)
    
    if member not in group.members.all():
        messages.error(request, "Member not in this group!")
        return redirect('group_detail', group_id=group.id)
    
    if request.method == 'POST':
        # Update GroupMember role to admin
        group_member, created = GroupMember.objects.get_or_create(
            group=group,
            user=member,
            defaults={'role': 'admin'}
        )
        if not created:
            group_member.role = 'admin'
            group_member.save()
        
        # Log activity
        GroupActivity.objects.create(
            group=group,
            action_by=request.user,
            action_type='ownership_transferred',
            description=f"Made {member.first_name or member.username} an admin of the group",
            related_user=member
        )
        
        # Send notification email
        try:
            subject = f"You're now an admin of '{group.name}' on SplitMitra"
            message = f"""
Hello {member.first_name or member.username},

Congratulations! {request.user.first_name or request.user.username} has made you an admin of the group '{group.name}'.

You now have admin privileges including ability to:
- Edit group details
- Add/Remove members  
- Make other members admins
- Manage group settings

Visit your group: http://127.0.0.1:8000/group/{group.id}/

Best regards,
Team SplitMitra
            """
            send_mail(subject, message, getattr(settings, 'EMAIL_HOST_USER'), [member.email], fail_silently=True)
        except:
            pass
        
        messages.success(request, f"{member.first_name or member.username} is now an admin of the group!")
        return redirect('group_detail', group_id=group.id)
    
    return render(request, 'make_admin_confirm.html', {'group': group, 'member': member})


# --- 22. INVITE LINK API ---
def invite_link_api(request, group_id):
    """Return or generate a shareable invite link for the group in JSON format."""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required.'}, status=401)

    group = get_object_or_404(Group, id=group_id)
    if group.created_by != request.user:
        return JsonResponse({'error': 'Only group admins can generate invite links.'}, status=403)

    if request.method == 'POST':
        max_uses = request.POST.get('max_uses', 0)
        try:
            max_uses = int(max_uses) if max_uses else 0
        except:
            max_uses = 0

        invite = InviteLink.objects.create(
            group=group,
            created_by=request.user,
            max_uses=max_uses,
            is_active=True
        )

        GroupActivity.objects.create(
            group=group,
            action_by=request.user,
            action_type='group_edited',
            description=f"Generated new invite link with max uses: {max_uses if max_uses else 'Unlimited'}"
        )

        invite_url = f"http://127.0.0.1:8000/join-group/{invite.token}/"
        return JsonResponse({
            'invite_url': invite_url,
            'invite_id': invite.id,
            'max_uses': invite.max_uses,
            'used_count': invite.used_count,
        })

    active_invite = group.invite_links.filter(is_active=True).order_by('-created_at').first()
    if active_invite:
        invite_url = f"http://127.0.0.1:8000/join-group/{active_invite.token}/"
        return JsonResponse({
            'invite_url': invite_url,
            'invite_id': active_invite.id,
            'max_uses': active_invite.max_uses,
            'used_count': active_invite.used_count,
        })

    return JsonResponse({'invite_url': None})


# --- 23. GENERATE INVITE LINK ---
def generate_invite_link(request, group_id):
    """Generate a shareable invite link for the group"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    group = get_object_or_404(Group, id=group_id)
    
    # Check if user is admin
    if group.created_by != request.user:
        messages.error(request, "Only group admins can generate invite links!")
        return redirect('group_detail', group_id=group.id)
    
    if request.method == 'POST':
        max_uses = request.POST.get('max_uses', 0)
        try:
            max_uses = int(max_uses) if max_uses else 0
        except:
            max_uses = 0
        
        invite = InviteLink.objects.create(
            group=group,
            created_by=request.user,
            max_uses=max_uses,
            is_active=True
        )
        
        # Log activity
        GroupActivity.objects.create(
            group=group,
            action_by=request.user,
            action_type='group_edited',
            description=f"Generated new invite link with max uses: {max_uses if max_uses else 'Unlimited'}"
        )
        
        invite_url = f"http://127.0.0.1:8000/join-group/{invite.token}/"
        messages.success(request, f"Invite link generated successfully!")
        
        return render(request, 'invite_link_generated.html', {
            'group': group,
            'invite': invite,
            'invite_url': invite_url
        })
    
    # Get existing active invite links
    active_invites = group.invite_links.filter(is_active=True)
    
    context = {
        'group': group,
        'active_invites': active_invites,
    }
    return render(request, 'generate_invite_link.html', context)


# --- 23. JOIN GROUP VIA INVITE LINK ---
def join_group_via_link(request, token):
    """Accept an invite link and join a group"""
    if not request.user.is_authenticated:
        return redirect(f'login?next=/join-group/{token}/')
    
    invite = get_object_or_404(InviteLink, token=token)
    group = invite.group
    
    # Check if invite is valid
    if not invite.is_active:
        messages.error(request, "This invite link has been deactivated!")
        return redirect('my_groups')
    
    if invite.expires_at and invite.expires_at < timezone.now():
        messages.error(request, "This invite link has expired!")
        return redirect('my_groups')
    
    if invite.max_uses > 0 and invite.used_count >= invite.max_uses:
        messages.error(request, "This invite link has reached its usage limit!")
        return redirect('my_groups')
    
    # Add user to group if not already a member
    if request.user not in group.members.all():
        group.members.add(request.user)
        
        # Increment usage count
        invite.used_count += 1
        invite.save()
        
        # Log activity
        GroupActivity.objects.create(
            group=group,
            action_by=request.user,
            action_type='member_added',
            description=f"Joined group via invite link",
            related_user=request.user
        )
        
        messages.success(request, f"You've successfully joined '{group.name}'!")
    else:
        messages.info(request, f"You're already a member of '{group.name}'!")
    
    return redirect('group_detail', group_id=group.id)


# --- 24. DEACTIVATE/REVOKE INVITE LINK ---
def revoke_invite_link(request, invite_id):
    """Deactivate an invite link"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    invite = get_object_or_404(InviteLink, id=invite_id)
    group = invite.group
    
    # Check if user is admin
    if group.created_by != request.user:
        messages.error(request, "Only group admins can revoke invite links!")
        return redirect('group_detail', group_id=group.id)
    
    invite.is_active = False
    invite.save()
    
    # Log activity
    GroupActivity.objects.create(
        group=group,
        action_by=request.user,
        action_type='group_edited',
        description=f"Revoked invite link"
    )
    
    messages.success(request, "Invite link has been revoked!")
    return redirect('generate_invite_link', group_id=group.id)


# --- 25. VIEW GROUP ACTIVITY LOG ---
def group_activity_log(request, group_id):
    """View detailed activity log of a group"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    group = get_object_or_404(Group, id=group_id)
    
    if request.user not in group.members.all():
        messages.error(request, "You don't have access to this group!")
        return redirect('my_groups')
    
    # Get all activities for this group
    activities = group.activities.all().select_related('action_by', 'related_user').order_by('-timestamp')
    
    # Filter by type if requested
    activity_type = request.GET.get('type', 'all')
    if activity_type != 'all':
        activities = activities.filter(action_type=activity_type)
    
    context = {
        'group': group,
        'activities': activities[:100],
        'total_activities': group.activities.count(),
        'activity_type': activity_type,
    }
    
    return render(request, 'group_activity_log.html', context)


# --- 26. GET GROUP MEMBERS (AJAX) ---
def get_group_members(request, group_id):
    """Get group members with their roles (for AJAX)"""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    group = get_object_or_404(Group, id=group_id)
    
    if request.user not in group.members.all():
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    members_data = []
    for member in group.members.all():
        members_data.append({
            'id': member.id,
            'name': member.first_name or member.username,
            'email': member.email,
            'is_admin': member.id == group.created_by.id,
            'profile_image': f"https://ui-avatars.com/api/?name={member.first_name or member.username}&background=random&color=fff&bold=true"
        })
    
    return JsonResponse({
        'members': members_data,
        'total_members': len(members_data),
        'admin_id': group.created_by.id
    })


# --- 27. GET GROUP DETAILS (AJAX) ---
def get_group_details(request, group_id):
    """Get group details for modal/info display"""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    group = get_object_or_404(Group, id=group_id)
    
    if request.user not in group.members.all():
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    # Get group statistics
    expenses_count = group.expenses.count()
    members_count = group.members.count()
    total_amount = group.expenses.aggregate(Sum('amount'))['amount__sum'] or 0
    
    return JsonResponse({
        'id': group.id,
        'name': group.name,
        'description': group.description or '',
        'category': group.category,
        'created_by': group.created_by.first_name or group.created_by.username,
        'members_count': members_count,
        'expenses_count': expenses_count,
        'total_amount': float(total_amount),
        'is_archived': group.is_archived,
        'is_admin': request.user.id == group.created_by.id,
        'created_at': group.created_at.strftime('%d %b, %Y'),
    })


# ============================================================================
# BILL MANAGEMENT VIEWS - Advanced File Upload & Download System
# ============================================================================

# --- 25. UPLOAD BILL (Attached to Expense) ---
def upload_bill(request, expense_id):
    """Upload a bill/receipt for an expense"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    expense = get_object_or_404(Expense, id=expense_id)
    group = expense.group
    
    # Permission check: User must be part of group
    if request.user not in group.members.all():
        messages.error(request, "You don't have permission to upload bills for this group!")
        return redirect('group_detail', group_id=group.id)
    
    if request.method == 'POST':
        # File validation
        if 'bill' not in request.FILES:
            messages.error(request, "Please select a file to upload!")
            return redirect('group_detail', group_id=group.id)
        
        bill_file = request.FILES['bill']
        
        # File extension validation
        allowed_extensions = getattr(settings, 'ALLOWED_BILL_EXTENSIONS', ['pdf', 'jpg', 'jpeg', 'png'])
        file_ext = bill_file.name.split('.')[-1].lower()
        
        if file_ext not in allowed_extensions:
            messages.error(request, f"File type '.{file_ext}' is not allowed! Allowed: {', '.join(allowed_extensions)}")
            return redirect('group_detail', group_id=group.id)
        
        # File size validation
        max_size = getattr(settings, 'MAX_BILL_FILE_SIZE', 10485760)  # 10 MB default
        if bill_file.size > max_size:
            messages.error(request, f"File size exceeds maximum limit of {max_size / (1024*1024):.1f} MB!")
            return redirect('group_detail', group_id=group.id)
        
        try:
            # Create Bill record
            bill = Bill.objects.create(
                expense=expense,
                uploaded_by=request.user,
                file=bill_file,
                file_type=request.POST.get('file_type', 'bill'),
                description=request.POST.get('description', ''),
                is_public=request.POST.get('is_public', 'on') == 'on'
            )
            
            # If marked as primary, remove primary from other bills
            if request.POST.get('is_primary') == 'on':
                Bill.objects.filter(expense=expense).exclude(id=bill.id).update(is_primary=False)
                bill.is_primary = True
                bill.save()
            
            # Log activity
            GroupActivity.objects.create(
                group=group,
                action_by=request.user,
                action_type='expense_added',
                description=f"Uploaded bill '{bill.file_name}' for expense '{expense.description}' - {bill.get_file_type_display()}",
            )
            
            messages.success(request, f"✅ Bill '{bill.file_name}' uploaded successfully!")
            
        except Exception as e:
            messages.error(request, f"Error uploading bill: {str(e)}")
            return redirect('group_detail', group_id=group.id)
        
        return redirect('group_detail', group_id=group.id)
    
    return redirect('group_detail', group_id=group.id)


# --- 26. DOWNLOAD BILL (Track downloads) ---
def download_bill(request, bill_id):
    """Download bill file with audit trail"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    bill = get_object_or_404(Bill, id=bill_id)
    expense = bill.expense
    group = expense.group
    
    # Permission check
    if request.user not in group.members.all():
        messages.error(request, "You don't have permission to download this bill!")
        return redirect('login')
    
    # Update download tracking
    bill.download_count += 1
    bill.last_downloaded_by = request.user
    bill.last_downloaded_at = timezone.now()
    bill.save(update_fields=['download_count', 'last_downloaded_by', 'last_downloaded_at'])
    
    # Log activity
    GroupActivity.objects.create(
        group=group,
        action_by=request.user,
        action_type='expense_added',
        description=f"Downloaded bill '{bill.file_name}' from expense '{expense.description}'",
    )
    
    # Serve file
    try:
        from django.http import FileResponse
        response = FileResponse(bill.file.open('rb'), as_attachment=True, filename=bill.file_name)
        return response
    except Exception as e:
        messages.error(request, f"Error downloading file: {str(e)}")
        return redirect('group_detail', group_id=group.id)


# --- 27. DELETE BILL ---
def delete_bill(request, bill_id):
    """Delete a bill (only by uploader or admin)"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    bill = get_object_or_404(Bill, id=bill_id)
    expense = bill.expense
    group = expense.group
    
    # Permission check: Only uploader or group admin can delete
    if request.user != bill.uploaded_by and request.user != group.created_by:
        messages.error(request, "You don't have permission to delete this bill!")
        return redirect('group_detail', group_id=group.id)
    
    bill_name = bill.file_name
    
    try:
        # Delete file from storage
        if bill.file:
            bill.file.delete()
        
        # Log activity before deleting
        GroupActivity.objects.create(
            group=group,
            action_by=request.user,
            action_type='expense_deleted',
            description=f"Deleted bill '{bill_name}' from expense '{expense.description}'",
        )
        
        # Delete database record
        bill.delete()
        messages.success(request, f"✅ Bill '{bill_name}' deleted successfully!")
        
    except Exception as e:
        messages.error(request, f"Error deleting bill: {str(e)}")
    
    return redirect('group_detail', group_id=group.id)


# --- 28. VIEW BILL DETAILS (AJAX) ---
def get_bill_details(request, bill_id):
    """Get bill details for modal display"""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    bill = get_object_or_404(Bill, id=bill_id)
    expense = bill.expense
    group = expense.group
    
    # Permission check
    if request.user not in group.members.all():
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    return JsonResponse({
        'id': bill.id,
        'expense_id': expense.id,
        'expense_description': expense.description,
        'file_name': bill.file_name,
        'file_type': bill.get_file_type_display(),
        'file_size': f"{bill.file_size_mb} MB",
        'file_extension': bill.file_extension,
        'is_image': bill.is_image,
        'is_pdf': bill.is_pdf,
        'description': bill.description or 'No description',
        'uploaded_by': bill.uploaded_by.first_name or bill.uploaded_by.username,
        'uploaded_by_email': bill.uploaded_by.email,
        'uploaded_at': bill.uploaded_at.strftime('%d %b, %Y at %H:%M'),
        'is_primary': bill.is_primary,
        'download_count': bill.download_count,
        'is_public': bill.is_public,
        'file_url': bill.file.url if bill.file else '',
        'can_delete': request.user == bill.uploaded_by or request.user == group.created_by,
        'can_download': bill.is_public or request.user in group.members.all(),
    })


# --- 29. LIST BILLS FOR EXPENSE (AJAX) ---
def get_expense_bills(request, expense_id):
    """Get all bills for an expense"""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    expense = get_object_or_404(Expense, id=expense_id)
    group = expense.group
    
    # Permission check
    if request.user not in group.members.all():
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    bills = expense.bills.filter(is_public=True) | expense.bills.filter(uploaded_by=request.user)
    bills_data = []
    
    for bill in bills.order_by('-is_primary', '-uploaded_at'):
        bills_data.append({
            'id': bill.id,
            'file_name': bill.file_name,
            'file_type': bill.get_file_type_display(),
            'file_size': f"{bill.file_size_mb} MB",
            'is_image': bill.is_image,
            'is_pdf': bill.is_pdf,
            'is_primary': bill.is_primary,
            'uploaded_by': bill.uploaded_by.first_name or bill.uploaded_by.username,
            'uploaded_at': bill.uploaded_at.strftime('%d %b, %Y'),
            'download_count': bill.download_count,
            'file_url': bill.file.url if bill.file else '',
        })
    
    return JsonResponse({
        'expense_id': expense_id,
        'total_bills': bills.count(),
        'bills': bills_data,
    })


# --- 30. DELETE EXPENSE ---
def delete_expense(request, expense_id):
    """Delete an expense (admin or payer only)"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    expense = get_object_or_404(Expense, id=expense_id)
    group = expense.group
    
    # Permission checks: Only admin or the person who paid can delete
    is_admin = group.created_by == request.user
    is_payer = expense.paid_by == request.user
    
    if not (is_admin or is_payer):
        messages.error(request, "You don't have permission to delete this expense.")
        return redirect('group_detail', group_id=group.id)
    
    # Check if expense is already deleted
    if expense.is_deleted:
        messages.warning(request, "This expense has already been deleted.")
        return redirect('group_detail', group_id=group.id)
    
    if request.method == 'POST':
        # Soft delete the expense
        expense.is_deleted = True
        expense.save()
        
        # Log activity
        paid_by_name = expense.paid_by.first_name or expense.paid_by.username
        GroupActivity.objects.create(
            group=group,
            action_by=request.user,
            action_type='expense_deleted',
            description=f"Deleted expense: '{expense.description}' (₹{expense.amount}) paid by {paid_by_name}",
            related_user=expense.paid_by
        )
        
        messages.success(request, "Expense deleted successfully!")
        return redirect('group_detail', group_id=group.id)
    
    # For GET requests, show confirmation
    return render(request, 'confirm_delete_expense.html', {'expense': expense, 'group': group})

