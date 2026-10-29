from django.urls import path
from Home import views
urlpatterns = [
    path('', views.index, name='index'),
    path('logout', views.logoutUser, name='logout'),
    path('home/', views.home, name='home'),
    path('teams', views.teams, name='teams'),
    path('events', views.events, name='events'),
    path('student_login', views.student_login, name='student_login'),
    path('college_login', views.college_login, name='college_login'),
    path('student_register', views.student_register, name='student_register'),
    path('college_register', views.college_register, name='college_register'),
    path('student_form/', views.student_form, name='student_form'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile', views.profile, name='profile'),
    path('find_teammates', views.find_teammates, name='find_teammates'),
    path('create_team', views.find_teammates, name='create_team'),
    path('complete-profile/', views.complete_profile, name='complete_profile'),

]
