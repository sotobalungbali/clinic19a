from collections import OrderedDict

from werkzeug.exceptions import NotFound

from odoo import _
from odoo.http import request
from odoo.addons.portal.controllers.portal import pager as portal_pager


def render_treatments(
    controller,
    page=1,
    sortby="newest",
    **kwargs,
):
    """Render completed Encounter history only."""
    profile = controller._require_clinic_profile("treatments")
    profile._record_portal_access("treatments")

    Encounter = request.env["clinic.encounter"].sudo()
    domain = list(profile._portal_treatment_domain())

    sortings = OrderedDict([
        ("newest", {
            "label": _("Newest"),
            "order": "date_start desc, id desc",
        }),
        ("oldest", {
            "label": _("Oldest"),
            "order": "date_start asc, id asc",
        }),
        ("treatment", {
            "label": _("Treatment"),
            "order": "treatment_id, date_start desc, id desc",
        }),
    ])
    if sortby not in sortings:
        sortby = "newest"

    count = Encounter.search_count(domain)
    pager = portal_pager(
        url="/my/clinic/treatments",
        url_args={"sortby": sortby},
        total=count,
        page=page,
        step=controller._clinic_page_size(),
    )
    encounters = Encounter.search(
        domain,
        order=sortings[sortby]["order"],
        limit=controller._clinic_page_size(),
        offset=pager["offset"],
    )
    request.session["my_clinic_treatments_history"] = encounters.ids[:100]

    values = controller._clinic_base_values(profile, "clinic_treatments")
    values.update({
        "encounters": encounters,
        "pager": pager,
        "sortby": sortby,
        "searchbar_sortings": sortings,
        "default_url": "/my/clinic/treatments",
    })
    return request.render(
        "clinic_portal.portal_my_clinic_treatments",
        values,
    )


def render_treatment(controller, encounter_id, **kwargs):
    """Render one completed Encounter without generic clinical-note exposure."""
    profile = controller._require_clinic_profile("treatments")
    Encounter = request.env["clinic.encounter"].sudo()
    encounter = Encounter.search(
        [("id", "=", encounter_id)] + profile._portal_treatment_domain(),
        limit=1,
    )
    if not encounter:
        raise NotFound()

    # The generic Treatment History deliberately exposes completed procedure
    # sessions only. SOAP notes, assessments, diagnoses, vitals, internal
    # comments, and unpublished documents remain outside addon 31.
    procedure_sessions = request.env[
        "clinic.procedure.session"
    ].sudo().search([
        ("encounter_id", "=", encounter.id),
        ("company_id", "=", profile.company_id.id),
        ("state", "=", "done"),
    ], order="date_start asc, id asc")

    profile._record_portal_access("treatment")
    values = controller._clinic_base_values(profile, "clinic_treatment")
    values.update({
        "encounter": encounter,
        "procedure_sessions": procedure_sessions,
    })
    return request.render(
        "clinic_portal.portal_my_clinic_treatment",
        values,
    )
