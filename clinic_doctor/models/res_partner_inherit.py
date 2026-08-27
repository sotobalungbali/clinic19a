
# -*- coding: utf-8 -*-
# File: clinic_doctor/models/res_partner_inherit.py
# Module: clinic_doctor
#
# ClinicOne — res.partner extensions for Doctor Management (Odoo 19 CE ready)
#
# Purpose
# -------
# - Flag a contact as a Doctor (is_doctor)
# - Show linked Doctor records (company-aware), counters & next availability
# - Quick actions to open/create doctor records
# - Optional cross-module counters (appointments, treatments) guarded by presence checks
#
# Notes
# -----
# - This file does NOT create hard dependencies on other ClinicOne modules.
# - All strings are in English (product requirement).
# - Multi-company aware: one partner can be a doctor in multiple companies via multiple clinic.doctor records.

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    # -------------------------------------------------------------------------
    # DOCTOR FLAG & LINKS
    # -------------------------------------------------------------------------
    # SUDH DIPINDAH ke clinic_audit
    # is_doctor = fields.Boolean(
    #     string="Is a Doctor",
    #     help="Enable this to indicate that this contact is a doctor."
    # )
    doctor_ids = fields.One2many(
        "clinic.doctor",
        "partner_id",
        string="Doctor Records",
        help="Doctor records referencing this contact (one per company)."
    )
    doctor_count = fields.Integer(
        compute="_compute_doctor_links",
        store=False,
        help="Number of doctor records linked to this contact."
    )
    doctor_current_company_id = fields.Many2one(
        "clinic.doctor",
        compute="_compute_doctor_links",
        store=False,
        string="Doctor (Current Company)",
        help="Doctor record for the current company, if any."
    )

    # Convenience mirrors for current company doctor
    doctor_license_no = fields.Char(
        compute="_compute_doctor_links",
        store=False,
        help="License number from the current company's doctor record."
    )
    doctor_seniority = fields.Selection(
        [
            ("resident", "Resident"),
            ("junior", "Junior"),
            ("senior", "Senior"),
            ("consultant", "Consultant"),
        ],
        compute="_compute_doctor_links",
        store=False,
        help="Seniority level from the current company's doctor record."
    )
    doctor_specialty_names = fields.Char(
        compute="_compute_doctor_links",
        store=False,
        help="Comma-separated specialty names from the current company's doctor record."
    )

    # -------------------------------------------------------------------------
    # DOCTOR-CENTRIC KPIs (CURRENT COMPANY CONTEXT)
    # -------------------------------------------------------------------------
    appointment_count_as_doctor = fields.Integer(
        compute="_compute_doctor_kpis",
        store=False,
        help="Number of appointments where this contact acts as the doctor (current company)."
    )
    open_appointment_count_as_doctor = fields.Integer(
        compute="_compute_doctor_kpis",
        store=False,
        help="Number of non-closed appointments for this doctor (current company)."
    )
    next_available_slot_as_doctor = fields.Datetime(
        compute="_compute_doctor_kpis",
        store=False,
        help="Next available slot for this doctor (current company), if the availability module is installed."
    )
    treatment_session_count_as_doctor = fields.Integer(
        compute="_compute_doctor_kpis",
        store=False,
        help="Number of treatment sessions performed by this doctor (current company; if the model exists)."
    )

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    def _compute_doctor_links(self):
        """
        Compute:
          - doctor_count
          - doctor_current_company_id
          - doctor_license_no, doctor_seniority, doctor_specialty_names
        """
        company = self.env.company
        for rec in self:
            docs = rec.doctor_ids
            rec.doctor_count = len(docs)
            # current company doctor (there should be 0..1 by uniqueness in clinic.doctor)
            cur = docs.filtered(lambda d: d.company_id == company)[:1]
            rec.doctor_current_company_id = cur.id if cur else False

            # mirrors
            if cur:
                rec.doctor_license_no = cur.license_no or ""
                rec.doctor_seniority = cur.seniority_level or False
                rec.doctor_specialty_names = ", ".join(cur.mapped("specialty_ids.complete_name"))
            else:
                rec.doctor_license_no = ""
                rec.doctor_seniority = False
                rec.doctor_specialty_names = ""

    def _compute_doctor_kpis(self):
        """
        Compute KPIs for the current company doctor context:
          - appointments (all & open)
          - next availability
          - treatment session count (optional)
        """
        # Batch map partner_id -> doctor_id for current company
        partner_to_doc = {}
        for p in self:
            d = p.doctor_ids.filtered(lambda r: r.company_id == self.env.company)[:1]
            partner_to_doc[p.id] = d.id if d else False

        # Pre-fill zeros
        for rec in self:
            rec.appointment_count_as_doctor = 0
            rec.open_appointment_count_as_doctor = 0
            rec.treatment_session_count_as_doctor = 0
            rec.next_available_slot_as_doctor = False

        # Appointments (optional)
        if "clinic.appointment" in self.env:
            App = self.env["clinic.appointment"]
            doc_ids = [d for d in partner_to_doc.values() if d]
            if doc_ids:
                # all appointments
                g_all = App.read_group(
                    [("doctor_id", "in", doc_ids)],
                    ["doctor_id"],
                    ["doctor_id"],
                )
                map_all = {g["doctor_id"][0]: g["doctor_id_count"] for g in g_all}
                # open appointments (exclude terminal states)
                g_open = App.read_group(
                    [("doctor_id", "in", doc_ids), ("state", "not in", ["canceled", "done", "no_show"])],
                    ["doctor_id"],
                    ["doctor_id"],
                )
                map_open = {g["doctor_id"][0]: g["doctor_id_count"] for g in g_open}
                # assign to partner
                for rec in self:
                    did = partner_to_doc.get(rec.id)
                    if did:
                        rec.appointment_count_as_doctor = map_all.get(did, 0)
                        rec.open_appointment_count_as_doctor = map_open.get(did, 0)

        # Treatment sessions (optional)
        # if "clinic.procedure.session" in self.env:
        #     Sess = self.env["clinic.procedure.session"]
        #     doc_ids = [d for d in partner_to_doc.values() if d]
        #     if doc_ids:
        #         g_ts = Sess.read_group(
        #             [("doctor_id", "in", doc_ids)],
        #             ["doctor_id"],
        #             ["doctor_id"],
        #         )
        #         map_ts = {g["doctor_id"][0]: g["doctor_id_count"] for g in g_ts}
        #         for rec in self:
        #             did = partner_to_doc.get(rec.id)
        #             if did:
        #                 rec.treatment_session_count_as_doctor = map_ts.get(did, 0)

        # Next availability (optional)
        if "clinic.availability.slot" in self.env:
            Slot = self.env["clinic.availability.slot"]
            now = fields.Datetime.now()
            for rec in self:
                did = partner_to_doc.get(rec.id)
                if not did:
                    continue
                slot = Slot.search([
                    ("doctor_id", "=", did),
                    ("state", "=", "open") if "state" in Slot._fields else ("id", "!=", 0),
                    ("start", ">=", now),
                ], order="start asc", limit=1)
                rec.next_available_slot_as_doctor = slot.start if slot else False

    # -------------------------------------------------------------------------
    # BEHAVIOR — KEEP FLAG & LINKS CONSISTENT
    # -------------------------------------------------------------------------
    def _toggle_is_doctor_effects(self, new_value):
        """
        When toggling is_doctor off, deactivate doctor records for the current company.
        When toggling on, do nothing (doctor records are created from Doctor module to ensure license completeness).
        Behavior can be tuned via system parameters:
          - clinic_doctor.deactivate_doctor_on_unflag = True/False (default True)
        """
        Param = self.env["ir.config_parameter"].sudo()
        deactivate = Param.get_param("clinic_doctor.deactivate_doctor_on_unflag", "True") == "True"

        for rec in self:
            if not new_value and deactivate:
                doctors = rec.doctor_ids.filtered(lambda d: d.company_id == self.env.company and d.active)
                for d in doctors:
                    d.active = False

    def write(self, vals):
        # Intercept is_doctor flips for behavior
        flip = "is_doctor" in vals
        res = super().write(vals)
        if flip:
            # Apply effects per record (vals['is_doctor'] is uniform for all in self)
            self._toggle_is_doctor_effects(bool(vals.get("is_doctor")))
        return res

    # -------------------------------------------------------------------------
    # QUICK ACTIONS
    # -------------------------------------------------------------------------
    def action_view_doctor_records(self):
        """
        Open clinic.doctor records linked to this partner.
        """
        self.ensure_one()
        if "clinic.doctor" not in self.env:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {"title": _("Not Available"),
                           "message": _("Doctor module is not installed."),
                           "sticky": False},
            }
        return {
            "type": "ir.actions.act_window",
            "name": _("Doctor Records"),
            "res_model": "clinic.doctor",
            "view_mode": "list,form,kanban",
            "domain": [("partner_id", "=", self.id)],
            "target": "current",
            "context": {
                "default_partner_id": self.id,
            },
        }

    def action_open_current_company_doctor(self):
        """
        Open the doctor record for the current company (if any),
        otherwise open the create form with defaults.
        """
        self.ensure_one()
        if "clinic.doctor" not in self.env:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {"title": _("Not Available"),
                           "message": _("Doctor module is not installed."),
                           "sticky": False},
            }
        doc = self.doctor_ids.filtered(lambda d: d.company_id == self.env.company)[:1]
        if doc:
            return {
                "type": "ir.actions.act_window",
                "name": _("Doctor"),
                "res_model": "clinic.doctor",
                "view_mode": "form",
                "res_id": doc.id,
                "target": "current",
            }
        # else open create form
        return {
            "type": "ir.actions.act_window",
            "name": _("Create Doctor"),
            "res_model": "clinic.doctor",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_partner_id": self.id,
                "default_company_id": self.env.company.id,
            },
        }

    def action_view_doctor_appointments(self):
        """
        Open appointments where this contact acts as a doctor (current company).
        """
        self.ensure_one()
        if "clinic.appointment" not in self.env:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {"title": _("Not Available"),
                           "message": _("Appointment module is not installed."),
                           "sticky": False},
            }
        # Resolve current company doctor
        doc = self.doctor_ids.filtered(lambda d: d.company_id == self.env.company)[:1]
        if not doc:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {"title": _("No Doctor"),
                           "message": _("This contact has no doctor record in the current company."),
                           "sticky": False},
            }
        return {
            "type": "ir.actions.act_window",
            "name": _("Appointments"),
            "res_model": "clinic.appointment",
            "view_mode": "calendar,list,form,pivot,graph",
            "domain": [("doctor_id", "=", doc.id)],
            "target": "current",
        }

    def action_view_next_availability(self):
        """
        Show the next available slot for this doctor (current company), if availability model exists.
        """
        self.ensure_one()
        if "clinic.availability.slot" not in self.env:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {"title": _("Not Available"),
                           "message": _("Availability module is not installed."),
                           "sticky": False},
            }
        doc = self.doctor_ids.filtered(lambda d: d.company_id == self.env.company)[:1]
        if not doc:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {"title": _("No Doctor"),
                           "message": _("This contact has no doctor record in the current company."),
                           "sticky": False},
            }
        domain = [("doctor_id", "=", doc.id)]
        if "state" in self.env["clinic.availability.slot"]._fields:
            domain += [("state", "=", "open")]
        if self.next_available_slot_as_doctor:
            domain += [("start", ">=", self.next_available_slot_as_doctor)]
        return {
            "type": "ir.actions.act_window",
            "name": _("Availability"),
            "res_model": "clinic.availability.slot",
            "view_mode": "calendar,list,form",
            "domain": domain,
            "target": "current",
        }

    # -------------------------------------------------------------------------
    # OPTIONAL HR BRIDGE (READ-ONLY MIRRORS)
    # -------------------------------------------------------------------------
    hr_employee_id = fields.Many2one(
        "hr.employee",
        compute="_compute_hr_bridge",
        store=False,
        string="Employee (Bridge)",
        help="Employee record linked via clinic_doctor_hr bridge (if installed and configured)."
    )
    has_hr_employee = fields.Boolean(
        compute="_compute_hr_bridge",
        store=False,
        help="True if this contact is a doctor and has a linked employee via the HR bridge."
    )

    def _compute_hr_bridge(self):
        """
        Expose HR employee linkage if bridge is installed.
        The bridge typically places employee_id on clinic.doctor.
        """
        for rec in self:
            rec.hr_employee_id = False
            rec.has_hr_employee = False
            if "hr.employee" not in self.env or "clinic.doctor" not in self.env:
                continue
            # read from current company doctor
            doc = rec.doctor_ids.filtered(lambda d: d.company_id == self.env.company)[:1]
            if doc and "employee_id" in doc._fields and doc.employee_id:
                rec.hr_employee_id = doc.employee_id.id
                rec.has_hr_employee = True

    # -------------------------------------------------------------------------
    # CONVENIENCE: VALIDATION / HELPERS
    # -------------------------------------------------------------------------
    @api.constrains("is_company", "is_doctor")
    def _check_is_company_flag(self):
        """
        Soft policy: a doctor contact should ideally be an individual (person), not a company.
        Enforce as ValidationError if you want hard policy; here we only warn in chatter.
        """
        for rec in self:
            if rec.is_doctor and rec.is_company:
                # Post a message instead of blocking to avoid friction in data imports
                rec.message_post(body=_(
                    "This contact is flagged as a Doctor but is marked as a Company. "
                    "It is recommended to use an individual contact for doctors."
                ))

    # Public helper
    def get_current_company_doctor(self):
        """
        Return the clinic.doctor record for this partner in the current company, or False.
        """
        self.ensure_one()
        return self.doctor_ids.filtered(lambda d: d.company_id == self.env.company)[:1] or False
