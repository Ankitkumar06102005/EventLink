from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from Home.views import _client_ip


class EventLinkAuthenticationTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_registration_creates_hashed_password_and_logs_user_in(self):
        response = self.client.post(reverse("student_register"), {
            "username": "newstudent",
            "email": "student@example.com",
            "password1": "R3allyStrong!Passphrase",
            "password2": "R3allyStrong!Passphrase",
        })
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username="newstudent")
        self.assertTrue(user.check_password("R3allyStrong!Passphrase"))
        self.assertNotEqual(user.password, "R3allyStrong!Passphrase")
        self.assertIn("_auth_user_id", self.client.session)

    def test_registration_rejects_mismatched_passwords(self):
        response = self.client.post(reverse("student_register"), {
            "username": "newstudent",
            "email": "student@example.com",
            "password1": "R3allyStrong!Passphrase",
            "password2": "Different!Passphrase987",
        })
        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(username="newstudent").exists())

    def test_login_accepts_registered_email(self):
        user = User.objects.create_user(
            username="existingstudent",
            email="student@example.com",
            password="R3allyStrong!Passphrase",
        )
        response = self.client.post(reverse("student_login"), {
            "identifier": "STUDENT@example.com",
            "password": "R3allyStrong!Passphrase",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session["_auth_user_id"], str(user.pk))

    def test_login_rejects_wrong_password_without_server_error(self):
        User.objects.create_user(
            username="existingstudent",
            email="student@example.com",
            password="R3allyStrong!Passphrase",
        )
        response = self.client.post(reverse("student_login"), {
            "identifier": "existingstudent",
            "password": "wrong-password",
        })
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Those credentials", status_code=400)

    def test_login_rate_limit_returns_429_after_ten_posts(self):
        for _ in range(10):
            response = self.client.post(reverse("student_login"), {
                "identifier": "missing-user",
                "password": "wrong-password",
            })
            self.assertEqual(response.status_code, 400)
        response = self.client.post(reverse("student_login"), {
            "identifier": "missing-user",
            "password": "wrong-password",
        })
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response["Retry-After"], "60")

    def test_registration_rate_limit_returns_429_after_five_posts(self):
        for _ in range(5):
            response = self.client.post(reverse("student_register"), {})
            self.assertEqual(response.status_code, 400)
        response = self.client.post(reverse("student_register"), {})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response["Retry-After"], "3600")

    def test_dashboard_requires_authentication(self):
        response = self.client.get(reverse("dashboard"))
        self.assertRedirects(
            response,
            f'{reverse("student_login")}?next={reverse("dashboard")}',
            fetch_redirect_response=False,
        )

    def test_profile_completion_requires_authentication(self):
        response = self.client.get(reverse("complete_profile"))
        self.assertRedirects(
            response,
            f'{reverse("student_login")}?next={reverse("complete_profile")}',
            fetch_redirect_response=False,
        )

    def test_registration_rejects_duplicate_email(self):
        User.objects.create_user(
            username="existingstudent",
            email="student@example.com",
            password="R3allyStrong!Passphrase",
        )
        response = self.client.post(reverse("student_register"), {
            "username": "anotherstudent",
            "email": "STUDENT@example.com",
            "password1": "R3allyStrong!Passphrase",
            "password2": "R3allyStrong!Passphrase",
        })
        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(username="anotherstudent").exists())

    def test_login_preserves_safe_next_url(self):
        User.objects.create_user(
            username="existingstudent",
            email="student@example.com",
            password="R3allyStrong!Passphrase",
        )
        response = self.client.post(reverse("student_login"), {
            "identifier": "existingstudent",
            "password": "R3allyStrong!Passphrase",
            "next": reverse("complete_profile"),
        })
        self.assertRedirects(response, reverse("complete_profile"), fetch_redirect_response=False)

    def test_login_rejects_external_next_url(self):
        User.objects.create_user(
            username="existingstudent",
            email="student@example.com",
            password="R3allyStrong!Passphrase",
        )
        response = self.client.post(reverse("student_login"), {
            "identifier": "existingstudent",
            "password": "R3allyStrong!Passphrase",
            "next": "https://evil.example/steal",
        })
        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)

    def test_password_similar_to_username_is_rejected(self):
        username = "VeryStrongStudentName"
        response = self.client.post(reverse("student_register"), {
            "username": username,
            "email": "different.person@example.com",
            "password1": "VeryStrongStudentName!123",
            "password2": "VeryStrongStudentName!123",
        })
        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(username=username).exists())

    def test_duplicate_username_and_email_share_generic_message(self):
        User.objects.create_user(
            username="existingstudent",
            email="student@example.com",
            password="R3allyStrong!Passphrase",
        )
        response = self.client.post(reverse("student_register"), {
            "username": "existingstudent",
            "email": "new@example.com",
            "password1": "R3allyStrong!Passphrase",
            "password2": "R3allyStrong!Passphrase",
        })
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "That username or email is already in use.", status_code=400)
        self.assertNotContains(response, "That username is already in use.", status_code=400)

    def test_account_throttle_counts_username_and_email_aliases_across_ips(self):
        user = User.objects.create_user(
            username="existingstudent",
            email="student@example.com",
            password="R3allyStrong!Passphrase",
        )
        for attempt in range(10):
            identifier = "student@example.com" if attempt % 2 else "existingstudent"
            response = self.client.post(
                reverse("student_login"),
                {"identifier": identifier, "password": "wrong-password"},
                REMOTE_ADDR=f"203.0.113.{attempt + 1}",
            )
            self.assertEqual(response.status_code, 400)
        response = self.client.post(
            reverse("student_login"),
            {"identifier": "STUDENT@example.com", "password": "wrong-password"},
            REMOTE_ADDR="203.0.113.50",
        )
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response["Retry-After"], "60")
        # A valid password is never blocked by the failed-attempt throttle.
        response = self.client.post(
            reverse("student_login"),
            {"identifier": "existingstudent", "password": "R3allyStrong!Passphrase"},
            REMOTE_ADDR="203.0.113.51",
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session["_auth_user_id"], str(user.pk))

    def test_profile_can_be_updated_without_integrity_error(self):
        user = User.objects.create_user(
            username="profileuser",
            email="profile@example.com",
            password="R3allyStrong!Passphrase",
        )
        self.client.force_login(user)
        payload = {
            "full_name": "First Name",
            "class_name": "CSAI",
            "section": "A",
            "net_number": "NET123",
            "about_you": "I enjoy building useful software.",
            "virtues": [],
        }
        first = self.client.post(reverse("complete_profile"), payload)
        self.assertRedirects(first, reverse("dashboard"), fetch_redirect_response=False)
        payload["full_name"] = "Updated Name"
        second = self.client.post(reverse("complete_profile"), payload)
        self.assertRedirects(second, reverse("dashboard"), fetch_redirect_response=False)
        from Home.models import Profile
        profile = Profile.objects.get(user=user)
        self.assertEqual(profile.full_name, "Updated Name")
        self.assertEqual(Profile.objects.filter(user=user).count(), 1)


    @override_settings(TRUSTED_PROXY_HOPS=1)
    def test_client_ip_uses_configured_proxy_header(self):
        request = RequestFactory().post(
            "/student_login",
            REMOTE_ADDR="192.0.2.10",
            HTTP_X_FORWARDED_FOR="203.0.113.20",
        )
        self.assertEqual(_client_ip(request), "203.0.113.20")
