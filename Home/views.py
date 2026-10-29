from functools import wraps
import hashlib
import ipaddress

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import ProfileForm
from .models import Profile


def _client_ip(request):
    """Resolve a client IP only when the deployment explicitly trusts proxy hops."""
    peer = request.META.get("REMOTE_ADDR", "unknown")
    try:
        peer = str(ipaddress.ip_address(peer))
    except ValueError:
        return "unknown"

    trusted_hops = max(0, int(getattr(settings, "TRUSTED_PROXY_HOPS", 0)))
    if not trusted_hops:
        return peer

    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    candidates = []
    for value in forwarded.split(","):
        value = value.strip()
        if not value:
            continue
        try:
            candidates.append(str(ipaddress.ip_address(value)))
        except ValueError:
            # Ignore malformed forwarded values; never use them as cache keys.
            continue

    # The immediate peer is trusted by configuration. Walk left past the
    # configured proxy hops; the remaining rightmost address is the client.
    chain = candidates + [peer]
    index = len(chain) - trusted_hops - 1
    return chain[index] if 0 <= index < len(chain) else peer


def _rate_key(*parts):
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:32]
    return f"eventlink:rate:{digest}"


def _increment_counter(key, window):
    """Atomically-ish increment a short-lived cache counter."""
    if cache.add(key, 1, timeout=window):
        return 1
    try:
        return cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=window)
        return 1


def rate_limit(scope, limit, window):
    """Cache-backed per-client throttle for authentication POST requests."""
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if request.method == "POST":
                ip = _client_ip(request)
                attempts = _increment_counter(_rate_key(scope, ip), window)
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
    next_url = request.POST.get("next") or request.GET.get("next") or ""
    safe_next = next_url if url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ) else ""

    if request.method == "POST":
        identifier = (request.POST.get("identifier") or "").strip()
        password = request.POST.get("password") or ""

        if not identifier or not password:
            return render(request, "student_login.html", {
                "error_msg": "Enter your email/username and password.",
                "next_url": safe_next,
            }, status=400)

        user_record = None
        if "@" in identifier:
            user_record = User.objects.filter(email__iexact=identifier).first()
        if user_record is None:
            user_record = User.objects.filter(username__iexact=identifier).first()

        canonical_identity = user_record.username.lower() if user_record else identifier.casefold()
        ip = _client_ip(request)
        account_key = _rate_key("login-account", canonical_identity)
        account_attempts = cache.get(account_key, 0)

        username = user_record.username if user_record else identifier
        user = authenticate(request, username=username, password=password)

        if user is not None:
            # Never lock a legitimate user out because an attacker guessed their
            # identifier. Correct credentials are accepted even after failures.
            cache.delete(account_key)
            login(request, user)
            return redirect(safe_next or "dashboard")

        failed_attempts = _increment_counter(account_key, 60)
        # A canonical identity bucket follows username/email aliases across IPs.
        # It throttles failed attempts only; valid credentials above still work.
        if account_attempts >= 10 or failed_attempts > 10:
            response = render(request, "student_login.html", {
                "error_msg": "Too many unsuccessful attempts for these credentials. Try again shortly.",
                "next_url": safe_next,
            }, status=429)
            response["Retry-After"] = "60"
            return response

        return render(request, "student_login.html", {
            "error_msg": "Those credentials didn't match an account. Please try again.",
            "next_url": safe_next,
        }, status=400)

    return render(request, "student_login.html", {"next_url": safe_next})


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

    if (
        User.objects.filter(username__iexact=username).exists()
        or User.objects.filter(email__iexact=email).exclude(email="").exists()
    ):
        return render(request, "student_register.html", {
            "error_msg": "That username or email is already in use."
        }, status=400)

    candidate_user = User(username=username, email=email)
    try:
        validate_password(password1, user=candidate_user)
    except ValidationError as exc:
        return render(request, "student_register.html", {
            "error_msg": " ".join(exc.messages)
        }, status=400)

    try:
        user = User.objects.create_user(username=username, email=email, password=password1)
    except IntegrityError:
        return render(request, "student_register.html", {
            "error_msg": "That username or email is already in use."
        }, status=400)

    login(request, user)
    messages.success(request, "Your EventLink account is ready.")
    return redirect("dashboard")


@login_required(login_url="student_login")
def student_form(request):
    return render(request, "student_form.html")


@login_required(login_url="student_login")
def dashboard(request):
    return render(request, "dashboard.html")


@login_required(login_url="student_login")
def profile(request):
    return HttpResponse("this is profile")


def find_teammates(request):
    return render(request, "home.html")


def create_team(request):
    return redirect("find_teammates")


@login_required(login_url="student_login")
def complete_profile(request):
    existing_profile = Profile.objects.filter(user=request.user).first()
    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=existing_profile)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.user = request.user
            try:
                profile.save()
            except IntegrityError:
                # A parallel first submission may have created the one-to-one row.
                existing_profile = Profile.objects.filter(user=request.user).first()
                if existing_profile is None:
                    raise
                form = ProfileForm(request.POST, request.FILES, instance=existing_profile)
                if not form.is_valid():
                    return render(request, "complete_profile.html", {"form": form})
                profile = form.save(commit=False)
                profile.user = request.user
                profile.save()
            form.save_m2m()
            messages.success(request, "Your profile has been saved.")
            return redirect("dashboard")
    else:
        form = ProfileForm(instance=existing_profile)
    return render(request, "complete_profile.html", {"form": form})
