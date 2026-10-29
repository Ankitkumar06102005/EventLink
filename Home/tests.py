from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse


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
        self.assertContains(response, "didn't match", status_code=400)

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
