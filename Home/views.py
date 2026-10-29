from functools import wraps
import hashlib

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError
from django.http import HttpResponse
from django.shortcuts import redirect, render

from .forms import ProfileForm


def rate_limit(scope, limit, window):
    """Small cache-backed per-IP throttle for authentication POST requests."""
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if request.method == "POST":
                # Use the direct peer address; do not trust client-supplied X-Forwarded-For.
                ip = request.META.get("REMOTE_ADDR", "unknown")
                digest = hashlib.sha256(ip.encode("utf-8")).hexdigest()[:24]
                key = f"eventlink:rate:{scope}:{digest}"
                if cache.add(key, 1, timeout=window):
                    attempts = 1
                else:
                    try:
                        attempts = cache.incr(key)
                    except ValueError:
                        cache.set(key, 1, timeout=window)
                        attempts = 1
                if attempts > limit:
                    response = HttpResponse(
                        "Too many attempts. Please wait a little and try again.",
                        status=429,
                        content_type="text/plain; charset=utf-8",
                    )
                    response["Retry-After"] = str(window)
                    return response
            return view(request, *args, **kwargs)
        return wrapped
    return decorator


def index(request):
    return render(request, "home.html")


def register(request):
    return redirect("student_register")


def logoutUser(request):
    if request.method == "POST":
        logout(request)
    return redirect("index")


def home(request):
    return redirect("index")


def teams(request):
    return render(request, "home.html")


def events(request):
    return render(request, "home.html")


@rate_limit("login", limit=10, window=60)
def student_login(request):
    if request.method == "POST":
        identifier = (request.POST.get("identifier") or "").strip()
        password = request.POST.get("password") or ""

        if not identifier or not password:
            return render(request, "student_login.html", {
                "error_msg": "Enter your email/username and password."
            }, status=400)

        username = identifier
        if "@" in identifier:
            user_record = User.objects.filter(email__iexact=identifier).only("username").first()
            username = user_record.username if user_record else ""

        user = authenticate(request, username=username, password=password) if username else None
        if user is not None:
            login(request, user)
            return redirect("dashboard")

        return render(request, "student_login.html", {
            "error_msg": "Those credentials didn't match an account. Please try again."
        }, status=400)

    return render(request, "student_login.html")


def college_login(request):
    return redirect("student_login")


def college_register(request):
    return redirect("student_register")


@rate_limit("register", limit=5, window=3600)
def student_register(request):
    if request.method != "POST":
        return render(request, "student_register.html")

    username = (request.POST.get("username") or "").strip()
    email = (request.POST.get("email") or "").strip().lower()
    password1 = request.POST.get("password1") or ""
    password2 = request.POST.get("password2") or ""

    if not username or not email or not password1 or not password2:
        return render(request, "student_register.html", {
            "error_msg": "Complete every field to create your account."
        }, status=400)

    if len(username) > 150 or len(email) > 254:
        return render(request, "student_register.html", {
            "error_msg": "Your username or email is too long."
        }, status=400)

    try:
        validate_email(email)
    except ValidationError:
        return render(request, "student_register.html", {
            "error_msg": "Enter a valid email address."
        }, status=400)

    if password1 != password2:
        return render(request, "student_register.html", {
            "error_msg": "The passwords do not match."
        }, status=400)

    if User.objects.filter(username__iexact=username).exists():
        return render(request, "student_register.html", {
            "error_msg": "That username is already in use. Choose another."
        }, status=400)

    if User.objects.filter(email__iexact=email).exclude(email="").exists():
        return render(request, "student_register.html", {
            "error_msg": "An account with that email already exists. Log in instead."
        }, status=400)

    try:
        validate_password(password1)
    except ValidationError as exc:
        return render(request, "student_register.html", {
            "error_msg": " ".join(exc.messages)
        }, status=400)

    try:
        user = User.objects.create_user(username=username, email=email, password=password1)
    except IntegrityError:
        return render(request, "student_register.html", {
            "error_msg": "We couldn't create that account. Check your details and try again."
        }, status=400)

    login(request, user)
    messages.success(request, "Your EventLink account is ready.")
    return redirect("dashboard")


def student_form(request):
    return render(request, "student_form.html")


def dashboard(request):
    return render(request, "dashboard.html")


def profile(request):
    return HttpResponse("this is profile")


def find_teammates(request):
    return render(request, "home.html")


def create_team(request):
    return redirect("find_teammates")


def complete_profile(request):
    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.user = request.user
            profile.save()
            form.save_m2m()
            return redirect("dashboard")
    else:
        form = ProfileForm()
    return render(request, "complete_profile.html", {"form": form})
