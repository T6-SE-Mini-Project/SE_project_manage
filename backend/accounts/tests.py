from django.conf import settings
from django.contrib.auth.hashers import get_hasher, identify_hasher
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

        # The stored password must not be plaintext.
        self.assertNotEqual(user.password, self.password)

        # Django must verify the original password against the stored hash.
        self.assertTrue(user.check_password(self.password))

        # The stored value must be an identifiable Django password hash in
        # the "<algorithm>$..." encoded format, produced by the configured
        # hasher. identify_hasher raises ValueError for anything that is not
        # a valid Django encoded password.
        #
        # The expected label comes from the configured hasher's own
        # ``algorithm`` attribute, which is what Django writes into the hash.
        # It cannot be derived from the hasher's class name: the default
        # PBKDF2PasswordHasher stores "pbkdf2_sha256", not "pbkdf2".
        configured_algorithm = get_hasher("default").algorithm

        self.assertEqual(
            identify_hasher(user.password).algorithm,
            configured_algorithm,
        )
        self.assertEqual(user.password.split("$")[0], configured_algorithm)

    def test_password_hash_uses_configured_hasher(self):
        self.register_customer()

        user = User.objects.get(username="newcustomer")

        # Same reasoning as above: assert against the configured hasher's
        # algorithm label rather than a guess derived from its class name,
        # so this holds for whichever hasher the settings select.
        self.assertTrue(
            user.password.startswith(f"{get_hasher('default').algorithm}$")
        )

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
        self.success_url = reverse("login_success")
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

        self.assertRedirects(response, self.success_url)
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

    def test_login_success_requires_authentication(self):
        response = self.client.get(self.success_url)

        expected_url = (
            f"{self.url}?next={self.success_url}"
        )

        self.assertRedirects(response, expected_url)

    def test_authenticated_user_can_access_login_success(self):
        user = User.objects.get(username=self.username)
        self.client.force_login(user)

        response = self.client.get(self.success_url)

        self.assertEqual(response.status_code, 200)


class SessionTimeoutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="sessionuser",
            email="sessionuser@example.com",
            password="A-Strong-Test-Pass-938!",
        )

    def test_session_cookie_age_is_15_minutes(self):
        self.assertEqual(settings.SESSION_COOKIE_AGE, 900)

    def test_expired_session_cannot_access_protected_page(self):
        self.client.force_login(self.user)

        session = self.client.session
        session.set_expiry(-1)
        session.save()

        response = self.client.get(reverse("login_success"))

        self.assertRedirects(
            response,
            f"{reverse('customer_login')}?next={reverse('login_success')}",
        )


class AdminAuthorizationTests(TestCase):
    def test_anonymous_user_cannot_access_admin(self):
        response = self.client.get(reverse("admin:index"))

        self.assertIn(response.status_code, [301, 302])

    def test_regular_customer_cannot_access_admin(self):
        customer = User.objects.create_user(
            username="regularcustomer",
            email="customer@example.com",
            password="A-Strong-Test-Pass-938!",
        )
        self.client.force_login(customer)

        response = self.client.get(reverse("admin:index"))

        self.assertIn(response.status_code, [301, 302, 403])

    def test_staff_user_can_access_admin(self):
        staff_user = User.objects.create_user(
            username="staffmember",
            email="staff@example.com",
            password="A-Strong-Test-Pass-938!",
            is_staff=True,
        )
        self.client.force_login(staff_user)

        response = self.client.get(reverse("admin:index"))

        self.assertEqual(response.status_code, 200)
