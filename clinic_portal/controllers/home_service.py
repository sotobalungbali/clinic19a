from odoo.http import request


def render_home(controller, **kwargs):
    """Render the ClinicOne patient overview without mutating source records."""
    profile = controller._clinic_profile()

    if not profile or profile.state != "active":
        values = {
            "page_name": "clinic_home",
            "clinic_profile": profile,
            "clinic_patient": profile.patient_id if profile else False,
            "clinic_partner": request.env.user.partner_id,
            "clinic_company": request.env.company,
        }
        return request.render(
            "clinic_portal.portal_access_unavailable",
            values,
        )

    profile._record_portal_access("home")
    summary = profile._portal_summary_counts()
    values = controller._clinic_base_values(profile, "clinic_home")
    values.update(summary)

    if profile.allow_booking_view:
        values["recent_bookings"] = request.env[
            "booking.booking"
        ].sudo().search(
            profile._portal_booking_domain(),
            order="start_datetime desc, id desc",
            limit=5,
        )
    else:
        values["recent_bookings"] = request.env["booking.booking"]

    if profile.allow_invoice_view:
        values["recent_invoices"] = request.env[
            "clinic.billing.invoice"
        ].sudo().search(
            profile._portal_invoice_domain(),
            order="invoice_date desc, id desc",
            limit=5,
        )
    else:
        values["recent_invoices"] = request.env["clinic.billing.invoice"]

    if profile.allow_treatment_history_view:
        values["recent_treatments"] = request.env[
            "clinic.encounter"
        ].sudo().search(
            profile._portal_treatment_domain(),
            order="date_start desc, id desc",
            limit=5,
        )
    else:
        values["recent_treatments"] = request.env["clinic.encounter"]

    return request.render("clinic_portal.portal_my_clinic", values)
