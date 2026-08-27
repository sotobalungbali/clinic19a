from werkzeug.exceptions import Forbidden

from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal

from . import booking_service
from . import home_service
from . import invoice_service
from . import treatment_service


class ClinicPatientPortal(CustomerPortal):
    """Odoo 19 Customer Portal extension with exact-patient ClinicOne scope."""

    def _clinic_profile(self, allow_create=True):
        Profile = request.env["clinic.portal.profile"].sudo()
        if allow_create:
            return Profile._ensure_for_user(
                request.env.user,
                request.env.company,
            )
        return Profile._find_for_user(
            request.env.user,
            request.env.company,
        )

    def _require_clinic_profile(self, feature=None):
        profile = self._clinic_profile()
        if not profile or profile.state != "active":
            raise Forbidden()

        feature_fields = {
            "bookings": "allow_booking_view",
            "invoices": "allow_invoice_view",
            "treatments": "allow_treatment_history_view",
        }
        field_name = feature_fields.get(feature)
        if field_name and not profile[field_name]:
            raise Forbidden()

        return profile

    def _clinic_page_size(self):
        return max(
            5,
            min(request.env.company.clinic_portal_page_size or 20, 100),
        )

    def _clinic_base_values(self, profile, page_name):
        return {
            "page_name": page_name,
            "clinic_profile": profile,
            "clinic_patient": profile.patient_id,
            "clinic_partner": request.env.user.partner_id,
            "clinic_company": request.env.company,
        }

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        # Odoo 19 `/my/counters` is readonly=True, so counters must never
        # auto-create a profile. Creation happens only on ClinicOne pages.
        profile = self._clinic_profile(allow_create=False)

        values["clinic_portal_profile"] = profile
        values["clinic_portal_enabled"] = bool(
            profile and profile.state == "active"
        )

        summary = {
            "clinic_booking_count": 0,
            "clinic_invoice_count": 0,
            "clinic_treatment_count": 0,
        }
        if profile:
            summary = profile._portal_summary_counts()

        for counter_name, value in summary.items():
            if counter_name in counters:
                values[counter_name] = value

        return values

    @http.route(
        ["/my/clinic"],
        type="http",
        auth="user",
        website=True,
        readonly=False,
    )
    def clinic_portal_home(self, **kwargs):
        return home_service.render_home(self, **kwargs)

    @http.route(
        ["/my/clinic/bookings", "/my/clinic/bookings/page/<int:page>"],
        type="http",
        auth="user",
        website=True,
        readonly=False,
    )
    def clinic_portal_bookings(self, page=1, sortby="newest", filterby="all", **kwargs):
        return booking_service.render_bookings(
            self,
            page=page,
            sortby=sortby,
            filterby=filterby,
            **kwargs,
        )

    @http.route(
        ["/my/clinic/bookings/<int:booking_id>"],
        type="http",
        auth="user",
        website=True,
        readonly=False,
    )
    def clinic_portal_booking(self, booking_id, **kwargs):
        return booking_service.render_booking(
            self,
            booking_id,
            **kwargs,
        )

    @http.route(
        ["/my/clinic/invoices", "/my/clinic/invoices/page/<int:page>"],
        type="http",
        auth="user",
        website=True,
        readonly=False,
    )
    def clinic_portal_invoices(self, page=1, sortby="newest", filterby="all", **kwargs):
        return invoice_service.render_invoices(
            self,
            page=page,
            sortby=sortby,
            filterby=filterby,
            **kwargs,
        )

    @http.route(
        ["/my/clinic/invoices/<int:invoice_id>"],
        type="http",
        auth="user",
        website=True,
        readonly=False,
    )
    def clinic_portal_invoice(self, invoice_id, **kwargs):
        return invoice_service.render_invoice(
            self,
            invoice_id,
            **kwargs,
        )

    @http.route(
        ["/my/clinic/treatments", "/my/clinic/treatments/page/<int:page>"],
        type="http",
        auth="user",
        website=True,
        readonly=False,
    )
    def clinic_portal_treatments(self, page=1, sortby="newest", **kwargs):
        return treatment_service.render_treatments(
            self,
            page=page,
            sortby=sortby,
            **kwargs,
        )

    @http.route(
        ["/my/clinic/treatments/<int:encounter_id>"],
        type="http",
        auth="user",
        website=True,
        readonly=False,
    )
    def clinic_portal_treatment(self, encounter_id, **kwargs):
        return treatment_service.render_treatment(
            self,
            encounter_id,
            **kwargs,
        )
