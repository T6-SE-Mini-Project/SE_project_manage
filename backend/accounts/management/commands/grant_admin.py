"""Promote or demote an administrator by email address.

Firebase creates every account as an ordinary customer: it knows nothing
about this project's ``is_staff`` flag, and nothing a customer can do in
the browser may grant it. So the first administrator has to be made from
the command line, after they have signed in once through Firebase:

    python manage.py grant_admin you@example.com

Use ``--revoke`` to take the privilege away again. The Django admin at
/admin/ can do the same thing, but reaching it needs an administrator
already — which is exactly the situation this command exists for.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Grant or revoke administrator access for the account with this email."

    def add_arguments(self, parser):
        parser.add_argument(
            "email",
            help="Email address of the account to promote.",
        )
        parser.add_argument(
            "--revoke",
            action="store_true",
            help="Remove administrator access instead of granting it.",
        )

    def handle(self, *args, **options):
        email = options["email"].strip()
        grant = not options["revoke"]

        matches = list(
            get_user_model().objects.filter(email__iexact=email).order_by("pk")
        )

        if not matches:
            raise CommandError(
                f"No account with the email address {email}. "
                "Sign in through the app once, then run this again."
            )

        if len(matches) > 1:
            usernames = ", ".join(user.username for user in matches)
            raise CommandError(
                f"{len(matches)} accounts share the email address {email} "
                f"({usernames}). Promote one in the Django admin instead."
            )

        user = matches[0]

        if user.is_staff == grant:
            self.stdout.write(
                f"{user.username} is already "
                f"{'an administrator' if grant else 'a customer'}."
            )
            return

        user.is_staff = grant
        user.save(update_fields=["is_staff"])

        self.stdout.write(
            self.style.SUCCESS(
                f"{user.username} ({email}) is now "
                f"{'an administrator' if grant else 'a customer'}."
            )
        )
