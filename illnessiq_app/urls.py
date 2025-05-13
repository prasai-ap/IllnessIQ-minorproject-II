from django.urls import path
from. import views
urlpatterns = [
    path('', views.index, name='index'),
    path('aboutus',views.aboutus, name='aboutus'),
    path('login',views.login, name='login'),
    path('signup', views.signup, name='signup'),
    path('verify-otp/', views.verify_otp, name='verify_otp'),
    path('user/',views.user_dashboard, name='user_dashboard'),
    path('admin/',views.admin_dashboard, name='admin_dashboard'),
    path('diabetes-risk/',views.diabetes_risk, name='diabetes_risk'),
    path('heart-risk/',views.heart_risk, name='heart_risk'),
    path('liver-risk/',views.liver_risk,name='liver_risk'),
    path('thyroid-risk/',views.thyroid_risk,name='thyroid_risk'),
    path('logout/',views.logout,name='logout'),
]
