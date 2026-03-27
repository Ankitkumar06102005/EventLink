from django.urls import path
from Home import views

urlpatterns = [
    path('', views.index, name='index'),
    path('home/', views.home, name='home'),
    path('logout/', views.logoutUser, name='logout'),

    # Student auth
    path('login/', views.student_login, name='student_login'),
    path('register/', views.student_register, name='student_register'),

    # College auth
    path('college-login/', views.college_login, name='college_login'),
    path('college-register/', views.college_register, name='college_register'),

    # Student pages
    path('dashboard/', views.dashboard, name='dashboard'),
    path('complete-profile/', views.complete_profile, name='complete_profile'),
    path('find-teammates/', views.find_teammates, name='find_teammates'),
    path('create-team/', views.create_team, name='create_team'),
    path('events/', views.events, name='events'),
    path('events/<int:event_id>/', views.event_detail, name='event_detail'),
    path('events/<int:event_id>/apply/', views.apply_event, name='apply_event'),

    # College pages
    path('college/dashboard/', views.college_dashboard, name='college_dashboard'),
    path('college/create-event/', views.create_event, name='create_event'),
    path('college/approve/<int:reg_id>/', views.approve_team, name='approve_team'),
    path('college/reject/<int:reg_id>/', views.reject_team, name='reject_team'),

    # Misc
    path('profile/', views.profile, name='profile'),
    path('teams/', views.find_teammates, name='teams'),
    path('student-form/', views.student_form, name='student_form'),
]
