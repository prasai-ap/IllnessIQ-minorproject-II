from django.shortcuts import render,redirect
from django.db import connection ,IntegrityError
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
import random ,datetime
from datetime import date
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.template.loader import get_template
import os
import joblib
import pandas as pd
from xhtml2pdf import pisa
import markdown 
import google.generativeai as genai

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
    if request.session.get('user_id') and request.session.get('user_role'):
        role = request.session.get('user_role')
        if role == "admin":
            return redirect('admin_dashboard')
        elif role == "users":
            return redirect('user_dashboard')

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
            # Check if email already exists
            cursor.execute("SELECT COUNT(*) FROM users WHERE u_email = %s", [email])
            if cursor.fetchone()[0] > 0:
                messages.error(request, "Email already exists.")
                return render(request, 'signup.html')

            # Insert new user
            cursor.execute("INSERT INTO users (u_name, u_email, u_role) VALUES (%s, %s, %s) RETURNING u_id", 
                           [full_name, email, 'users'])
            user_id = cursor.fetchone()[0]

        # Save session values
        request.session['otp_user_id'] = user_id
        request.session['otp_user_email'] = email
        request.session['otp_user_role'] = 'users'

        # Generate OTP
        otp = str(random.randint(100000, 999999))
        created_at = datetime.datetime.now()
        expires_at = created_at + datetime.timedelta(minutes=5)

        # Save OTP to DB
        with connection.cursor() as cursor:
            cursor.execute("""INSERT INTO otp_verification (u_id, otp_code, created_at, expires_at, is_verified)
                              VALUES (%s, %s, %s, %s, %s)""", [user_id, otp, created_at, expires_at, False])

        # Send combined email
        subject = 'Welcome to IllnessIQ – Your OTP & Introduction'
        message = f'''Dear {full_name},

Welcome to IllnessIQ – your personal companion for better health insights. We're thrilled to have you on board!

Here’s your OTP to verify your email: {otp}
(This OTP is valid for 5 minutes)

Once verified, you can:
- Check your risk for diseases like diabetes, heart, liver, and thyroid
- Get AI-based health recommendations
- Track your reports and progress

Thank you for joining!

– The IllnessIQ Team
'''
        email_from = settings.EMAIL_HOST_USER
        send_mail(subject, message, email_from, [email])
        return redirect('verify_otp')

    return render(request, 'signup.html')


from django.shortcuts import render, redirect
from django.db import connection

def user_dashboard(request):
    if not request.session.get('user_id'):
        return redirect('login')

    user_id = request.session.get('user_id')
    query = """
        SELECT 'Diabetes' AS disease, patient_name, risk_status, entry_date 
        FROM diabetes_medical_details d
        JOIN diabetes_risk r ON d.d_id = r.d_id
        WHERE d.u_id = %s AND d.entry_date >= CURRENT_DATE - INTERVAL '7 days'

        UNION ALL

        SELECT 'Heart', patient_name, risk_status, entry_date 
        FROM heart_medical_details h
        JOIN heart_risk r ON h.h_id = r.h_id
        WHERE h.u_id = %s AND h.entry_date >= CURRENT_DATE - INTERVAL '7 days'

        UNION ALL

        SELECT 'Liver', patient_name, risk_status, entry_date 
        FROM liver_medical_details l
        JOIN liver_risk r ON l.l_id = r.l_id
        WHERE l.u_id = %s AND l.entry_date >= CURRENT_DATE - INTERVAL '7 days'

        UNION ALL

        SELECT 'Thyroid', patient_name, risk_status, entry_date 
        FROM thyroid_medical_details t
        JOIN thyroid_risk r ON t.t_id = r.t_id
        WHERE t.u_id = %s AND t.entry_date >= CURRENT_DATE - INTERVAL '7 days'

        ORDER BY entry_date DESC
        LIMIT 5;
    """

    with connection.cursor() as cursor:
        cursor.execute(query, [user_id, user_id, user_id, user_id])
        rows = cursor.fetchall()

    recent_activities = [
        {
            'disease': row[0],
            'patient_name': row[1],
            'risk_status': row[2],
            'entry_date': row[3]
        }
        for row in rows
    ]

    return render(request, 'user_dash.html', {
        'recent_activities': recent_activities
    })



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


diabetes_model = os.path.join(settings.BASE_DIR, 'illnessiq_app', 'ml_models', 'diabetes_model.pkl')
heart_model = os.path.join(settings.BASE_DIR, 'illnessiq_app', 'ml_models', 'heart_model.pkl')
liver_model = os.path.join(settings.BASE_DIR, 'illnessiq_app', 'ml_models', 'liver_model.pkl')
thyroid_model = os.path.join(settings.BASE_DIR, 'illnessiq_app', 'ml_models', 'thyroid_model.pkl')

gender_map = {'Male': 1, 'Female': 0}
hypertension_map = {'Yes': 1, 'No': 0}
heart_disease_map = {'Yes': 1, 'No': 0}
smoking_map = {'Never': 0, 'Former': 1, 'Current': 2}

from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import connection
from datetime import date
import pandas as pd
import joblib
import markdown
import google.generativeai as genai

def predict_diabetes(request):
    if not request.session.get('user_id'):
        return redirect('login')

    try:
        model = joblib.load(diabetes_model)
    except FileNotFoundError:
        return render(request, 'diabetes_risk_result.html', {
            'result': "Error: Prediction model file not found.",
            'recommendations': ["<p>Please contact support regarding a system configuration error.</p>"]
        })
    except Exception as e:
        return render(request, 'diabetes_risk_result.html', {
            'result': f"Error loading prediction model: {str(e)}",
            'recommendations': ["<p>Please contact support regarding a system configuration error.</p>"]
        })

    user = request.session.get('user_id')

    if request.method == 'POST':
        patient_name = request.POST.get('Patient_Name')
        age_raw = request.POST.get('Age')
        gender = request.POST.get('Gender')
        hypertension = request.POST.get('Hypertension')
        heart_disease = request.POST.get('Heart_Disease')
        smoking_status = request.POST.get('Smoking_Status')
        bmi_raw = request.POST.get('BMI')
        hba1c_raw = request.POST.get('HbA1c_Level')
        glucose_raw = request.POST.get('Blood_Glucose_Level')

        
        if not all([patient_name, age_raw, gender, hypertension, heart_disease, smoking_status, bmi_raw, hba1c_raw, glucose_raw]):
            messages.error(request, "All fields are required. Please fill them out.")
            return redirect('diabetes_risk') 

    
        try:
            age = int(age_raw)
            bmi = float(bmi_raw)
            hba1c = float(hba1c_raw)
            glucose = float(glucose_raw)
        except ValueError:
            messages.error(request, "Please enter valid numeric values for age, BMI, HbA1c, and glucose.")
            return redirect(request, 'diabetes_risk')

        try:
            input_data = pd.DataFrame([{
                'gender': gender_map.get(gender),
                'age': age,
                'hypertension': hypertension_map.get(hypertension),
                'heart_disease': heart_disease_map.get(heart_disease),
                'smoking_history': smoking_map.get(smoking_status),
                'bmi': bmi,
                'HbA1c_level': hba1c,
                'blood_glucose_level': glucose
            }])

            prediction = model.predict(input_data)[0]
            result = "High Risk" if prediction == 1 else "Low Risk"
            today = date.today()

            with connection.cursor() as cursor:
                cursor.execute("""INSERT INTO diabetes_medical_details 
                    (u_id, patient_name, age, gender, hypertension, heart_diseases, smoking_history, bmi, hba1c, blood_glucose, entry_date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING d_id""",
                    [user, patient_name, age, gender, hypertension, heart_disease, smoking_status, bmi, hba1c, glucose, today])
                d_id = cursor.fetchone()[0]

                cursor.execute("INSERT INTO diabetes_risk (risk_status, d_id) VALUES (%s, %s) RETURNING dr_id", [result, d_id])
                dr_id = cursor.fetchone()[0]

            prompt = f"""Based on the following user data, provide personalized health recommendations for diabetes risk management.
            The user is a {gender.lower()} aged {age} with a {result} of diabetes.
            Key metrics: BMI = {bmi}, HbA1c = {hba1c}, Blood Glucose = {glucose}.
            Health history: Smoking Status = {smoking_status}, Hypertension = {hypertension}, Heart Disease = {heart_disease}.

            Structure your response with clear headings for categories like "Summary of Risk", "Lifestyle Recommendations", "Dietary Advice", and "Medical Considerations".
            Use bullet points for individual recommendations within each category.
            Start directly with the recommendations, no introductory sentences before the first heading.
            """

            model_gemini = genai.GenerativeModel('gemini-2.5-flash')
            response = model_gemini.generate_content(prompt)
            recommendation_text = response.text.strip()
            sections = [s.strip() for s in recommendation_text.split("\n\n") if s.strip()]
            recommendations = [markdown.markdown(section) for section in sections]

            with connection.cursor() as cursor:
                cursor.execute("INSERT INTO diabetes_recommendation (dr_id, recommendation) VALUES (%s, %s)", [dr_id, recommendation_text])

            return render(request, 'diabetes_risk_result.html', {
                'result': result,
                'recommendations': recommendations,
                'dr_id': dr_id
            })

        except Exception as e:
            return render(request, 'diabetes_risk_result.html', {
                'result': f"Unexpected error: {str(e)}",
                'recommendations': ["<p>An unexpected issue occurred. Please try again later.</p>"]
            })

def predict_heart(request):
    if not request.session.get('user_id'):
        return redirect('login')

    try:
        model = joblib.load(heart_model)
    except Exception as e:
        return render(request, 'heart_risk_result.html', {
            'result': f"Model Error: {str(e)}",
            'recommendations': ["<p>Please contact support.</p>"]
        })

    user_id = request.session.get('user_id')

    if request.method == 'POST':
        try:
            patient_name = request.POST.get('Patient_Name')
            age_raw = request.POST.get('Age')
            gender = request.POST.get('Gender')
            cholesterol_raw = request.POST.get('Cholesterol')
            fbs = request.POST.get('Fasting_Blood_Sugar')
            hr_raw = request.POST.get('Heart_Rate')

            if not all([patient_name, age_raw, gender, cholesterol_raw, fbs, hr_raw]):
                messages.error(request, "All fields are required.")
                return redirect('heart_risk')

            age = int(age_raw)
            cholesterol = float(cholesterol_raw)
            heart_rate = int(hr_raw)
            gender_encoded = 1 if gender.lower() == 'male' else 0
            fbs_encoded = 1 if fbs.lower() == 'yes' else 0

            input_data = pd.DataFrame([{
                'age': age, 
                'gender': gender_encoded,
                'chol': cholesterol, 
                'fbs': fbs_encoded,
                'thalach': heart_rate
            }])

            prediction = model.predict(input_data)[0]
            result = "High Risk" if prediction == 1 else "Low Risk"
            today = date.today()

            with connection.cursor() as cursor:
                cursor.execute("""INSERT INTO heart_medical_details 
                    (u_id, patient_name, age, gender, cholesterol, high_blood_sugar, heart_rate, entry_date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING h_id""",
                    [user_id, patient_name, age, gender, cholesterol, fbs, heart_rate, today])
                h_id = cursor.fetchone()[0]

                cursor.execute("INSERT INTO heart_risk (risk_status, h_id) VALUES (%s, %s) RETURNING hr_id", [result, h_id])
                hr_id = cursor.fetchone()[0]

            
            prompt = f"""Based on the following user data, provide personalized health recommendations for heart disease risk management.
            The user is a {gender.lower()} aged {age} with a {result} of heart disease.
            Key metrics: cholesterol = {cholesterol}, high fasting blood sugar = {fbs}, heart rate = {heart_rate}.

            Structure your response with clear headings for categories like "Summary of Risk", "Lifestyle Recommendations", "Dietary Advice", and "Medical Considerations".
            Use bullet points for individual recommendations within each category.
            Start directly with the recommendations, no introductory sentences before the first heading.
            """

            response = genai.GenerativeModel('gemini-2.5-flash').generate_content(prompt)
            recommendation_text = response.text.strip()
            recommendations = [markdown.markdown(s.strip()) for s in recommendation_text.split("\n\n") if s.strip()]

            with connection.cursor() as cursor:
                cursor.execute("INSERT INTO heart_recommendation (hr_id, recommendation) VALUES (%s, %s)", [hr_id, recommendation_text])

            return render(request, 'heart_risk_result.html', {
                'result': result,
                'recommendations': recommendations,
                'hr_id': hr_id
            })

        except Exception as e:
            return render(request, 'heart_risk_result.html', {
                'result': f"Error: {str(e)}",
                'recommendations': ["<p>Please check your input.</p>"]
            })


def predict_liver(request):
    if not request.session.get('user_id'):
        return redirect('login')

    try:
        model = joblib.load(liver_model)
    except Exception as e:
        return render(request, 'liver_risk_result.html', {
            'result': f"Model Error: {str(e)}",
            'recommendations': ["<p>Contact support for assistance.</p>"]
        })

    user_id = request.session.get('user_id')

    if request.method == 'POST':
        try:
            patient_name = request.POST.get('Patient_Name')
            age_raw = request.POST.get('Age')
            gender = request.POST.get('Gender')
            tb = request.POST.get('Total_Bilirubin')
            db = request.POST.get('Direct_Bilirubin')
            sgot = request.POST.get('SGOT')
            sgpt = request.POST.get('SGPT')
            alkp = request.POST.get('Alkaline_Phosphatase')
            protein = request.POST.get('Total_Protein')
            albumin = request.POST.get('Albumin')
            ag_ratio = request.POST.get('A_G_Ratio')

            if not all([patient_name, age_raw, gender, tb, db, sgot, sgpt, alkp, protein, albumin, ag_ratio]):
                messages.error(request, "All fields are required.")
                return redirect('liver_risk')

            age = int(age_raw) 
            tb = float(tb)
            db = float(db)
            alkp = float(alkp)
            sgpt = float(sgpt)
            sgot = float(sgot)
            protein = float(protein)
            albumin = float(albumin)
            ag_ratio = float(ag_ratio)

            input_data = pd.DataFrame([{
                'Age ': age,
                'Gender': 1 if gender.lower() == 'male' else 0,
                'Total_Bilirubin': tb,
                'Direct_Bilirubin': db,
                'Alkaline_Phosphatase': alkp,
                'Sgpt': sgpt,
                'Sgot ': sgot,
                'Total_Proteins': protein,
                ' Albumin': albumin,
                'A_G_Ratio': ag_ratio
            }])

            prediction = model.predict(input_data)[0]
            result = "High Risk" if prediction == 1 else "Low Risk"
            today = date.today()

            with connection.cursor() as cursor:
                cursor.execute("""INSERT INTO liver_medical_details 
                    (u_id, patient_name, age, gender, bilirubin_total, bilirubin_direct, sgot, sgpt, alkaline_phosphatase, protein, albumin, ag_ratio, entry_date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING l_id""",
                    [user_id, patient_name, age, gender, tb, db, sgot, sgpt, alkp, protein, albumin, ag_ratio, today])
                l_id = cursor.fetchone()[0]

                cursor.execute("INSERT INTO liver_risk (risk_status, l_id) VALUES (%s, %s) RETURNING lr_id", [result, l_id])
                lr_id = cursor.fetchone()[0]

            prompt = f"""Based on the following user data, provide personalized health recommendations for liver health management.
            The user is a {gender.lower()} aged {age} with a {result} of liver disease.
            Key metrics: Total Bilirubin = {tb}, Direct Bilirubin = {db}, SGOT = {sgot}, SGPT = {sgpt}, ALP = {alkp}, Protein = {protein}, Albumin = {albumin}, A/G Ratio = {ag_ratio}.

            Structure your response with clear headings for categories like "Summary of Risk", "Lifestyle Recommendations", "Dietary Advice", and "Medical Considerations".
            Use bullet points for individual recommendations within each category.
            Start directly with the recommendations, no introductory sentences before the first heading.
            """
            response = genai.GenerativeModel('gemini-2.5-flash').generate_content(prompt)
            recommendation_text = response.text.strip()
            recommendations = [markdown.markdown(s.strip()) for s in recommendation_text.split("\n\n") if s.strip()]

            with connection.cursor() as cursor:
                cursor.execute("INSERT INTO liver_recommendation (lr_id, recommendation) VALUES (%s, %s)", [lr_id, recommendation_text])

            return render(request, 'liver_risk_result.html', {
                'result': result,
                'recommendations': recommendations,
                'lr_id': lr_id
            })

        except Exception as e:
            return render(request, 'liver_risk_result.html', {
                'result': f"Unexpected error: {str(e)}",
                'recommendations': ["<p>Please check your entries and try again.</p>"]
            })


def predict_thyroid(request):
    if not request.session.get('user_id'):
        return redirect('login')

    try:
        model = joblib.load(thyroid_model)
    except Exception as e:
        return render(request, 'thyroid_risk_result.html', {
            'result': f"Model Error: {str(e)}",
            'recommendations': ["<p>Contact support.</p>"]
        })

    user_id = request.session.get('user_id')

    if request.method == 'POST':
        try:
            patient_name = request.POST.get('Patient_Name')
            age_raw = request.POST.get('Age')
            gender = request.POST.get('Gender')
            tsh = request.POST.get('TSH')
            ft4 = request.POST.get('FT4')
            ft3 = request.POST.get('FT3')

            if not all([patient_name, age_raw, gender, tsh, ft4, ft3]):
                messages.error(request, "All fields are required.")
                return redirect('thyroid_risk')

            age = int(age_raw)
            tsh = float(tsh)
            ft3 = float(ft3)
            ft4 = float(ft4)
            
            input_data = pd.DataFrame([{
                'age': age,
                'gender': 1 if gender.lower() == 'male' else 0,
                'TSH': tsh,
                'T3': ft3,
                'T4': ft4
            }])

            prediction = model.predict(input_data)[0]
            result = "High Risk" if prediction == 1 else "Low Risk"
            today = date.today()

            with connection.cursor() as cursor:
                cursor.execute("""INSERT INTO thyroid_medical_details (u_id, age, gender, tsh, ft4, ft3, patient_name, entry_date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING t_id""",
                    [user_id, age, gender, tsh, ft4, ft3, patient_name, today])
                t_id = cursor.fetchone()[0]

                cursor.execute("INSERT INTO thyroid_risk (risk_status, t_id) VALUES (%s, %s) RETURNING tr_id", [result, t_id])
                tr_id = cursor.fetchone()[0]

            prompt = f"""Based on the following user data, provide personalized health recommendations for thyroid disease risk management.
            The user is a {gender.lower()} aged {age} with a {result} of thyroid disease.
            Key metrics: TSH = {tsh}, FT4 = {ft4}, FT3 = {ft3}.

            Structure your response with clear headings for categories like "Summary of Risk", "Lifestyle Recommendations", "Dietary Advice", and "Medical Considerations".
            Use bullet points for individual recommendations within each category.
            Start directly with the recommendations, no introductory sentences before the first heading.
            
            """
            response = genai.GenerativeModel('gemini-2.5-flash').generate_content(prompt)
            recommendation_text = response.text.strip()
            recommendations = [markdown.markdown(s.strip()) for s in recommendation_text.split("\n\n") if s.strip()]

            with connection.cursor() as cursor:
                cursor.execute("INSERT INTO thyroid_recommendation (tr_id, recommendation) VALUES (%s, %s)", [tr_id, recommendation_text])

            return render(request, 'thyroid_risk_result.html', {
                'result': result,
                'recommendations': recommendations,
                'tr_id': tr_id
            })

        except Exception as e:
            return render(request, 'thyroid_risk_result.html', {
                'result': f"Unexpected error: {str(e)}",
                'recommendations': ["<p>Please try again later.</p>"]
            })



def download_diabetes_report(request, dr_id):
    if not request.session.get('user_id'):
        return redirect('login')

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT d.patient_name, d.age, d.gender, d.hypertension, d.heart_diseases,
                   d.smoking_history, d.bmi, d.hba1c, d.blood_glucose,
                   r.risk_status, rec.recommendation
            FROM diabetes_medical_details d
            JOIN diabetes_risk r ON d.d_id = r.d_id
            JOIN diabetes_recommendation rec ON r.dr_id = rec.dr_id
            WHERE r.dr_id = %s
        """, [dr_id])
        row = cursor.fetchone()

    if not row:
        return HttpResponse("No data found", status=404)

    logo_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'logo.png')
    static_url = f'file://{logo_path.rsplit("/", 1)[0]}/'

    context = {
        'patient_name': row[0],
        'age': row[1],
        'gender': row[2],
        'hypertension': row[3],
        'heart_disease': row[4],
        'smoking': row[5],
        'bmi': row[6],
        'hba1c': row[7],
        'glucose': row[8],
        'risk_status': row[9],
        'recommendation_html': markdown.markdown(row[10] or ""),
        'date': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'STATIC_URL': static_url
    }

    template = get_template("diabetes_report_template.html")
    html = template.render(context)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Diabetes_Report_{context["patient_name"]}.pdf"'

    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse("PDF generation failed", status=500)

    return response


def download_heart_report(request, hr_id):
    if not request.session.get('user_id'):
        return redirect('login')

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT h.patient_name, h.age, h.gender, h.cholesterol, h.high_blood_sugar, h.heart_rate,
                   r.risk_status, rec.recommendation
            FROM heart_medical_details h
            JOIN heart_risk r ON h.h_id = r.h_id
            JOIN heart_recommendation rec ON r.hr_id = rec.hr_id
            WHERE r.hr_id = %s
        """, [hr_id])
        row = cursor.fetchone()

    if not row:
        return HttpResponse("No data found", status=404)

    logo_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'logo.png')
    static_url = f'file://{logo_path.rsplit("/", 1)[0]}/'

    context = {
        'patient_name': row[0],
        'age': row[1],
        'gender': row[2],
        'cholesterol': row[3],
        'fasting_blood_sugar': row[4],
        'heart_rate': row[5],
        'risk_status': row[6],
        'recommendation_html': markdown.markdown(row[7] or ""),
        'date': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'STATIC_URL': static_url
    }

    template = get_template("heart_report_template.html")
    html = template.render(context)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Heart_Report_{context["patient_name"]}.pdf"'

    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse("PDF generation failed", status=500)

    return response

def download_liver_report(request, lr_id):
    if not request.session.get('user_id'):
        return redirect('login')

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT l.patient_name, l.age, l.gender, l.bilirubin_total, l.bilirubin_direct,
                   l.sgot, l.sgpt, l.alkaline_phosphatase, l.protein, l.albumin, l.ag_ratio,
                   r.risk_status, rec.recommendation
            FROM liver_medical_details l
            JOIN liver_risk r ON l.l_id = r.l_id
            JOIN liver_recommendation rec ON r.lr_id = rec.lr_id
            WHERE r.lr_id = %s
        """, [lr_id])
        row = cursor.fetchone()

    if not row:
        return HttpResponse("No data found", status=404)

    logo_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'logo.png')
    static_url = f'file://{logo_path.rsplit("/", 1)[0]}/'

    context = {
        'patient_name': row[0],
        'age': row[1],
        'gender': row[2],
        'total_bilirubin': row[3],
        'direct_bilirubin': row[4],
        'sgot': row[5],
        'sgpt': row[6],
        'alkaline_phosphatase': row[7],
        'total_protein': row[8],
        'albumin': row[9],
        'a_g_ratio': row[10],
        'risk_status': row[11],
        'recommendation_html': markdown.markdown(row[12] or ""),
        'date': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'STATIC_URL': static_url
    }

    template = get_template("liver_report_template.html")
    html = template.render(context)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Liver_Report_{context["patient_name"]}.pdf"'

    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse("PDF generation failed", status=500)

    return response

def download_thyroid_report(request, tr_id):
    if not request.session.get('user_id'):
        return redirect('login')

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT t.patient_name, t.age, t.gender, t.tsh, t.ft4, t.ft3,
                   r.risk_status, rec.recommendation
            FROM thyroid_medical_details t
            JOIN thyroid_risk r ON t.t_id = r.t_id
            JOIN thyroid_recommendation rec ON r.tr_id = rec.tr_id
            WHERE r.tr_id = %s
        """, [tr_id])
        row = cursor.fetchone()

    if not row:
        return HttpResponse("No data found", status=404)

    logo_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'logo.png')
    static_url = f'file://{logo_path.rsplit("/", 1)[0]}/'

    context = {
        'patient_name': row[0],
        'age': row[1],
        'gender': row[2],
        'tsh': row[3],
        'ft4': row[4],
        'ft3': row[5],
        'risk_status': row[6],
        'recommendation_html': markdown.markdown(row[7] or ""),
        'date': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'STATIC_URL': static_url
    }

    template = get_template("thyroid_report_template.html")
    html = template.render(context)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Thyroid_Report_{context["patient_name"]}.pdf"'

    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse("PDF generation failed", status=500)

    return response


def history_view(request):
    if not request.session.get('user_id'):
        return redirect('login')

    user_id = request.session['user_id']
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')

    filter_applied = from_date and to_date

    if not filter_applied:
        from_date = '2025-01-01'
        to_date_obj = date.today()
        to_date = to_date_obj.strftime('%Y-%m-%d')
    else:
        to_date_obj = date.fromisoformat(to_date)

    history_data = {}

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT t.t_id, t.patient_name, t.age, t.gender, tr.risk_status, t.entry_date
            FROM thyroid_medical_details t
            JOIN thyroid_risk tr ON t.t_id = tr.t_id
            WHERE t.u_id = %s AND t.entry_date BETWEEN %s AND %s
            ORDER BY t.entry_date DESC
        """, [user_id, from_date, to_date])
        history_data['thyroid'] = cursor.fetchall()

        cursor.execute("""
            SELECT l.l_id, l.patient_name, l.age, l.gender, lr.risk_status, l.entry_date
            FROM liver_medical_details l
            JOIN liver_risk lr ON l.l_id = lr.l_id
            WHERE l.u_id = %s AND l.entry_date BETWEEN %s AND %s
            ORDER BY l.entry_date DESC
        """, [user_id, from_date, to_date])
        history_data['liver'] = cursor.fetchall()

        cursor.execute("""
            SELECT h.h_id, h.patient_name, h.age, h.gender, hr.risk_status, h.entry_date
            FROM heart_medical_details h
            JOIN heart_risk hr ON h.h_id = hr.h_id
            WHERE h.u_id = %s AND h.entry_date BETWEEN %s AND %s
            ORDER BY h.entry_date DESC
        """, [user_id, from_date, to_date])
        history_data['heart'] = cursor.fetchall()

        cursor.execute("""
            SELECT d.d_id, d.patient_name, d.age, d.gender, dr.risk_status, d.entry_date
            FROM diabetes_medical_details d
            JOIN diabetes_risk dr ON d.d_id = dr.d_id
            WHERE d.u_id = %s AND d.entry_date BETWEEN %s AND %s
            ORDER BY d.entry_date DESC
        """, [user_id, from_date, to_date])
        history_data['diabetes'] = cursor.fetchall()

    return render(request, 'history.html', {
        'history': history_data,
        'from_date': from_date,
        'to_date': to_date,
        'filter_applied': filter_applied,
        'today': date.today().strftime('%Y-%m-%d') 
    })


def parse_markdown_sections(text):
    sections = [s.strip() for s in text.strip().split("\n\n") if s.strip()]
    return [markdown.markdown(section) for section in sections]

def view_history_detail(request, disease, record_id):
    if not request.session.get('user_id'):
        return redirect('login')

    user_id = request.session['user_id']
    data = None
    recommendations = []

    with connection.cursor() as cursor:
        if disease == 'thyroid':
            report_download_url_name = f"download_{disease}_report"

            cursor.execute("""
                SELECT t.patient_name, t.age, t.gender, t.tsh, t.ft4, t.ft3,
                       tr.risk_status, t.entry_date
                FROM thyroid_medical_details t
                JOIN thyroid_risk tr ON t.t_id = tr.t_id
                WHERE t.u_id = %s AND t.t_id = %s
            """, [user_id, record_id])
            row = cursor.fetchone()

            cursor.execute("""
                SELECT recommendation
                FROM thyroid_recommendation
                WHERE tr_id = (SELECT tr_id FROM thyroid_risk WHERE t_id = %s)
            """, [record_id])
            raw_rec = cursor.fetchone()
            if raw_rec:
                recommendations = parse_markdown_sections(raw_rec[0])

            if row:
                data = {
                    'Disease': 'Thyroid',
                    'Name': row[0],
                    'Age': row[1],
                    'Gender': row[2],
                    'TSH': row[3],
                    'FT4': row[4],
                    'FT3': row[5],
                    'Risk Status': row[6],
                    'Entry Date': row[7],
                }

        elif disease == 'liver':
            report_download_url_name = f"download_{disease}_report"

            cursor.execute("""
                SELECT l.patient_name, l.age, l.gender, l.bilirubin_total, l.bilirubin_direct,
                       l.sgot, l.sgpt, l.alkaline_phosphatase, l.protein, l.albumin,
                       l.ag_ratio, lr.risk_status, l.entry_date
                FROM liver_medical_details l
                JOIN liver_risk lr ON l.l_id = lr.l_id
                WHERE l.u_id = %s AND l.l_id = %s
            """, [user_id, record_id])
            row = cursor.fetchone()

            cursor.execute("""
                SELECT recommendation
                FROM liver_recommendation
                WHERE lr_id = (SELECT lr_id FROM liver_risk WHERE l_id = %s)
            """, [record_id])
            raw_rec = cursor.fetchone()
            if raw_rec:
                recommendations = parse_markdown_sections(raw_rec[0])

            if row:
                data = {
                    'Disease': 'Liver',
                    'Name': row[0],
                    'Age': row[1],
                    'Gender': row[2],
                    'Total Bilirubin': row[3],
                    'Direct Bilirubin': row[4],
                    'SGOT': row[5],
                    'SGPT': row[6],
                    'Alkaline Phosphatase': row[7],
                    'Protein': row[8],
                    'Albumin': row[9],
                    'A/G Ratio': row[10],
                    'Risk Status': row[11],
                    'Entry Date': row[12],
                }

        elif disease == 'heart':
            report_download_url_name = f"download_{disease}_report"

            cursor.execute("""
                SELECT h.patient_name, h.age, h.gender, h.heart_rate, h.cholesterol,
                       h.high_blood_sugar, hr.risk_status, h.entry_date
                FROM heart_medical_details h
                JOIN heart_risk hr ON h.h_id = hr.h_id
                WHERE h.u_id = %s AND h.h_id = %s
            """, [user_id, record_id])
            row = cursor.fetchone()

            cursor.execute("""
                SELECT recommendation
                FROM heart_recommendation
                WHERE hr_id = (SELECT hr_id FROM heart_risk WHERE h_id = %s)
            """, [record_id])
            raw_rec = cursor.fetchone()
            if raw_rec:
                recommendations = parse_markdown_sections(raw_rec[0])

            if row:
                data = {
                    'Disease': 'Heart',
                    'Name': row[0],
                    'Age': row[1],
                    'Gender': row[2],
                    'Heart Rate': row[3],
                    'Cholesterol': row[4],
                    'High Blood Sugar': row[5],
                    'Risk Status': row[6],
                    'Entry Date': row[7],
                }

        elif disease == 'diabetes':
            report_download_url_name = f"download_{disease}_report"
            
            cursor.execute("""
                SELECT d.patient_name, d.age, d.gender, d.hypertension, d.heart_diseases,
                       d.smoking_history, d.bmi, d.hba1c, d.blood_glucose,
                       dr.risk_status, d.entry_date
                FROM diabetes_medical_details d
                JOIN diabetes_risk dr ON d.d_id = dr.d_id
                WHERE d.u_id = %s AND d.d_id = %s
            """, [user_id, record_id])
            row = cursor.fetchone()

            cursor.execute("""
                SELECT recommendation
                FROM diabetes_recommendation
                WHERE dr_id = (SELECT dr_id FROM diabetes_risk WHERE d_id = %s)
            """, [record_id])
            raw_rec = cursor.fetchone()
            if raw_rec:
                recommendations = parse_markdown_sections(raw_rec[0])

            if row:
                data = {
                    'Disease': 'Diabetes',
                    'Name': row[0],
                    'Age': row[1],
                    'Gender': row[2],
                    'Hypertension': row[3],
                    'Heart Diseases': row[4],
                    'Smoking History': row[5],
                    'BMI': row[6],
                    'HbA1c': row[7],
                    'Blood Glucose': row[8],
                    'Risk Status': row[9],
                    'Entry Date': row[10],
                }

    return render(request, 'history_detail.html', {
        'data': data,
        'recommendations': recommendations,
        'record_id': record_id,
        'report_url_name': report_download_url_name
    })