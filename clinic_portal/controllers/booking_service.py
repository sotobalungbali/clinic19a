from collections import OrderedDict

from werkzeug.exceptions import NotFound

from odoo import fields, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import pager as portal_pager


def render_bookings(
    controller,
    page=1,
    sortby="newest",
    filterby="all",
    **kwargs,
):
    """Render exact-patient Booking records with portal pagination."""
    profile = controller._require_clinic_profile("bookings")
    profile._record_portal_access("bookings")

    Booking = request.env["booking.booking"].sudo()
    domain = list(profile._portal_booking_domain())

    now = fields.Datetime.now()
    filters = OrderedDict([
        ("all", {
            "label": _("All"),
            "domain": [],
        }),
        ("upcoming", {
            "label": _("Upcoming"),
            "domain": [
                ("start_datetime", ">=", now),
                ("state", "not in", ("done", "cancelled")),
            ],
        }),
        ("history", {
            "label": _("History"),
            "domain": [
                "|",
                ("start_datetime", "<", now),
                ("state", "=", "done"),
            ],
        }),
        ("cancelled", {
            "label": _("Cancelled"),
            "domain": [("state", "=", "cancelled")],
        }),
    ])
    if filterby not in filters:
        filterby = "all"
    domain += filters[filterby]["domain"]

    sortings = OrderedDict([
        ("newest", {
            "label": _("Newest"),
            "order": "start_datetime desc, id desc",
        }),
        ("oldest", {
            "label": _("Oldest"),
            "order": "start_datetime asc, id asc",
        }),
        ("status", {
            "label": _("Status"),
            "order": "state, start_datetime desc, id desc",
        }),
    ])
    if sortby not in sortings:
        sortby = "newest"

    count = Booking.search_count(domain)
    pager = portal_pager(
        url="/my/clinic/bookings",
        url_args={
            "sortby": sortby,
            "filterby": filterby,
        },
        total=count,
        page=page,
        step=controller._clinic_page_size(),
    )
    bookings = Booking.search(
        domain,
        order=sortings[sortby]["order"],
        limit=controller._clinic_page_size(),
        offset=pager["offset"],
    )
    request.session["my_clinic_bookings_history"] = bookings.ids[:100]

    values = controller._clinic_base_values(profile, "clinic_bookings")
    values.update({
        "bookings": bookings,
        "pager": pager,
        "sortby": sortby,
        "filterby": filterby,
        "searchbar_sortings": sortings,
        "searchbar_filters": filters,
        "default_url": "/my/clinic/bookings",
    })
    return request.render(
        "clinic_portal.portal_my_clinic_bookings",
        values,
    )


def render_booking(controller, booking_id, **kwargs):
    """Render one Booking only after exact patient/company ID intersection."""
    profile = controller._require_clinic_profile("bookings")
    Booking = request.env["booking.booking"].sudo()
    booking = Booking.search(
        [("id", "=", booking_id)] + profile._portal_booking_domain(),
        limit=1,
    )
    if not booking:
        raise NotFound()

    profile._record_portal_access("booking")
    values = controller._clinic_base_values(profile, "clinic_booking")
    values.update({
        "booking": booking,
        "native_invoice_url": (
            booking.invoice_id.get_portal_url()
            if booking.invoice_id
            and booking.invoice_id.state == "posted"
            and booking.invoice_id.partner_id == profile.partner_id
            else False
        ),
    })
    return request.render(
        "clinic_portal.portal_my_clinic_booking",
        values,
    )
