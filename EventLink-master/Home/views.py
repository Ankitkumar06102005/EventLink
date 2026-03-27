from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import IntegrityError
from .forms import ProfileForm, EventForm
from .models import Profile, Team, Event, EventRegistration


# ─── Public ───────────────────────────────────────────────────────────────────

def index(request):
    event_cards = [
        {"title": "CodeMaster Challenge", "college": "IIT Bombay", "description": "A 48-hour coding marathon featuring real-world problems.", "tags": "Coding,Hackathon", "tag_list": ["Coding", "Hackathon"]},
        {"title": "DesignSphere 2025", "college": "NID Ahmedabad", "description": "Creative jam session focusing on UX/UI innovation.", "tags": "Design,Creativity", "tag_list": ["Design", "Creativity"]},
        {"title": "HackHub", "college": "VIT Vellore", "description": "A national-level hackathon on AI and sustainability.", "tags": "Hackathon,AI", "tag_list": ["Hackathon", "AI"]},
        {"title": "Startup Grind Fest", "college": "BITS Goa", "description": "Pitch, network, and grow your startup with mentors.", "tags": "Startup,Business", "tag_list": ["Startup", "Business"]},
        {"title": "AI in Healthcare", "college": "AIIMS Delhi", "description": "Exploring the future of medicine powered by AI.", "tags": "AI,Healthcare", "tag_list": ["AI", "Healthcare"]},
        {"title": "WebCraft Workshop", "college": "IIIT Bangalore", "description": "Masterclass in web technologies: React, Tailwind, and more.", "tags": "Design,Hackathon", "tag_list": ["Design", "Hackathon"]},
    ]
    return render(request, "home.html", {"event_cards": event_cards})


def home(request):
    return redirect("index")


def logoutUser(request):
    logout(request)
    return redirect("index")


# ─── Auth ─────────────────────────────────────────────────────────────────────

def student_login(request):
    # Already logged in → redirect away
    if request.user.is_authenticated:
        return redirect("college_dashboard" if request.user.profile.role == "college" else "dashboard")
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        if not username or not password:
            messages.error(request, "Please fill in all fields")
            return render(request, "student_login.html")
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect("college_dashboard" if user.profile.role == "college" else "dashboard")
        messages.error(request, "Invalid username or password")
    return render(request, "student_login.html")


def student_register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    if request.method == 'POST':
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password1 = request.POST.get("password1", "")
        password2 = request.POST.get("password2", "")
        if not username or not password1:
            messages.error(request, "Username and password are required")
            return render(request, "student_register.html")
        if password1 != password2:
            messages.error(request, "Passwords do not match")
            return render(request, "student_register.html")
        if len(password1) < 6:
            messages.error(request, "Password must be at least 6 characters")
            return render(request, "student_register.html")
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already taken")
            return render(request, "student_register.html")
        user = User.objects.create_user(username=username, email=email, password=password1)
        login(request, user)
        return redirect('complete_profile')
    return render(request, "student_register.html")


def college_login(request):
    if request.user.is_authenticated:
        return redirect("college_dashboard")
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        if not username or not password:
            messages.error(request, "Please fill in all fields")
            return render(request, "college_login.html")
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect("college_dashboard")
        messages.error(request, "Invalid credentials")
    return render(request, "college_login.html")


def college_register(request):
    if request.user.is_authenticated:
        return redirect("college_dashboard")
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password1 = request.POST.get("password1", "")
        password2 = request.POST.get("password2", "")
        college_name = request.POST.get("college_name", "").strip()
        if not college_name or not username or not password1:
            messages.error(request, "All fields are required")
            return render(request, "college_register.html")
        if password1 != password2:
            messages.error(request, "Passwords do not match")
            return render(request, "college_register.html")
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already taken")
            return render(request, "college_register.html")
        user = User.objects.create_user(username=username, email=email, password=password1)
        user.profile.role = "college"
        user.profile.full_name = college_name
        user.profile.save()
        login(request, user)
        return redirect("college_dashboard")
    return render(request, "college_register.html")


# ─── Student ──────────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    # College users shouldn't land here
    if request.user.profile.role == 'college':
        return redirect('college_dashboard')
    profile = request.user.profile
    teams = request.user.teams.all()
    my_team = Team.objects.filter(leader=request.user).first()
    registrations = (
        EventRegistration.objects
        .filter(team=my_team)
        .select_related('event')
        .order_by('-submitted_at')
    ) if my_team else []
    events_count = Event.objects.count()
    return render(request, "dashboard.html", {
        "profile": profile,
        "teams": teams,
        "my_team": my_team,
        "registrations": registrations,
        "events_count": events_count,
    })


@login_required
def complete_profile(request):
    profile = request.user.profile
    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile saved!")
            return redirect('dashboard')
    else:
        form = ProfileForm(instance=profile)
    return render(request, 'complete_profile.html', {'form': form})


@login_required
def find_teammates(request):
    query = request.GET.get('q', '').strip()
    virtue_filter = request.GET.get('virtue', '').strip()
    profiles = Profile.objects.exclude(user=request.user).filter(role='student')
    if query:
        profiles = profiles.filter(full_name__icontains=query)
    if virtue_filter:
        profiles = profiles.filter(virtues__name__icontains=virtue_filter)
    all_virtues = sorted(set(
        v for v in Profile.objects.values_list('virtues__name', flat=True) if v
    ))
    return render(request, "find_teammates.html", {
        "profiles": profiles,
        "query": query,
        "virtue_filter": virtue_filter,
        "all_virtues": all_virtues,
    })


@login_required
def create_team(request):
    # College accounts can't create teams
    if request.user.profile.role == 'college':
        return redirect('college_dashboard')
    if request.method == "POST":
        name = request.POST.get("team_name", "").strip()
        if not name:
            messages.error(request, "Team name cannot be empty")
            return render(request, "create_team.html")
        try:
            team = Team.objects.create(name=name, leader=request.user)
            team.members.add(request.user)
            messages.success(request, f'Team "{name}" created!')
            return redirect("dashboard")
        except IntegrityError:
            messages.error(request, "Something went wrong, try again")
    return render(request, "create_team.html")


@login_required
def events(request):
    all_events = Event.objects.all().order_by('-date')
    my_team = Team.objects.filter(leader=request.user).first()
    applied_event_ids = set(
        EventRegistration.objects.filter(team=my_team).values_list('event_id', flat=True)
    ) if my_team else set()
    return render(request, "events.html", {
        "events": all_events,
        "my_team": my_team,
        "applied_event_ids": applied_event_ids,
    })


@login_required
def apply_event(request, event_id):
    # Only POST allowed — prevents re-apply on browser refresh
    if request.method != "POST":
        return redirect("events")
    event = get_object_or_404(Event, id=event_id)
    my_team = Team.objects.filter(leader=request.user).first()
    if not my_team:
        messages.error(request, "You need to create a team before applying.")
        return redirect("create_team")
    # Prevent applying to own college's event
    if event.created_by == request.user:
        messages.error(request, "You can't apply to your own event.")
        return redirect("events")
    _, created = EventRegistration.objects.get_or_create(team=my_team, event=event)
    if created:
        messages.success(request, f'Applied to "{event.title}" — waiting for approval.')
    else:
        messages.info(request, "Your team has already applied to this event.")
    return redirect("events")


@login_required
def event_detail(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    registrations = (
        event.registrations
        .select_related('team', 'team__leader')
        .prefetch_related('team__members')
        .order_by('-submitted_at')
    )
    my_team = Team.objects.filter(leader=request.user).first()
    my_reg = registrations.filter(team=my_team).first() if my_team else None
    return render(request, "event_detail.html", {
        "event": event,
        "registrations": registrations,
        "my_reg": my_reg,
        "is_owner": event.created_by == request.user,
    })


# ─── College ──────────────────────────────────────────────────────────────────

@login_required
def college_dashboard(request):
    if request.user.profile.role != 'college':
        return redirect('dashboard')
    my_events = Event.objects.filter(created_by=request.user).order_by('-date')
    registrations = (
        EventRegistration.objects
        .filter(event__in=my_events)
        .select_related('team', 'team__leader', 'event')
        .prefetch_related('team__members')
        .order_by('-submitted_at')
    )
    pending = registrations.filter(status='pending')
    approved = registrations.filter(status='approved')
    rejected = registrations.filter(status='rejected')
    total_participants = sum(r.team.members.count() for r in approved)
    return render(request, "college_dashboard.html", {
        "my_events": my_events,
        "registrations": registrations,
        "pending": pending,
        "approved": approved,
        "rejected": rejected,
        "total_participants": total_participants,
    })


@login_required
def create_event(request):
    if request.user.profile.role != 'college':
        return redirect('dashboard')
    if request.method == "POST":
        form = EventForm(request.POST)
        if form.is_valid():
            event = form.save(commit=False)
            event.created_by = request.user
            event.save()
            messages.success(request, f'Event "{event.title}" published!')
            return redirect("college_dashboard")
    else:
        form = EventForm()
    return render(request, "create_event.html", {"form": form})


@login_required
def approve_team(request, reg_id):
    if request.method != "POST":
        return redirect("college_dashboard")
    # ownership enforced — 404 if not their event
    reg = get_object_or_404(EventRegistration, id=reg_id, event__created_by=request.user)
    if reg.status == 'approved':
        messages.info(request, "Already approved.")
        return redirect("college_dashboard")
    reg.status = "approved"
    reg.save()
    messages.success(request, f'"{reg.team.name}" approved for {reg.event.title}.')
    return redirect("college_dashboard")


@login_required
def reject_team(request, reg_id):
    if request.method != "POST":
        return redirect("college_dashboard")
    reg = get_object_or_404(EventRegistration, id=reg_id, event__created_by=request.user)
    if reg.status == 'rejected':
        messages.info(request, "Already rejected.")
        return redirect("college_dashboard")
    reg.status = "rejected"
    reg.save()
    messages.info(request, f'"{reg.team.name}" rejected.')
    return redirect("college_dashboard")


# ─── Misc ─────────────────────────────────────────────────────────────────────

def profile(request):
    return redirect("dashboard")

def student_form(request):
    return render(request, "student_form.html")
