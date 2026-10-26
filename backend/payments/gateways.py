"""Payment gateway integration (issue #9, OBS-F-012).

The supported payment mechanism is card payment processed through a
mock, in-process gateway. The gateway is deliberately deterministic so
tests and demos can drive both outcomes:

- any Luhn-valid card number succeeds, except
- ``4000000000000002`` -> declined (generic decline), and
- ``4000000000009995`` -> declined (insufficient funds),

mirroring common payment-provider test cards. Provider-internal
behavior beyond this integration (real charges, refunds, webhooks) is
out of scope for the project.

Replace ``MockCardGateway`` with a real provider client behind the same
interface to switch payment providers; nothing else in the codebase
needs to change.
"""

import secrets
from dataclasses import dataclass


@dataclass(frozen=True)
class PaymentResult:
    """Outcome of one gateway charge attempt."""

    succeeded: bool
    reference: str = ""
    failure_reason: str = ""


class MockCardGateway:
    """Deterministic in-process card gateway."""

    DECLINED_NUMBERS = {
        "4000000000000002": "Your card was declined.",
        "4000000000009995": "Your card has insufficient funds.",
    }

    def charge(
        self,
        amount,
        card_number,
        cvc,
        expiry_month,
        expiry_year,
    ):
        """Charge ``amount`` and return a :class:`PaymentResult`."""
        normalized = card_number.replace(" ", "").replace("-", "")

        if normalized in self.DECLINED_NUMBERS:
            return PaymentResult(
                succeeded=False,
                failure_reason=self.DECLINED_NUMBERS[normalized],
            )

        reference = "MOCK-{amount}-{token}".format(
            amount=f"{amount:.2f}",
            token=secrets.token_hex(8).upper(),
        )
        return PaymentResult(succeeded=True, reference=reference)


gateway = MockCardGateway()
