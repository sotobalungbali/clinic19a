from collections import OrderedDict

from werkzeug.exceptions import NotFound

from odoo import _
from odoo.http import request
from odoo.addons.portal.controllers.portal import pager as portal_pager


def render_invoices(
    controller,
    page=1,
    sortby="newest",
    filterby="all",
    **kwargs,
):
    """Render Clinic Billing summaries; official invoice UI remains native."""
    profile = controller._require_clinic_profile("invoices")
    profile._record_portal_access("invoices")

    Invoice = request.env["clinic.billing.invoice"].sudo()
    domain = list(profile._portal_invoice_domain())

    filters = OrderedDict([
        ("all", {
            "label": _("All"),
            "domain": [],
        }),
        ("open", {
            "label": _("Open"),
            "domain": [
                ("state", "in", ("confirmed", "posted")),
                ("amount_residual", ">", 0),
            ],
        }),
        ("paid", {
            "label": _("Paid"),
            "domain": [("state", "=", "paid")],
        }),
    ])
    if filterby not in filters:
        filterby = "all"
    domain += filters[filterby]["domain"]

    sortings = OrderedDict([
        ("newest", {
            "label": _("Newest"),
            "order": "invoice_date desc, id desc",
        }),
        ("oldest", {
            "label": _("Oldest"),
            "order": "invoice_date asc, id asc",
        }),
        ("status", {
            "label": _("Status"),
            "order": "state, invoice_date desc, id desc",
        }),
        ("amount", {
            "label": _("Amount"),
            "order": "amount_total desc, invoice_date desc, id desc",
        }),
    ])
    if sortby not in sortings:
        sortby = "newest"

    count = Invoice.search_count(domain)
    pager = portal_pager(
        url="/my/clinic/invoices",
        url_args={
            "sortby": sortby,
            "filterby": filterby,
        },
        total=count,
        page=page,
        step=controller._clinic_page_size(),
    )
    invoices = Invoice.search(
        domain,
        order=sortings[sortby]["order"],
        limit=controller._clinic_page_size(),
        offset=pager["offset"],
    )
    request.session["my_clinic_invoices_history"] = invoices.ids[:100]

    values = controller._clinic_base_values(profile, "clinic_invoices")
    values.update({
        "invoices": invoices,
        "pager": pager,
        "sortby": sortby,
        "filterby": filterby,
        "searchbar_sortings": sortings,
        "searchbar_filters": filters,
        "default_url": "/my/clinic/invoices",
    })
    return request.render(
        "clinic_portal.portal_my_clinic_invoices",
        values,
    )


def render_invoice(controller, invoice_id, **kwargs):
    """Render one Clinic Billing record and hand payment/PDF to account.move."""
    profile = controller._require_clinic_profile("invoices")
    Invoice = request.env["clinic.billing.invoice"].sudo()
    invoice = Invoice.search(
        [("id", "=", invoice_id)] + profile._portal_invoice_domain(),
        limit=1,
    )
    if not invoice:
        raise NotFound()

    profile._record_portal_access("invoice")
    native_invoice_url = False
    if (
        invoice.move_id
        and invoice.move_id.state == "posted"
        and invoice.move_id.partner_id == profile.partner_id
    ):
        native_invoice_url = invoice.move_id.get_portal_url()

    values = controller._clinic_base_values(profile, "clinic_invoice")
    values.update({
        "clinic_invoice": invoice,
        "native_invoice_url": native_invoice_url,
    })
    return request.render(
        "clinic_portal.portal_my_clinic_invoice",
        values,
    )
