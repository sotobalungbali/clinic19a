# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal


class ClinicWalletPortal(CustomerPortal):
    """Small, explicit portal surface; business security remains in ORM models."""

    @staticmethod
    def _portal_partner():
        return request.env.user.partner_id.commercial_partner_id

    def _wallet_page_values(self, error=None):
        partner = self._portal_partner()
        company = request.env.company
        wallet = request.env["clinic.wallet"].search([
            ("partner_id", "=", partner.id),
            ("company_id", "=", company.id),
            ("active", "=", True),
        ], limit=1)
        transactions = request.env["clinic.wallet.transaction"].search(
            [("wallet_id", "=", wallet.id)], order="date desc, id desc", limit=100
        ) if wallet else request.env["clinic.wallet.transaction"].browse()
        requests = request.env["clinic.wallet.portal.request"].search([
            ("partner_id", "=", partner.id),
            ("company_id", "=", company.id),
        ], order="create_date desc, id desc", limit=50)
        return {
            "page_name": "clinic_wallet",
            "wallet": wallet,
            "transactions": transactions,
            "wallet_requests": requests,
            "error": error,
        }

    @http.route(["/my/clinic-wallet"], type="http", auth="user", website=True)
    def portal_wallet(self, **kwargs):
        return request.render("clinic_wallet.portal_my_wallet", self._wallet_page_values())

    @http.route(
        ["/my/clinic-wallet/request"],
        type="http",
        auth="user",
        website=True,
        methods=["POST"],
        csrf=True,
    )
    def portal_wallet_request(self, **post):
        values = self._wallet_page_values()
        wallet = values["wallet"]
        if not wallet:
            return request.render(
                "clinic_wallet.portal_my_wallet",
                self._wallet_page_values(_("No active wallet is available for this company.")),
            )
        try:
            request_type = post.get("request_type")
            if request_type not in ("topup", "refund"):
                raise ValidationError(_("Invalid wallet request type."))
            amount = float(post.get("amount") or 0.0)
            req = request.env["clinic.wallet.portal.request"].create({
                "request_type": request_type,
                "wallet_id": wallet.id,
                "partner_id": wallet.partner_id.id,
                "company_id": wallet.company_id.id,
                "currency_id": wallet.currency_id.id,
                "amount": amount,
                "note": post.get("note") or "",
            })
            req.action_submit()
            return request.redirect("/my/clinic-wallet")
        except (AccessError, UserError, ValidationError, ValueError) as exc:
            return request.render(
                "clinic_wallet.portal_my_wallet",
                self._wallet_page_values(str(exc)),
            )




