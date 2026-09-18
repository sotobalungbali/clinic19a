




"""Central deny-by-default external side-effect policy."""

import re

from odoo.exceptions import UserError


class DemoSafeModeService:
    CAPABILITIES = {
        "email",
        "sms",
        "whatsapp",
        "payment_gateway",
        "webhook",
        "external_api_mutation",
        "portal_invitation",
        "ecommerce_payment",
        "outbound_clinical_message",
    }

    def __init__(self, run):
        run.ensure_one()
        self.run = run

    def assert_allowed(self, capability, explicit_opt_in=False):
        if capability not in self.CAPABILITIES:
            raise UserError(f"Unknown external capability: {capability}")
        if self.run.safe_mode or not explicit_opt_in:
            raise UserError(
                f"Demo Safe Mode blocks external capability: {capability}. "
                "A specific manager-controlled opt-in outside one-click generation is required."
            )
        return True

    @staticmethod
    def synthetic_email(demo_key):
        local = re.sub(r"[^a-z0-9]+", "-", (demo_key or "demo").lower()).strip("-")
        local = local or "demo"
        return f"{local}@clinicone-demo.invalid"
























