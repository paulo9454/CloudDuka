"""Payments router facade (backward-compatible)."""

from backend.server import (  # noqa: F401
    mpesa_stk_push,
    mpesa_confirm_payment,
    mpesa_check_status,
    payments_mpesa_initiate,
    payments_mpesa_confirm,
    get_payment_status,
    payments_paystack_webhook,
    paystack_initialize,
    paystack_verify,
    paystack_webhook,
)
