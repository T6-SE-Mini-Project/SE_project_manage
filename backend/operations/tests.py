"""Tests for automated order and inventory backups.

Issue #18 / OBS-NF-006 / TC-OBS-024: order and inventory data must be
backed up automatically at least once every 24 hours, and the backup
executions must be inspectable.
"""

import json
import shutil
import tempfile
from decimal import Decimal
from pathlib import Path

from django.core.management import CommandError, call_command
from django.test import TestCase
from django.utils import timezone

from books.models import Book
from orders.models import Order, OrderItem
from payments.models import Payment

from .models import BackupRun
from .services import backup_freshness, run_backup


class BackupTestCase(TestCase):
    """Writes backups into a temporary directory, never the real one."""

    def setUp(self):
        self.backup_dir = Path(tempfile.mkdtemp(prefix="obs-backup-test-"))
        self.addCleanup(shutil.rmtree, self.backup_dir, True)

        self.book = Book.objects.create(
            title="Backup Book",
            author="Backup Author",
            isbn="9780132350884",
            category="Fiction",
            price=Decimal("25.00"),
            stock_quantity=7,
        )
        self.order = Order.objects.create(
            session_key="backupsession",
            status=Order.STATUS_CONFIRMED,
            total_amount=Decimal("50.00"),
            paid_at=timezone.now(),
            stock_reserved=True,
        )
        OrderItem.objects.create(
            order=self.order,
            book=self.book,
            book_title=self.book.title,
            unit_price=Decimal("25.00"),
            quantity=2,
        )
        Payment.objects.create(
            order=self.order,
            amount=Decimal("50.00"),
            status=Payment.STATUS_SUCCEEDED,
            reference="MOCK-REF",
            card_last4="4242",
        )


class BackupRunTests(BackupTestCase):
    def test_backup_writes_order_and_inventory_data(self):
        run = run_backup(root=self.backup_dir)

        self.assertTrue(run.succeeded)
        self.assertEqual(run.status, BackupRun.STATUS_SUCCESS)

        location = Path(run.location)
        self.assertTrue(location.is_dir())

        # Orders, order lines, payments and the book catalogue (which
        # carries the stock levels) are all captured.
        for dataset in (
            "orders.order",
            "orders.orderitem",
            "payments.payment",
            "books.book",
        ):
            with self.subTest(dataset=dataset):
                self.assertTrue((location / f"{dataset}.json").is_file())

        self.assertEqual(run.record_counts["orders.order"], 1)
        self.assertEqual(run.record_counts["orders.orderitem"], 1)
        self.assertEqual(run.record_counts["payments.payment"], 1)
        self.assertEqual(run.record_counts["books.book"], 1)
        self.assertEqual(run.total_records, 4)
        self.assertGreater(run.size_bytes, 0)

    def test_backup_contents_are_restorable_fixtures(self):
        run = run_backup(root=self.backup_dir)

        payload = json.loads(
            (Path(run.location) / "orders.order.json").read_text()
        )

        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["model"], "orders.order")
        self.assertEqual(payload[0]["fields"]["total_amount"], "50.00")
        self.assertEqual(payload[0]["fields"]["status"], "CONFIRMED")

        inventory = json.loads(
            (Path(run.location) / "books.book.json").read_text()
        )
        self.assertEqual(inventory[0]["fields"]["stock_quantity"], 7)

    def test_manifest_records_counts_and_checksums(self):
        run = run_backup(root=self.backup_dir)

        manifest = json.loads(
            (Path(run.location) / "manifest.json").read_text()
        )

        self.assertEqual(manifest["backup_run_id"], run.pk)
        self.assertEqual(
            manifest["datasets"]["orders.order"]["records"], 1
        )
        self.assertEqual(
            len(manifest["datasets"]["books.book"]["sha256"]), 64
        )

    def test_every_run_is_recorded_with_its_trigger(self):
        run_backup(root=self.backup_dir, trigger=BackupRun.TRIGGER_SCHEDULED)
        run_backup(root=self.backup_dir, trigger=BackupRun.TRIGGER_MANUAL)

        self.assertEqual(BackupRun.objects.count(), 2)
        self.assertEqual(
            BackupRun.objects.filter(
                trigger=BackupRun.TRIGGER_SCHEDULED
            ).count(),
            1,
        )

    def test_failure_is_recorded_rather_than_raised(self):
        # A file where the backup directory should be makes mkdir fail.
        blocked = self.backup_dir / "blocked"
        blocked.write_text("not a directory", encoding="utf-8")

        run = run_backup(root=blocked)

        self.assertFalse(run.succeeded)
        self.assertEqual(run.status, BackupRun.STATUS_FAILED)
        self.assertTrue(run.error_message)
        self.assertIsNotNone(run.finished_at)

    def test_old_backup_artifacts_are_pruned(self):
        stale = self.backup_dir / "backup-20200101T000000Z-1"
        stale.mkdir(parents=True)
        (stale / "books.book.json").write_text("[]", encoding="utf-8")

        import os

        old_time = (
            timezone.now() - timezone.timedelta(days=40)
        ).timestamp()
        os.utime(stale, (old_time, old_time))

        run_backup(root=self.backup_dir, keep_days=14)

        self.assertFalse(stale.exists())
        # The execution record of the pruned run is still inspectable.
        self.assertTrue(BackupRun.objects.exists())

    def test_recent_artifacts_are_kept(self):
        first = run_backup(root=self.backup_dir)
        run_backup(root=self.backup_dir, keep_days=14)

        self.assertTrue(Path(first.location).exists())


class BackupFreshnessTests(BackupTestCase):
    """TC-OBS-024: a successful backup must exist every 24 hours."""

    def test_no_backup_is_reported_as_not_fresh(self):
        freshness = backup_freshness(max_age_hours=24)

        self.assertFalse(freshness["fresh"])
        self.assertIsNone(freshness["latest"])
        self.assertIn("No successful backup", freshness["detail"])

    def test_recent_backup_is_fresh(self):
        run_backup(root=self.backup_dir)

        freshness = backup_freshness(max_age_hours=24)

        self.assertTrue(freshness["fresh"])
        self.assertLess(freshness["age_hours"], 1)

    def test_backup_older_than_the_limit_is_not_fresh(self):
        run = run_backup(root=self.backup_dir)
        run.started_at = timezone.now() - timezone.timedelta(hours=30)
        run.save(update_fields=["started_at"])

        freshness = backup_freshness(max_age_hours=24)

        self.assertFalse(freshness["fresh"])
        self.assertGreater(freshness["age_hours"], 24)

    def test_failed_runs_do_not_count_as_backups(self):
        BackupRun.objects.create(
            started_at=timezone.now(),
            finished_at=timezone.now(),
            status=BackupRun.STATUS_FAILED,
            error_message="disk full",
        )

        self.assertFalse(backup_freshness(max_age_hours=24)["fresh"])


class BackupCommandTests(BackupTestCase):
    def call(self, command, *args, **options):
        from io import StringIO

        out = StringIO()
        call_command(command, *args, stdout=out, stderr=out, **options)
        return out.getvalue()

    def test_backup_data_command_records_a_scheduled_run(self):
        output = self.call(
            "backup_data",
            trigger="scheduled",
            destination=str(self.backup_dir),
        )

        self.assertIn("succeeded", output)
        self.assertIn("orders.order: 1 records", output)

        run = BackupRun.objects.get()
        self.assertEqual(run.trigger, BackupRun.TRIGGER_SCHEDULED)
        self.assertTrue(run.succeeded)

    def test_backup_data_command_fails_loudly(self):
        blocked = self.backup_dir / "blocked"
        blocked.write_text("not a directory", encoding="utf-8")

        with self.assertRaises(CommandError):
            self.call("backup_data", destination=str(blocked))

        self.assertFalse(BackupRun.objects.get().succeeded)

    def test_verify_backups_passes_after_a_backup(self):
        run_backup(root=self.backup_dir)

        output = self.call("verify_backups")

        self.assertIn("OBS-NF-006", output)
        self.assertIn("Recent backup executions", output)

    def test_verify_backups_fails_without_a_recent_backup(self):
        with self.assertRaises(CommandError) as raised:
            self.call("verify_backups")

        self.assertIn("No successful order and inventory backup", str(raised.exception))

    def test_verify_backups_fails_when_the_backup_is_stale(self):
        run = run_backup(root=self.backup_dir)
        run.started_at = timezone.now() - timezone.timedelta(hours=48)
        run.save(update_fields=["started_at"])

        with self.assertRaises(CommandError):
            self.call("verify_backups")

    def test_verify_backups_can_emit_json_evidence(self):
        run_backup(root=self.backup_dir)

        output = self.call("verify_backups", as_json=True)
        payload = json.loads(output)

        self.assertTrue(payload["fresh"])
        self.assertEqual(payload["max_age_hours"], 24)
        self.assertEqual(payload["latest"]["status"], "SUCCESS")
        self.assertEqual(len(payload["history"]), 1)

