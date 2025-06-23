from django.shortcuts import render,redirect
from django.db import connection ,IntegrityError
from django.contrib import messages
from django.http import JsonResponse
import random ,datetime
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone

def index(request):
    return render(request,'index.html')

def aboutus(request):
    return render(request,'aboutus.html')

def send_otp_email(user_email, otp):
    with connection.cursor() as cursor:
        cursor.execute("SELECT u_name FROM users WHERE u_email = %s",[user_email])
        result = cursor.fetchone()
        if result:
            user_name=result[0]
        subject = 'Your OTP for IllnessIQ Login'
        message = f'''Dear {user_name},\n\nYour OTP code is: {otp}. It is valid for 5 minutes.\n\n'''
        email_from = settings.EMAIL_HOST_USER
        send_mail(subject, message, email_from, [user_email])

def login(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        with connection.cursor() as cursor:
            cursor.execute("SELECT u_id, u_role FROM users WHERE u_email = %s", [email])
            user = cursor.fetchone()

        if user:
            user_id, role = user
            otp = str(random.randint(100000, 999999))
            created_at = datetime.datetime.now()
            expires_at = datetime.datetime.now() + datetime.timedelta(minutes=5)

            with connection.cursor() as cursor:
                cursor.execute("INSERT INTO otp_verification (u_id, otp_code, created_at, expires_at, is_verified)VALUES (%s, %s, %s, %s, %s)", [user_id, otp, created_at, expires_at, False])

            request.session['otp_user_id'] = user_id
            request.session['otp_user_email'] = email
            request.session['otp_user_role'] = role

            send_otp_email(email, otp)
            return redirect('verify_otp') 

        else:
            messages.error(request, 'Invalid email or email not registered')
    return render(request, 'login.html')

def verify_otp(request):
    if not request.session.get('otp_user_id'):
        return redirect('login')

    user_id = request.session.get('otp_user_id')
    email = request.session.get('otp_user_email')

    if request.method == 'POST':
        if 'resend' in request.POST:
            otp = str(random.randint(100000, 999999))
            created_at = datetime.datetime.now()
            expires_at = created_at + datetime.timedelta(minutes=5)

            with connection.cursor() as cursor:
                cursor.execute("INSERT INTO otp_verification (u_id, otp_code, created_at, expires_at, is_verified)VALUES (%s, %s, %s, %s, %s)", [user_id, otp, created_at, expires_at, False])

            send_otp_email(email, otp)
            messages.success(request, 'A new OTP has been sent to your email.')
            return redirect('verify_otp')

        else:
            input_otp = request.POST.get('otp')

            with connection.cursor() as cursor:
                cursor.execute("SELECT otp_id FROM otp_verification WHERE u_id = %s AND otp_code = %s AND is_verified = FALSE AND expires_at > NOW() ORDER BY created_at DESC LIMIT 1", [user_id, input_otp])
                row = cursor.fetchone()

                if row:
                    cursor.execute("UPDATE otp_verification SET is_verified = TRUE WHERE otp_id = %s", [row[0]])

                    request.session['user_id'] = user_id
                    role = request.session.get('otp_user_role')
                    request.session['user_role']=role

                    for key in ['otp_user_id', 'otp_user_role', 'otp_user_email']:
                        request.session.pop(key, None)
                        
                    return redirect('admin_dashboard' if role == 'admin' else 'user_dashboard')
                else:
                    messages.error(request, 'Invalid or expired OTP.')

    return render(request, 'verify_otp.html')



def signup(request):
    if request.method == 'POST':
        full_name = request.POST.get('full_name')
        email = request.POST.get('email')
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM users WHERE u_email = %s", [email])
            if cursor.fetchone()[0] > 0:
                messages.error(request, "Email already exists.")
                return render(request, 'signup.html')
    
            cursor.execute("INSERT INTO users (u_name, u_email,u_role) VALUES (%s, %s, %s)", [full_name, email,'users'])
        messages.success(request, "Account created successfully.")
        subject = 'Welcome To IllnessIQ'
        message = f'''Dear {full_name},
        Welcome to IllnessIQ – your personal companion for better health insights. We’re thrilled to have you on board. With IllnessIQ, you can:
        
        - Check your risk for common illnesses like diabetes, liver, heart, and thyroid problems.
        - Get AI-based recommendations for health improvements.
        - Track your medical history and wellness goals easily.
        
        Feel free to explore and take control of your health today!
        
        Best regards,  
        The IllnessIQ Team'''
        email_from = settings.EMAIL_HOST_USER
        send_mail(subject, message, email_from, [email])
    return render(request,'signup.html')

def user_dashboard(request):
    if not request.session.get('user_id'):
        return redirect('login')
    return render(request,'user_dash.html')


def admin_dashboard(request):
    if request.session.get('user_role')!="admin":
        return redirect('login')
    return render(request,'admin_dash.html')

def diabetes_risk(request):
    if not request.session.get('user_id'):
        return redirect('login')
    return render(request,'diabetes_risk.html')

def heart_risk(request):
    if not request.session.get('user_id'):
        return redirect('login')
    return render(request,'heart_risk.html')

def liver_risk(request):
    if not request.session.get('user_id'):
        return redirect('login')
    return render(request,'liver_risk.html')

def thyroid_risk(request):
    if not request.session.get('user_id'):
        return redirect('login')
    return render(request,'thyroid_risk.html')

def logout(request):
    request.session.flush()
    return redirect('index')

def feedback(request):
    if not request.session.get('user_id'):
        return redirect('login')
    
    if request.method == 'POST':
        rating = request.POST.get('rating', '').strip()
        description = request.POST.get('message', '').strip()
        user_id = request.session.get('user_id')
        if not rating or not description:
            messages.error(request, "All fields are required.")
            return redirect('feedback')

        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO feedback (f_description, u_id, rating)
                    VALUES (%s, %s, %s)
                """, [description, user_id, rating])
            messages.success(request, "Feedback Received Successfully!")
            return redirect('feedback')
        except IntegrityError:
            messages.error(request, "An error occurred while submitting your feedback.")
            return redirect('feedback')

    return render(request, 'feedback.html')
def report_issue(request):
    if not request.session.get('user_id'):
        return redirect('login')
    
    if request.method == 'POST':
        issue_title = request.POST.get('issue_title')
        description = request.POST.get('description')
        user = request.session.get('user_id')
        with connection.cursor() as cursor:
            cursor.execute("INSERT INTO issue_report (ir_name, ir_description, u_id) VALUES (%s, %s, %s)", [issue_title, description, user])
        messages.success(request, "Issue Reported!!!.")
    return render(request,'report_issue.html')
