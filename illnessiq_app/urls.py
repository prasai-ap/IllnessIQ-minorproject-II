from django.urls import path
from. import views
urlpatterns = [
    path('', views.index, name='index'),
    path('aboutus',views.aboutus, name='aboutus'),
    path('login',views.login, name='login'),
    path('signup', views.signup, name='signup'),
    path('verify-otp/', views.verify_otp, name='verify_otp'),
    path('user/',views.user_dashboard, name='user_dahsboard')
    path('admin/',views.admin_dashboard, name='admin_dahsboard')
]
