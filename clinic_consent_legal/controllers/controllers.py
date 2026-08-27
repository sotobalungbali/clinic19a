# -*- coding: utf-8 -*-
"""Portal endpoints for ClinicOne consent documents.

The portal is read-only here. Legal signing continues to use the model's
server-side `action_sign()` contract so signature capture can be provided by a
dedicated UI/provider without weakening authorization.
"""

from odoo import http
from odoo.exceptions import AccessError, MissingError
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal


class ClinicConsentPortal(CustomerPortal):

    @http.route(
        ["/my/consents"],
        type="http",
        auth="user",
        website=True,
        readonly=True,
    )
    def portal_my_consents(self, **kwargs):
        partner = request.env.user.partner_id
        Consent = request.env["clinic.consent.form"].sudo()
        domain = [
            "|",
            ("patient_id", "=", partner.id),
            ("guardian_partner_id", "=", partner.id),
            ("active", "=", True),
        ]
        consents = Consent.search(domain, order="create_date desc, id desc", limit=100)
        return request.render(
            "clinic_consent_legal.portal_my_consents",
            {
                "page_name": "consents",
                "consents": consents,
            },
        )

    @http.route(
        ["/my/consents/<int:consent_id>"],
        type="http",
        auth="public",
        website=True,
        readonly=True,
    )
    def portal_consent_page(self, consent_id, access_token=None, **kwargs):
        try:
            consent = self._document_check_access(
                "clinic.consent.form",
                consent_id,
                access_token=access_token,
            )
        except (AccessError, MissingError):
            return request.redirect("/my")

        return request.render(
            "clinic_consent_legal.portal_consent_page",
            {
                "page_name": "consent",
                "consent": consent,
                "access_token": access_token,
            },
        )
