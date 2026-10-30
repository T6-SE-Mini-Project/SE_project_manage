"""Tests for how accounts are stored and protected.

Customer credentials live in Firebase (see ``tests_firebase.py``), so
what is tested here is what Django still owns: the password storage of
the administrator accounts made with ``manage.py createsuperuser`` for
the admin site, the fact that a Firebase-backed account has no password
at all, and the admin site's own authorization.
"""

from django.conf import settings
from django.contrib.auth.hashers import get_hasher, identify_hasher
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import FirebaseIdentity


class PasswordStorageTests(TestCase):
    """TC-OBS-021 / TC-OBS-030: OBS-NF-003 and OBS-SR-003.

    The only passwords this project still stores are the ones for the
    Django admin site, set by ``createsuperuser`` or in the admin itself.
    Django hashes them, and these assert that it does — a plaintext or
    unrecognized stored credential must fail the suite.
    """

    def setUp(self):
        self.password = "A-Strong-Test-Pass-938!"
        self.user = User.objects.create_user(
            username="storeadmin",
            email="storeadmin@example.com",
            password=self.password,
            is_staff=True,
        )

    def test_password_is_hashed(self):
        # The stored password must not be plaintext.
        self.assertNotEqual(self.user.password, self.password)

        # Django must verify the original password against the stored hash.
        self.assertTrue(self.user.check_password(self.password))

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
            identify_hasher(self.user.password).algorithm,
            configured_algorithm,
        )
        self.assertEqual(
            self.user.password.split("$")[0], configured_algorithm
        )

    def test_password_hash_uses_configured_hasher(self):
        # Same reasoning as above: assert against the configured hasher's
        # algorithm label rather than a guess derived from its class name,
        # so this holds for whichever hasher the settings select.
        self.assertTrue(
            self.user.password.startswith(f"{get_hasher('default').algorithm}$")
        )

    def test_a_firebase_account_stores_no_password(self):
        # Customers authenticate with a Firebase ID token. Their Django
        # account is given an unusable password, so no password check can
        # ever succeed for it and there is no credential to leak.
        customer = User.objects.create_user(
            username="firebasecustomer",
            email="customer@example.com",
        )
        customer.set_unusable_password()
        customer.save(update_fields=["password"])
        FirebaseIdentity.objects.create(
            user=customer, uid="uid-password-test"
        )

        self.assertFalse(customer.has_usable_password())
        self.assertFalse(customer.check_password(""))

    def test_no_password_endpoint_remains(self):
        # The template login and registration pages were removed with the
        # move to Firebase. Nothing may accept a password again by
        # accident: a second credential path would bypass Firebase
        # entirely.
        self.assertEqual(self.client.get("/login/").status_code, 404)
        self.assertEqual(self.client.get("/register/").status_code, 404)
        self.assertEqual(
            self.client.post(
                "/api/auth/login/",
                data={"username": "storeadmin", "password": self.password},
            ).status_code,
            404,
        )


class SessionCookieTests(TestCase):
    """The session cookie no longer signs anybody in.

    It keys the *guest* cart and guest orders, which is why it still
    expires: an abandoned browser should not hand the next person at the
    machine a cart. Who the caller is comes from the Firebase ID token,
    which the SDK refreshes while the customer keeps using the app.
    """

    def test_session_cookie_age_is_15_minutes(self):
        self.assertEqual(settings.SESSION_COOKIE_AGE, 900)


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
