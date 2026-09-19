from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from uuid import uuid4

from django.db import close_old_connections
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from fees.services import create_account, record_payment, total_paid
from tests.test_academic_scopes import AcademicFixture


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class FinancialConcurrencyTests(TransactionTestCase):
    def setUp(self):
        AcademicFixture.setUpTestData.__func__(type(self))

    def test_simultaneous_payments_cannot_overpay(self):
        account = create_account(
            self.admin,
            {
                "registration": self.sp.registrations.get().pk,
                "title": "Tuition",
                "total_fee": Decimal("1000.00"),
                "installments": [{"due_date": timezone.localdate(), "amount": Decimal("1000.00")}],
            },
        )

        def pay(_):
            close_old_connections()
            try:
                record_payment(
                    self.admin,
                    account.pk,
                    {
                        "amount": Decimal("700.00"),
                        "method": "CASH",
                        "paid_on": timezone.localdate(),
                        "reference": "",
                        "idempotency_key": uuid4(),
                    },
                )
                return "saved"
            except ValidationError:
                return "rejected"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(pay, [1, 2]))
        self.assertCountEqual(results, ["saved", "rejected"])
        self.assertEqual(total_paid(account), Decimal("700.00"))
