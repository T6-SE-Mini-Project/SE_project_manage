
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

        self.assertEqual(User.objects.filter(username="newcustomer").count(), 1)

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
        response = self.register_customer(password2="Different-Test-Pass-938!")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            User.objects.filter(username="newcustomer").exists()
        )
