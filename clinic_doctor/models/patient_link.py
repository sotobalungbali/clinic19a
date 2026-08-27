
# -*- coding: utf-8 -*-
# File: clinic_doctor/models/patient_link.py
# Module: clinic_doctor
#
# ClinicOne — Doctor ↔ Patient linkage (Odoo 19 CE ready)
#
# Scope
# -----
# 1) Extend clinic.patient:
#    - Primary Doctor & Preferred Doctors (M2M)
#    - Appointment KPIs (counts, last/upcoming, no-show)
#    - Quick actions (view/book with doctor)
# 2) Extend clinic.doctor:
#    - Backlink M2M to patients + counter & action
# 3) Extend clinic.appointment (lightweight):
#    - Onchange to auto-bind patient by partner
#    - Policy: partner-patient consistency, optional auto-create patient
#
# Notes
# -----
# * All strings are in English (product requirement).
# * Multi-company aware (doctor <-> patient relations are scoped by company surface
#   via domains/actions dan kebijakan operasional).
# * Optional features guarded by config parameters (see docstrings).

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


# -----------------------------------------------------------------------------
# EXTEND: clinic.patient
# -----------------------------------------------------------------------------
class ClinicPatient(models.Model):
    _inherit = "clinic.patient"

    # -------------------------------------------------------------------------
    # DOCTOR PREFERENCES & LINKS
    # -------------------------------------------------------------------------
    primary_doctor_id = fields.Many2one(
        "clinic.doctor",
        ondelete="set null",
        index=True,
        tracking=True,
        help="Primary doctor responsible for this patient."
    )
    preferred_doctor_ids = fields.Many2many(
        "clinic.doctor",
        "clinic_patient_doctor_rel",      # shared M2M table with doctor-side backlink
        "patient_id",
        "doctor_id",
        string="Preferred Doctors",
        help="Preferred doctors for this patient."
    )

    # Optional specialty preference (helps routing & pricing; not enforced)
    preferred_specialty_id = fields.Many2one(
        "clinic.specialty",
        ondelete="set null",
        help="Preferred specialty for this patient (optional)."
    )

    # -------------------------------------------------------------------------
    # APPOINTMENT INSIGHTS (KPIs & NAVIGATION)
    # -------------------------------------------------------------------------
    appointment_count = fields.Integer(
        compute="_compute_appointment_kpis",
        store=False,
        help="Total number of appointments for this patient."
    )
    open_appointment_count = fields.Integer(
        compute="_compute_appointment_kpis",
        store=False,
        help="Number of non-terminal appointments (draft/confirmed/checked-in/in-treatment)."
    )
    no_show_count = fields.Integer(
        compute="_compute_appointment_kpis",
        store=False,
        help="Number of no-show appointments."
    )
    last_appointment_id = fields.Many2one(
        "clinic.appointment",
        compute="_compute_appointment_kpis",
        store=False,
        help="Most recent completed appointment for this patient."
    )
    upcoming_appointment_id = fields.Many2one(
        "clinic.appointment",
        compute="_compute_appointment_kpis",
        store=False,
        help="Nearest upcoming appointment for this patient."
    )

    # Convenience mirrors for UI (from primary doctor)
    next_available_slot_primary_doctor = fields.Datetime(
        compute="_compute_primary_doctor_mirrors",
        store=False,
        help="Next available slot of the primary doctor (if availability module is installed)."
    )
    primary_doctor_room = fields.Many2one(
        "clinic.room",
        compute="_compute_primary_doctor_mirrors",
        store=False,
        help="Default room of the primary doctor, if any."
    )

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    def _compute_appointment_kpis(self):
        """
        Compute appointment KPIs via read_group for performance.
        """
        ids = self.ids or []
        if not ids or "clinic.appointment" not in self.env:
            for rec in self:
                rec.appointment_count = 0
                rec.open_appointment_count = 0
                rec.no_show_count = 0
                rec.last_appointment_id = False
                rec.upcoming_appointment_id = False
            return

        App = self.env["clinic.appointment"]

        # all appointments
        g_all = App.read_group(
            [("patient_id", "in", ids)],
            ["patient_id"],
            ["patient_id"],
        )
        map_all = {g["patient_id"][0]: g["patient_id_count"] for g in g_all}

        # open appointments
        g_open = App.read_group(
            [("patient_id", "in", ids), ("state", "not in", ["canceled", "done", "no_show"])],
            ["patient_id"],
            ["patient_id"],
        )
        map_open = {g["patient_id"][0]: g["patient_id_count"] for g in g_open}

        # no-show
        g_ns = App.read_group(
            [("patient_id", "in", ids), ("state", "=", "no_show")],
            ["patient_id"],
            ["patient_id"],
        )
        map_ns = {g["patient_id"][0]: g["patient_id_count"] for g in g_ns}

        # last done & upcoming (per-record search for clarity)
        now = fields.Datetime.now()
        for rec in self:
            rec.appointment_count = map_all.get(rec.id, 0)
            rec.open_appointment_count = map_open.get(rec.id, 0)
            rec.no_show_count = map_ns.get(rec.id, 0)

            last_done = App.search(
                [("patient_id", "=", rec.id), ("state", "=", "done")],
                order="end desc", limit=1
            )
            rec.last_appointment_id = last_done.id if last_done else False

            upcoming = App.search(
                [("patient_id", "=", rec.id), ("start", ">=", now), ("state", "not in", ["canceled", "no_show"])],
                order="start asc", limit=1
            )
            rec.upcoming_appointment_id = upcoming.id if upcoming else False

    def _compute_primary_doctor_mirrors(self):
        for rec in self:
            doc = rec.primary_doctor_id
            if doc:
                # Next availability (if availability model exists)
                if "clinic.availability.slot" in self.env:
                    slot = self.env["clinic.availability.slot"].search([
                        ("doctor_id", "=", doc.id),
                        ("state", "=", "open") if "state" in self.env["clinic.availability.slot"]._fields else ("id", "!=", 0),
                        ("start", ">=", fields.Datetime.now()),
                    ], order="start asc", limit=1)
                    rec.next_available_slot_primary_doctor = slot.start if slot else False
                else:
                    rec.next_available_slot_primary_doctor = False
                # Default room mirror (if present on doctor)
                rec.primary_doctor_room = getattr(doc, "default_room_id", False) and doc.default_room_id.id or False
            else:
                rec.next_available_slot_primary_doctor = False
                rec.primary_doctor_room = False

    # -------------------------------------------------------------------------
    # ONCHANGES & CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.onchange("primary_doctor_id")
    def _onchange_primary_doctor_id(self):
        for rec in self:
            if rec.primary_doctor_id and rec.primary_doctor_id not in rec.preferred_doctor_ids:
                # Keep primary contained within preferred as soft policy
                rec.preferred_doctor_ids = [(4, rec.primary_doctor_id.id)]

    @api.constrains("primary_doctor_id")
    def _check_primary_doctor_company(self):
        """
        Optional soft guard: In multi-company setups, warn when primary doctor belongs
        to a different company than the patient's company (if such field exists).
        We only post a message to avoid friction.
        """
        for rec in self:
            if rec.primary_doctor_id and rec.company_id and rec.primary_doctor_id.company_id != rec.company_id:
                rec.message_post(body=_(
                    "Primary doctor is assigned from a different company (%s). "
                    "Please ensure this is intended."
                ) % rec.primary_doctor_id.company_id.display_name)

    # -------------------------------------------------------------------------
    # ACTIONS
    # -------------------------------------------------------------------------
    def action_view_appointments(self):
        """Open all appointments of this patient."""
        self.ensure_one()
        if "clinic.appointment" not in self.env:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {"title": _("Not Available"),
                           "message": _("Appointment module is not installed."),
                           "sticky": False},
            }
        return {
            "type": "ir.actions.act_window",
            "name": _("Appointments"),
            "res_model": "clinic.appointment",
            "view_mode": "calendar,tree,form,pivot,graph",
            "domain": [("patient_id", "=", self.id)],
            "target": "current",
        }

    def action_book_with_primary_doctor(self):
        """
        Open appointment form pre-filled with patient & primary doctor.
        If no primary doctor, open with patient only.
        """
        self.ensure_one()
        if "clinic.appointment" not in self.env:
            return {"type": "ir.actions.client", "tag": "display_notification",
                    "params": {"title": _("Not Available"),
                               "message": _("Appointment module is not installed."),
                               "sticky": False}}
        ctx = {
            "default_patient_id": self.id,
            "default_partner_id": self.partner_id.id if "partner_id" in self._fields and self.partner_id else False,
            "default_company_id": self.company_id.id if "company_id" in self._fields else False,
        }
        if self.primary_doctor_id:
            ctx["default_doctor_id"] = self.primary_doctor_id.id
            # Preselect room/specialty if available
            if "default_room_id" in self.primary_doctor_id._fields and self.primary_doctor_id.default_room_id:
                ctx["default_room_id"] = self.primary_doctor_id.default_room_id.id
        return {
            "type": "ir.actions.act_window",
            "name": _("Book Appointment"),
            "res_model": "clinic.appointment",
            "view_mode": "form",
            "target": "current",
            "context": ctx,
        }

    def action_view_preferred_doctors(self):
        """Open preferred doctors of this patient."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Preferred Doctors"),
            "res_model": "clinic.doctor",
            "view_mode": "tree,form,kanban,calendar",
            "domain": [("id", "in", self.preferred_doctor_ids.ids)],
            "target": "current",
        }


# -----------------------------------------------------------------------------
# EXTEND: clinic.doctor (backlink & actions) # dipindah ke file doctor.py masih dalam 1 addon
# -----------------------------------------------------------------------------
# class ClinicDoctor(models.Model):
#     _inherit = "clinic.doctor"

#     patient_ids = fields.Many2many(
#         "clinic.patient",
#         "clinic_patient_doctor_rel",      # same M2M table
#         "doctor_id",
#         "patient_id",
#         string="Patients",
#         help="Patients that marked this doctor as preferred (or primary)."
#     )
#     patient_count = fields.Integer(
#         compute="_compute_patient_count",
#         store=False,
#         help="Number of patients that prefer this doctor."
#     )

#     def _compute_patient_count(self):
#         for rec in self:
#             rec.patient_count = len(rec.patient_ids)

#     def action_view_patients(self):
#         self.ensure_one()
#         return {
#             "type": "ir.actions.act_window",
#             "name": _("Patients"),
#             "res_model": "clinic.patient",
#             "view_mode": "tree,form,kanban",
#             "domain": [("id", "in", self.patient_ids.ids)],
#             "target": "current",
#         }

#     def action_view_primary_patients(self):
#         """Open patients for whom this doctor is the primary doctor."""
#         self.ensure_one()
#         return {
#             "type": "ir.actions.act_window",
#             "name": _("Primary Patients"),
#             "res_model": "clinic.patient",
#             "view_mode": "tree,form,kanban",
#             "domain": [("primary_doctor_id", "=", self.id)],
#             "target": "current",
#         }


# -----------------------------------------------------------------------------
# EXTEND: clinic.appointment (partner ↔ patient consistency)
# -----------------------------------------------------------------------------
# class ClinicAppointment(models.Model):
#     _inherit = "clinic.appointment"

#     # NOTE: field patient_id is already defined in clinic_doctor/models/appointment.py.
#     # Here we only add consistency guards and convenience behavior.

#     @api.onchange("partner_id")
#     def _onchange_partner_bind_patient(self):
#         """
#         When a partner is chosen, bind the patient record automatically if:
#           - There is exactly one patient with that partner
#           - Or system parameter allows auto-create when none exists
#         """
#         Param = self.env["ir.config_parameter"].sudo()
#         auto_create = Param.get_param("clinic_doctor.auto_create_patient_on_appointment", "False") == "True"

#         for rec in self:
#             if not rec.partner_id:
#                 rec.patient_id = False
#                 continue
#             Patient = self.env["clinic.patient"]
#             candidates = Patient.search([("partner_id", "=", rec.partner_id.id)], limit=2)
#             if len(candidates) == 1:
#                 rec.patient_id = candidates.id
#             elif len(candidates) == 0 and auto_create:
#                 # Create patient shell linked to this partner
#                 patient = Patient.create({
#                     "name": rec.partner_id.name,
#                     "partner_id": rec.partner_id.id,
#                     "company_id": rec.company_id.id if rec.company_id else self.env.company.id,
#                 })
#                 rec.patient_id = patient.id
#             else:
#                 # multiple candidates — do nothing, let user choose
#                 rec.patient_id = False

#     @api.constrains("partner_id", "patient_id")
#     def _check_partner_patient_consistency(self):
#         """
#         Ensure appointment.partner_id matches patient.partner_id (if patient is set).
#         """
#         for rec in self:
#             if rec.patient_id and rec.partner_id and rec.patient_id.partner_id and rec.patient_id.partner_id != rec.partner_id:
#                 raise ValidationError(_("Appointment contact does not match the selected patient."))
