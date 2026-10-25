
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class CustomerRegistrationTests(TestCase):
    def setUp(self):
        self.url = reverse("register")
        self.password = "A-Strong-Test-Pass-938!"

    def register_customer(self, **overrides):
        data = {
            "username": "newcustomer",
            "email": "newcustomer@example.com",
            "password1": self.password,
            "password2": self.password,
        }
        data.update(overrides)
        return self.client.post(self.url, data)

    def test_registration_page_loads(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Create your account")

    def test_successful_registration(self):
        response = self.register_customer()

        self.assertRedirects(
            response,
            reverse("register_success"),
        )
        self.assertTrue(
            User.objects.filter(username="newcustomer").exists()
        )

    def test_password_is_hashed(self):
        self.register_customer()

        user = User.objects.get(username="newcustomer")

        self.assertNotEqual(user.password, self.password)
        self.assertTrue(user.check_password(self.password))

    def test_duplicate_username_is_rejected(self):
        User.objects.create_user(
            username="newcustomer",
            email="existing@example.com",
            password=self.password,
        )

        self.register_customer(email="another@example.com")

        self.assertEqual(
            User.objects.filter(username="newcustomer").count(),
            1,
        )

    def test_duplicate_email_is_rejected(self):
        User.objects.create_user(
            username="existingcustomer",
            email="newcustomer@example.com",
            password=self.password,
        )

        response = self.register_customer()

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "An account with this email address already exists.",
        )
        self.assertFalse(
            User.objects.filter(username="newcustomer").exists()
        )

    def test_mismatched_passwords_are_rejected(self):
        response = self.register_customer(
            password2="Different-Test-Pass-938!"
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            User.objects.filter(username="newcustomer").exists()
        )


class CustomerLoginTests(TestCase):
    def setUp(self):
        self.url = reverse("customer_login")
        self.username = "loginuser"
        self.password = "A-Strong-Test-Pass-938!"

        User.objects.create_user(
            username=self.username,
            email="loginuser@example.com",
            password=self.password,
        )

    def test_login_page_loads(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Customer Login")

    def test_valid_credentials_log_in_user(self):
        response = self.client.post(
            self.url,
            {
                "username": self.username,
                "password": self.password,
            },
        )

        self.assertRedirects(
            response,
            reverse("login_success"),
        )
        self.assertEqual(
            int(self.client.session["_auth_user_id"]),
            User.objects.get(username=self.username).pk,
        )

    def test_invalid_password_is_rejected(self):
        response = self.client.post(
            self.url,
            {
                "username": self.username,
                "password": "Wrong-Password-938!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_unknown_username_is_rejected(self):
        response = self.client.post(
            self.url,
            {
                "username": "unknownuser",
                "password": self.password,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)
