"""Tests for Firebase ID token verification and user linking.

These mint real RS256 tokens with a throwaway key pair and a self-signed
certificate, and point the verifier's certificate fetch at them, so the
signature, issuer, audience and expiry checks in ``accounts/firebase.py``
are exercised as written rather than mocked away.
"""

import datetime
import time
from io import StringIO
from unittest import mock

import jwt
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase

from config import env

from . import firebase
from .models import PROVIDER_GOOGLE, PROVIDER_PASSWORD, FirebaseIdentity
from .services import available_username, identity_for_claims

PROJECT_ID = "obs-test-project"
KEY_ID = "test-key-1"


def _signing_material():
    """An RSA key and a self-signed certificate, as Google publishes."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    name = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "securetoken.google.com")]
    )
    now = datetime.datetime.now(datetime.timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .sign(key, hashes.SHA256())
    )

    pem = certificate.public_bytes(serialization.Encoding.PEM).decode()
    return key, pem


# Generating a 2048-bit key takes long enough to be worth doing once for
# the whole test run rather than per test.
SIGNING_KEY, SIGNING_CERTIFICATE_PEM = _signing_material()


class FirebaseTokenMixin:
    """Mints signed ID tokens and makes the verifier trust them."""

    project_id = PROJECT_ID

    def setUp(self):
        super().setUp()

        self.private_key_pem = SIGNING_KEY.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode()

        firebase.public_keys.clear()
        self.addCleanup(firebase.public_keys.clear)

        fetch = mock.patch.object(
            firebase,
            "_fetch_certificates",
            return_value=({KEY_ID: SIGNING_CERTIFICATE_PEM}, 3600),
        )
        self.fetch_certificates = fetch.start()
        self.addCleanup(fetch.stop)

        project = mock.patch.object(env, "FIREBASE_PROJECT_ID", self.project_id)
        project.start()
        self.addCleanup(project.stop)

    def make_token(
        self,
        uid="firebase-uid-1",
        email="customer@example.com",
        email_verified=True,
        provider=PROVIDER_PASSWORD,
        name="Test Customer",
        audience=None,
        issuer=None,
        expires_in=3600,
        key_id=KEY_ID,
        algorithm="RS256",
        key=None,
        **claims,
    ):
        """Return a signed ID token with the given claims."""
        issued_at = int(time.time())
        payload = {
            "iss": issuer or f"{firebase.ISSUER_PREFIX}{self.project_id}",
            "aud": audience or self.project_id,
            "sub": uid,
            "iat": issued_at,
            "exp": issued_at + expires_in,
            "auth_time": issued_at,
            "email": email,
            "email_verified": email_verified,
            "name": name,
            "firebase": {"sign_in_provider": provider, "identities": {}},
        }
        payload.update(claims)

        return jwt.encode(
            payload,
            key if key is not None else self.private_key_pem,
            algorithm=algorithm,
            headers={"kid": key_id} if key_id else {},
        )


class IdTokenVerificationTests(FirebaseTokenMixin, TestCase):
    def test_a_valid_token_is_accepted(self):
        claims = firebase.verify_id_token(self.make_token())

        self.assertEqual(claims["sub"], "firebase-uid-1")
        self.assertEqual(claims["email"], "customer@example.com")

    def test_certificates_are_fetched_once_and_cached(self):
        firebase.verify_id_token(self.make_token())
        firebase.verify_id_token(self.make_token())

        self.assertEqual(self.fetch_certificates.call_count, 1)

    def test_a_token_for_another_project_is_rejected(self):
        # Google signs every project's tokens with the same keys, so the
        # audience is the only thing standing between this API and a token
        # minted by somebody else's Firebase project.
        token = self.make_token(audience="someone-elses-project")

        with self.assertRaises(firebase.FirebaseAuthError):
            firebase.verify_id_token(token)

    def test_a_token_from_another_issuer_is_rejected(self):
        token = self.make_token(issuer="https://evil.example.com/")

        with self.assertRaises(firebase.FirebaseAuthError):
            firebase.verify_id_token(token)

    def test_an_expired_token_is_rejected(self):
        token = self.make_token(expires_in=-120)

        with self.assertRaises(firebase.FirebaseAuthError):
            firebase.verify_id_token(token)

    def test_a_token_signed_by_another_key_is_rejected(self):
        other_key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048
        )
        token = self.make_token(
            key=other_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            ).decode()
        )

        with self.assertRaises(firebase.FirebaseAuthError):
            firebase.verify_id_token(token)

    def test_an_unsigned_token_is_rejected(self):
        # The classic forgery: strip the signature and claim the algorithm
        # is "none". PyJWT would need "none" in algorithms to accept it;
        # this asserts it never is.
        token = jwt.encode(
            {"sub": "attacker", "aud": self.project_id},
            key="",
            algorithm="none",
        )

        with self.assertRaises(firebase.FirebaseAuthError):
            firebase.verify_id_token(token)

    def test_a_token_with_an_unknown_key_id_is_rejected(self):
        with self.assertRaises(firebase.FirebaseAuthError):
            firebase.verify_id_token(self.make_token(key_id="not-googles-key"))

    def test_garbage_is_rejected_without_fetching_certificates(self):
        with self.assertRaises(firebase.FirebaseAuthError):
            firebase.verify_id_token("not-a-jwt")

        self.fetch_certificates.assert_not_called()

    def test_tokens_are_refused_when_no_project_is_configured(self):
        # Verifying with an empty audience would accept any project's
        # tokens, so a misconfigured server must refuse instead.
        with mock.patch.object(env, "FIREBASE_PROJECT_ID", ""):
            with self.assertRaises(firebase.FirebaseAuthError):
                firebase.verify_id_token(self.make_token())

    def test_bearer_token_is_read_from_the_authorization_header(self):
        request = mock.Mock(META={"HTTP_AUTHORIZATION": "Bearer abc.def.ghi"})
        self.assertEqual(firebase.bearer_token(request), "abc.def.ghi")

    def test_other_authorization_schemes_are_ignored(self):
        request = mock.Mock(META={"HTTP_AUTHORIZATION": "Basic dXNlcjpwdw=="})
        self.assertIsNone(firebase.bearer_token(request))

        self.assertIsNone(firebase.bearer_token(mock.Mock(META={})))
        self.assertIsNone(
            firebase.bearer_token(mock.Mock(META={"HTTP_AUTHORIZATION": "Bearer"}))
        )


class IdentityLinkingTests(FirebaseTokenMixin, TestCase):
    def claims(self, **overrides):
        return firebase.verify_id_token(self.make_token(**overrides))

    def test_first_sign_in_creates_a_user_and_stores_the_uid(self):
        identity = identity_for_claims(self.claims(uid="uid-new"))

        self.assertEqual(identity.uid, "uid-new")
        self.assertEqual(identity.user.email, "customer@example.com")
        self.assertEqual(identity.user.username, "customer")
        self.assertEqual(identity.provider, PROVIDER_PASSWORD)
        self.assertTrue(identity.email_verified)
        self.assertEqual(
            FirebaseIdentity.objects.filter(uid="uid-new").count(), 1
        )

    def test_the_django_account_has_no_usable_password(self):
        # Firebase owns credentials: no Django password check may ever
        # succeed for an account created from a token.
        identity = identity_for_claims(self.claims(uid="uid-no-password"))

        self.assertFalse(identity.user.has_usable_password())

    def test_signing_in_again_reuses_the_same_user(self):
        first = identity_for_claims(self.claims(uid="uid-same"))
        second = identity_for_claims(self.claims(uid="uid-same"))

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(first.user_id, second.user_id)
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_a_changed_email_moves_with_the_uid(self):
        identity_for_claims(self.claims(uid="uid-move"))
        identity = identity_for_claims(
            self.claims(uid="uid-move", email="renamed@example.com")
        )

        self.assertEqual(identity.email, "renamed@example.com")
        self.assertEqual(identity.user.email, "renamed@example.com")
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_the_provider_records_the_latest_sign_in(self):
        identity_for_claims(self.claims(uid="uid-provider"))
        identity = identity_for_claims(
            self.claims(uid="uid-provider", provider=PROVIDER_GOOGLE)
        )

        self.assertEqual(identity.provider, PROVIDER_GOOGLE)
        self.assertEqual(identity.provider_display, "Google")

    def test_a_verified_email_adopts_the_matching_existing_account(self):
        # The administrator made by "manage.py createsuperuser" predates
        # Firebase; signing in with the same (verified) address must keep
        # their account, and with it is_staff and their order history.
        administrator = get_user_model().objects.create_user(
            username="bookstore-admin",
            email="Admin@Example.com",
            password="LegacyPassword123",
            is_staff=True,
        )

        identity = identity_for_claims(
            self.claims(uid="uid-admin", email="admin@example.com")
        )

        self.assertEqual(identity.user_id, administrator.pk)
        self.assertTrue(identity.user.is_staff)
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_an_unverified_email_never_adopts_an_existing_account(self):
        # Firebase's email/password provider does not verify addresses, so
        # adopting on an unverified match would hand anyone who registers
        # "admin@example.com" the real administrator's account.
        administrator = get_user_model().objects.create_user(
            username="bookstore-admin",
            email="admin@example.com",
            password="LegacyPassword123",
            is_staff=True,
        )

        identity = identity_for_claims(
            self.claims(
                uid="uid-impostor",
                email="admin@example.com",
                email_verified=False,
            )
        )

        self.assertNotEqual(identity.user_id, administrator.pk)
        self.assertFalse(identity.user.is_staff)

    def test_an_account_already_linked_is_not_adopted_again(self):
        identity_for_claims(self.claims(uid="uid-first", email="shared@example.com"))

        second = identity_for_claims(
            self.claims(uid="uid-second", email="shared@example.com")
        )

        self.assertNotEqual(
            second.user_id,
            FirebaseIdentity.objects.get(uid="uid-first").user_id,
        )

    def test_usernames_are_made_unique(self):
        get_user_model().objects.create_user(username="customer")

        identity = identity_for_claims(self.claims(uid="uid-dup"))

        self.assertEqual(identity.user.username, "customer-2")

    def test_a_token_without_an_email_still_gets_a_username(self):
        identity = identity_for_claims(
            self.claims(uid="uid-no-email", email="", name="")
        )

        self.assertTrue(identity.user.username.startswith("user-"))
        self.assertEqual(identity.user.email, "")

    def test_available_username_falls_back_when_nothing_is_usable(self):
        self.assertEqual(available_username("!!!"), "customer")


class GrantAdminCommandTests(TestCase):
    """The only way to make the first administrator (see the command)."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="newadmin", email="newadmin@example.com"
        )

    def run_command(self, *args):
        output = StringIO()
        call_command("grant_admin", *args, stdout=output)
        return output.getvalue()

    def test_an_account_can_be_promoted_by_email(self):
        self.run_command("NewAdmin@example.com")

        self.user.refresh_from_db()
        self.assertTrue(self.user.is_staff)

    def test_administrator_access_can_be_revoked(self):
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])

        self.run_command("newadmin@example.com", "--revoke")

        self.user.refresh_from_db()
        self.assertFalse(self.user.is_staff)

    def test_an_unknown_email_fails_loudly(self):
        with self.assertRaises(CommandError):
            self.run_command("nobody@example.com")

        # Nothing was promoted by accident.
        self.assertFalse(
            get_user_model().objects.filter(is_staff=True).exists()
        )

    def test_a_shared_email_is_refused_rather_than_guessed(self):
        get_user_model().objects.create_user(
            username="twin", email="newadmin@example.com"
        )

        with self.assertRaises(CommandError):
            self.run_command("newadmin@example.com")


class MiddlewareConfigurationTests(SimpleTestCase):
    def test_firebase_middleware_follows_djangos_authentication_middleware(self):
        # Order is load-bearing: the Firebase middleware overrides the user
        # Django's AuthenticationMiddleware resolved from the session, so
        # it has to run after it.
        middleware = list(settings.MIDDLEWARE)

        self.assertIn(
            "accounts.middleware.FirebaseAuthenticationMiddleware", middleware
        )
        self.assertGreater(
            middleware.index("accounts.middleware.FirebaseAuthenticationMiddleware"),
            middleware.index(
                "django.contrib.auth.middleware.AuthenticationMiddleware"
            ),
        )
