from django.shortcuts import render,redirect
from django.db import connection ,IntegrityError
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
import random ,datetime
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


diabetes_model = os.path.join(settings.BASE_DIR, 'illnessiq_app', 'ml_models', 'diabetes_model.pkl')
heart_model = os.path.join(settings.BASE_DIR, 'illnessiq_app', 'ml_models', 'heart_model.pkl')
liver_model = os.path.join(settings.BASE_DIR, 'illnessiq_app', 'ml_models', 'liver_model.pkl')

gender_map = {'Male': 1, 'Female': 0}
hypertension_map = {'Yes': 1, 'No': 0}
heart_disease_map = {'Yes': 1, 'No': 0}
smoking_map = {'Never': 0, 'Former': 1, 'Current': 2}

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
        try:
            age = int(request.POST.get('Age'))
            gender = request.POST.get('Gender')
            hypertension = request.POST.get('Hypertension')
            heart_disease = request.POST.get('Heart_Disease')
            smoking_status = request.POST.get('Smoking_Status')
            bmi = float(request.POST.get('BMI'))
            hba1c = float(request.POST.get('HbA1c_Level'))
            glucose = float(request.POST.get('Blood_Glucose_Level'))
            patient_name = request.POST.get('Patient_Name')

            model_features = [
                'gender', 'age', 'hypertension', 'heart_disease',
                'smoking_history', 'bmi', 'HbA1c_level', 'blood_glucose_level'
            ]

            input_values = {
                'age': age,
                'gender': gender_map.get(gender),
                'hypertension': hypertension_map.get(hypertension),
                'heart_disease': heart_disease_map.get(heart_disease),
                'smoking_history': smoking_map.get(smoking_status),
                'bmi': bmi,
                'HbA1c_level': hba1c,
                'blood_glucose_level': glucose
            }

            input_data = pd.DataFrame([input_values], columns=model_features)
            prediction = model.predict(input_data)[0]
            result = "High Risk" if prediction == 1 else "Low Risk"

            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO diabetes_medical_details 
                    (u_id, patient_name, age, gender, hypertension, heart_diseases, smoking_history, bmi, hba1c, blood_glucose)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING d_id
                """, [
                    user, patient_name, age, gender, hypertension, heart_disease,
                    smoking_status, bmi, hba1c, glucose
                ])
                d_id = cursor.fetchone()[0]

                cursor.execute("""
                    INSERT INTO diabetes_risk (risk_status, d_id)
                    VALUES (%s, %s) RETURNING dr_id
                """, [result, d_id])
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
                cursor.execute("""
                    INSERT INTO diabetes_recommendation (dr_id, recommendation)
                    VALUES (%s, %s) RETURNING dre_id
                """, [dr_id, recommendation_text])
                dre_id = cursor.fetchone()[0]

            return render(request, 'diabetes_risk_result.html', {
                'result': result,
                'recommendations': recommendations,
                'dr_id': dr_id
            })

        except ValueError as ve:
            return render(request, 'diabetes_risk_result.html', {
                'result': f"Error: Invalid input data. Please ensure all fields are correctly filled. Details: {str(ve)}",
                'recommendations': ["<p>Please check your input values and try again.</p>"]
            })
        except Exception as e:
            return render(request, 'diabetes_risk_result.html', {
                'result': f"An unexpected error occurred during prediction: {str(e)}",
                'recommendations': ["<p>An unexpected issue occurred. Please try again later or contact support.</p>"]
            })


def predict_heart(request):
    if not request.session.get('user_id'):
        return redirect('login')

    try:
        model = joblib.load(heart_model)
    except FileNotFoundError:
        return render(request, 'heart_risk_result.html', {
            'result': "Error: Heart model not found.",
            'recommendations': ["<p>Please contact support to resolve the system configuration issue.</p>"]
        })
    except Exception as e:
        return render(request, 'heart_risk_result.html', {
            'result': f"Error loading model: {str(e)}",
            'recommendations': ["<p>An unexpected error occurred. Please contact support.</p>"]
        })

    user_id = request.session.get('user_id')

    if request.method == 'POST':
        try:
            patient_name = request.POST.get('Patient_Name')
            age = int(request.POST.get('Age'))
            gender = request.POST.get('Gender')
            cholesterol = float(request.POST.get('Cholesterol'))
            fasting_blood_sugar = request.POST.get('Fasting_Blood_Sugar')
            heart_rate = int(request.POST.get('Heart_Rate'))

            gender_encoded = 1 if gender.lower() == 'male' else 0
            fbs_encoded = 1 if fasting_blood_sugar.lower() == 'yes' else 0

            input_data = pd.DataFrame([{
                'age': age,
                'gender': gender_encoded,
                'chol': cholesterol,
                'fbs': fbs_encoded,
                'thalach': heart_rate
            }])

            prediction = model.predict(input_data)[0]
            result = "High Risk" if prediction == 1 else "Low Risk"

            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO heart_medical_details 
                    (u_id, patient_name, age, gender, cholesterol, high_blood_sugar, heart_rate)
                    VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING h_id
                """, [user_id, patient_name, age, gender, cholesterol, fasting_blood_sugar, heart_rate])
                h_id = cursor.fetchone()[0]

                cursor.execute("""
                    INSERT INTO heart_risk (risk_status, h_id)
                    VALUES (%s, %s) RETURNING hr_id
                """, [result, h_id])
                hr_id = cursor.fetchone()[0]

            prompt = f"""Based on the following user data, provide personalized health recommendations for heart disease risk management.
            The user is a {gender.lower()} aged {age} with a {result} of heart disease.
            Key metrics: cholesterol = {cholesterol}, high fasting blood sugar = {fasting_blood_sugar}, heart rate = {heart_rate}.

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
                cursor.execute("""
                    INSERT INTO heart_recommendation (hr_id, recommendation)
                    VALUES (%s, %s)
                """, [hr_id, recommendation_text])

            return render(request, 'heart_risk_result.html', {
                'result': result,
                'recommendations': recommendations,
                'hr_id': hr_id
            })

        except ValueError as ve:
            return render(request, 'heart_risk_result.html', {
                'result': f"Input Error: {str(ve)}",
                'recommendations': ["<p>Please check the values and ensure all fields are filled correctly.</p>"]
            })
        except Exception as e:
            return render(request, 'heart_risk_result.html', {
                'result': f"An unexpected error occurred: {str(e)}",
                'recommendations': ["<p>Please try again later or contact technical support.</p>"]
            })

def predict_liver(request):
    if not request.session.get('user_id'):
        return redirect('login')

    try:
        model = joblib.load(liver_model)
    except FileNotFoundError:
        return render(request, 'liver_risk_result.html', {
            'result': "Error: Liver model not found.",
            'recommendations': ["<p>Please contact support to resolve the system configuration issue.</p>"]
        })
    except Exception as e:
        return render(request, 'liver_risk_result.html', {
            'result': f"Error loading model: {str(e)}",
            'recommendations': ["<p>An unexpected error occurred. Please contact support.</p>"]
        })

    user_id = request.session.get('user_id')

    if request.method == 'POST':
        try:
            patient_name = request.POST.get('Patient_Name')
            age = int(request.POST.get('Age'))
            gender = request.POST.get('Gender')
            tb = float(request.POST.get('Total_Bilirubin'))
            db = float(request.POST.get('Direct_Bilirubin'))
            sgot = float(request.POST.get('SGOT'))
            sgpt = float(request.POST.get('SGPT'))
            alkp = float(request.POST.get('Alkaline_Phosphatase'))
            protein = float(request.POST.get('Total_Protein'))
            albumin = float(request.POST.get('Albumin'))
            ag_ratio = float(request.POST.get('A_G_Ratio'))

    
            gender_encoded = 1 if gender.lower() == 'male' else 0

            model_features = [ 'Age ','Gender','Total_Bilirubin','Direct_Bilirubin',
                'Alkaline_Phosphatase', 'Sgpt', 'Sgot ', 'Total_Proteins', ' Albumin', 'A_G_Ratio'
                
            ]

            input_values = {
                'Age': age,
                'Gender': gender_encoded,
                'Total_Bilirubin': tb,
                'Direct_Bilirubin': db,
                'Alkaline_Phosphatase': alkp,
                'Sgpt': sgpt,
                'Sgot': sgot,
                'Total_Proteins': protein,
                'Albumin': albumin,
                'A_G_Ratio': ag_ratio 
            }

            input_data = pd.DataFrame([input_values], columns=model_features)
            
            prediction = model.predict(input_data)[0]
            result = "High Risk" if prediction == 1 else "Low Risk"

            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO liver_medical_details 
                    (u_id, patient_name, age, gender, bilirubin_total, bilirubin_direct, sgot, sgpt, alkaline_phosphatase, protein, albumin, ag_ratio)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING l_id
                """, [
                    user_id, patient_name, age, gender, tb, db, sgot, sgpt, alkp, protein, albumin, ag_ratio
                ])
                l_id = cursor.fetchone()[0]

                cursor.execute("""
                    INSERT INTO liver_risk (risk_status, l_id)
                    VALUES (%s, %s) RETURNING lr_id
                """, [result, l_id])
                lr_id = cursor.fetchone()[0]

            prompt = f"""Based on the following user data, provide personalized health recommendations for liver health management.
            The user is a {gender.lower()} aged {age} with a {result} of liver disease.
            Key metrics: Total Bilirubin = {tb}, Direct Bilirubin = {db}, SGOT = {sgot}, SGPT = {sgpt}, ALP = {alkp}, Protein = {protein}, Albumin = {albumin}, A/G Ratio = {ag_ratio}.

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
                cursor.execute("""
                    INSERT INTO liver_recommendation (lr_id, recommendation)
                    VALUES (%s, %s)
                """, [lr_id, recommendation_text])

            return render(request, 'liver_risk_result.html', {
                'result': result,
                'recommendations': recommendations,
                'lr_id': lr_id
            })

        except ValueError as ve:
            return render(request, 'liver_risk_result.html', {
                'result': f"Input Error: {str(ve)}",
                'recommendations': ["<p>Please check the values and ensure all fields are filled correctly.</p>"]
            })
        except Exception as e:
            return render(request, 'liver_risk_result.html', {
                'result': f"An unexpected error occurred: {str(e)}",
                'recommendations': ["<p>Please try again later or contact technical support.</p>"]
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
