# -*- coding: utf-8 -*-
# ClinicOne — clinic_encounter
# Human-friendly navigation helpers used by enterprise One2many views.

from odoo import models


def _open_record(record, *, name):
    record.ensure_one()
    return {
        "type": "ir.actions.act_window",
        "name": name,
        "res_model": record._name,
        "res_id": record.id,
        "view_mode": "form",
        "views": [(False, "form")],
        "target": "current",
    }


class ClinicChecklistItemNavigation(models.Model):
    _inherit = "clinic.checklist.item"

    def action_open_checklist(self):
        self.ensure_one()
        return _open_record(self.checklist_id, name="Checklist")


class ClinicResultValueNavigation(models.Model):
    _inherit = "clinic.result.value"

    def action_open_result(self):
        self.ensure_one()
        return _open_record(self.result_id, name="Result Document")


class ClinicConsentRiskNavigation(models.Model):
    _inherit = "clinic.consent.risk"

    def action_open_consent(self):
        self.ensure_one()
        return _open_record(self.consent_id, name="Consent Document")


class ClinicProcedureConsumableNavigation(models.Model):
    _inherit = "clinic.procedure.consumable"

    def action_open_procedure(self):
        self.ensure_one()
        return _open_record(self.procedure_id, name="Procedure Catalog")


class ClinicAnesthesiaMedicationNavigation(models.Model):
    _inherit = "clinic.anesthesia.medication"

    def action_open_case(self):
        self.ensure_one()
        return _open_record(self.case_id, name="Anesthesia Case")


class ClinicAnesthesiaVitalNavigation(models.Model):
    _inherit = "clinic.anesthesia.vital"

    def action_open_case(self):
        self.ensure_one()
        return _open_record(self.case_id, name="Anesthesia Case")


class ClinicAnesthesiaFluidNavigation(models.Model):
    _inherit = "clinic.anesthesia.fluid"

    def action_open_case(self):
        self.ensure_one()
        return _open_record(self.case_id, name="Anesthesia Case")


class ClinicAnesthesiaAirwayNavigation(models.Model):
    _inherit = "clinic.anesthesia.airway"

    def action_open_case(self):
        self.ensure_one()
        return _open_record(self.case_id, name="Anesthesia Case")


class ClinicAnesthesiaEventNavigation(models.Model):
    _inherit = "clinic.anesthesia.event"

    def action_open_case(self):
        self.ensure_one()
        return _open_record(self.case_id, name="Anesthesia Case")


class ClinicAdverseEventActionNavigation(models.Model):
    _inherit = "clinic.ae.action"

    def action_open_adverse_event(self):
        self.ensure_one()
        return _open_record(self.ae_id, name="Adverse Event")


class ClinicAdverseEventFollowupNavigation(models.Model):
    _inherit = "clinic.ae.followup"

    def action_open_adverse_event(self):
        self.ensure_one()
        return _open_record(self.ae_id, name="Adverse Event")


class ClinicProcedureStepChecklistNavigation(models.Model):
    _inherit = "clinic.procedure.step.checklist"

    def action_open_step(self):
        self.ensure_one()
        return _open_record(self.step_id, name="Procedure Step")


class ClinicChecklistTemplateItemNavigation(models.Model):
    _inherit = "clinic.checklist.template.item"

    def action_open_template(self):
        self.ensure_one()
        return _open_record(self.template_id, name="Checklist Template")


class ClinicChecklistTemplateItemOptionNavigation(models.Model):
    _inherit = "clinic.checklist.template.item.option"

    def action_open_item(self):
        self.ensure_one()
        return _open_record(self.item_id, name="Checklist Template Item")
