# -*- coding: utf-8 -*-
"""
ClinicOne eMAR - Core Model: Alert
Model: clinic.emar.alert

Goals
-----
- Centralize clinical/operational alerts for the eMAR domain.
- Link alerts to Patient/Doctor/Product and eMAR artifacts (Prescription/Order/Schedule/Administration/Line).
- Provide deduplication via a stable digest and convenient upsert helpers.
- Offer standard workflow: open → acknowledged → resolved/dismissed, plus snooze.
- Soft-coupled design: references are optional and guarded by helpers in higher layers.

Compatibility
-------------
- Odoo 19 CE
- ClinicOne ecosystem (~38 addons)

"""

import hashlib
from datetime import datetime, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


# =============================================================================
# Utilities
# =============================================================================
def _get_model(env, model_name):
    try:
        return env[model_name]
    except Exception:
        return None


def _has_field(record_or_model, field_name):
    return hasattr(record_or_model, "_fields") and field_name in record_or_model._fields


def _now():
    return fields.Datetime.now()


def _to_int(val):
    try:
        return int(val) if val else 0
    except Exception:
        return 0


# =============================================================================
# Core Model
# =============================================================================
class ClinicEmarAlert(models.Model):
    _name = "clinic.emar.alert"
    _description = "ClinicOne eMAR Alert"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "clinic.emar.mixin.audit",  # abstract mixin (safe)
    ]
    _order = "severity desc, detected_on desc, id desc"
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Identity & Dedup
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Alert",
        compute="_compute_name",
        store=True,
        help="Human-readable title composed from severity, type, patient, and product."
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Uncheck to archive this alert."
    )
    digest = fields.Char(
        string="Digest",
        index=True,
        copy=False,
        help="Stable hash used for deduplicating the same alert context."
    )
    source_key = fields.Char(
        string="Source Key",
        help="Optional external key from the originating system/rule to help deduplication."
    )
    occurrence_count = fields.Integer(
        string="Occurrences",
        default=1,
        help="How many times the same condition has been observed."
    )
    first_seen_on = fields.Datetime(
        string="First Seen",
        default=_now,
        help="First detection time of this alert."
    )
    last_seen_on = fields.Datetime(
        string="Last Seen",
        default=_now,
        help="Last time the same alert was detected."
    )

    # -------------------------------------------------------------------------
    # Context & Links
    # -------------------------------------------------------------------------
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        index=True,
        default=lambda self: self.env.company,
    )
    patient_id = fields.Many2one(
        "clinic.patient",
        string="Patient",
        index=True,
        help="Patient involved in this alert."
    )
    doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Doctor",
        index=True,
        help="Doctor associated to this alert context (if any)."
    )
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        index=True,
        help="Medication/consumable/service related to this alert (if any)."
    )
    lot_id = fields.Many2one(
        "stock.lot",
        string="Lot/Serial",
        help="Lot/serial implicated in this alert (e.g., expired lot)."
    )

    prescription_id = fields.Many2one(
        "clinic.emar.prescription",
        string="Prescription",
        index=True,
        help="Linked eMAR Prescription if the alert originates there."
    )
    order_id = fields.Many2one(
        "clinic.emar.order",
        string="Order",
        index=True,
        help="Linked eMAR Order if the alert originates there."
    )
    schedule_id = fields.Many2one(
        "clinic.emar.schedule",
        string="Schedule",
        index=True,
        help="Linked eMAR Schedule if the alert originates there."
    )
    administration_id = fields.Many2one(
        "clinic.emar.administration",
        string="Administration",
        index=True,
        help="Linked eMAR Administration if the alert originates there."
    )
    line_id = fields.Many2one(
        "clinic.emar.medication.line",
        string="Medication Line",
        index=True,
        help="Linked eMAR Medication Line if the alert originates there."
    )

    # Optional external pointers
    source_model = fields.Char(
        string="Source Model",
        help="Optional name of the model that triggered the alert (for traceability)."
    )
    source_ref = fields.Char(
        string="Source Reference",
        help="Optional record name/identifier from the source model."
    )

    # -------------------------------------------------------------------------
    # Classification
    # -------------------------------------------------------------------------
    alert_type = fields.Selection(
        [
            ("allergy", "Allergy"),
            ("interaction", "Drug Interaction"),
            ("contra", "Contraindication"),
            ("dose_limit", "Dose Limit Exceeded"),
            ("duplicate_therapy", "Duplicate Therapy"),
            ("time_window", "Time Window Breach"),
            ("missed_dose", "Missed Dose"),
            ("inventory_shortage", "Inventory Shortage"),
            ("lot_expired", "Lot Expired"),
            ("billing_issue", "Billing Issue"),
            ("other", "Other"),
        ],
        string="Type",
        required=True,
        index=True,
        default="other",
        help="Classification of the alert."
    )
    severity = fields.Selection(
        [
            ("info", "Info"),
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
            ("critical", "Critical"),
        ],
        string="Severity",
        required=True,
        index=True,
        default="medium",
        help="Severity level of the alert."
    )

    # -------------------------------------------------------------------------
    # Lifecycle & Ownership
    # -------------------------------------------------------------------------
    state = fields.Selection(
        [
            ("open", "Open"),
            ("ack", "Acknowledged"),
            ("resolved", "Resolved"),
            ("dismissed", "Dismissed"),
        ],
        string="Status",
        required=True,
        index=True,
        default="open",
        tracking=True,
    )
    detected_on = fields.Datetime(
        string="Detected On",
        default=_now,
        help="When the alert was detected."
    )
    acknowledged_on = fields.Datetime(
        string="Acknowledged On"
    )
    resolved_on = fields.Datetime(
        string="Resolved On"
    )
    dismissed_on = fields.Datetime(
        string="Dismissed On"
    )

    responsible_user_id = fields.Many2one(
        "res.users",
        string="Responsible",
        help="User responsible for following up this alert."
    )
    assigned_user_id = fields.Many2one(
        "res.users",
        string="Assigned To",
        help="User assigned to take action on this alert."
    )
    assigned_team_id = fields.Many2one(
        "crm.team",
        string="Assigned Team",
        help="Team assigned to this alert (optional; use Sales Team as a generic team model)."
    )

    # Snooze
    snooze_until = fields.Datetime(
        string="Snooze Until",
        help="Temporarily silence this alert until the specified date/time."
    )
    is_snoozed = fields.Boolean(
        string="Snoozed",
        compute="_compute_is_snoozed",
        help="True if current time is before Snooze Until."
    )

    # -------------------------------------------------------------------------
    # Message
    # -------------------------------------------------------------------------
    headline = fields.Char(
        string="Headline",
        help="Short alert title (optional override for computed name)."
    )
    description = fields.Text(
        string="Description",
        help="Detailed description of the condition that triggered the alert."
    )
    recommendation = fields.Text(
        string="Recommendation",
        help="Suggested action(s) to remediate this alert."
    )

    # Optional numeric context (for shortages, ceilings, etc.)
    expected_qty = fields.Float(
        string="Expected Qty",
        help="Expected quantity (e.g., planned dose or required stock)."
    )
    available_qty = fields.Float(
        string="Available Qty",
        help="Available quantity (e.g., available stock at detection time)."
    )
    threshold_qty = fields.Float(
        string="Threshold Qty",
        help="Threshold that was violated (e.g., max daily dose, min stock)."
    )

    # -------------------------------------------------------------------------
    # Odoo 19 SQL constraint
    # -------------------------------------------------------------------------
    _uniq_alert_digest = models.Constraint(
        "UNIQUE(digest)",
        "An identical alert already exists (digest uniqueness).",
    )

    # =========================================================================
    # COMPUTES
    # =========================================================================
    @api.depends("headline", "severity", "alert_type", "patient_id", "product_id")
    def _compute_name(self):
        for rec in self:
            if rec.headline:
                rec.name = rec.headline
                continue
            sev = dict(self._fields["severity"].selection).get(rec.severity, rec.severity or "")
            typ = dict(self._fields["alert_type"].selection).get(rec.alert_type, rec.alert_type or "")
            who = rec.patient_id.display_name if rec.patient_id else _("No Patient")
            what = rec.product_id.display_name if rec.product_id else _("Item")
            rec.name = "[%s] %s — %s — %s" % (sev.upper(), typ, who, what)

    @api.depends("snooze_until")
    def _compute_is_snoozed(self):
        now = _now()
        for rec in self:
            rec.is_snoozed = bool(rec.snooze_until and now < rec.snooze_until)

    # =========================================================================
    # HELPERS: Digest & Upsert
    # =========================================================================
    def _make_digest_values_tuple(self, vals):
        """Collect key parts for digest from vals dict (create/update context)."""
        return (
            _to_int(vals.get("company_id")),
            _to_int(vals.get("patient_id")),
            vals.get("alert_type") or "",
            _to_int(vals.get("product_id")),
            _to_int(vals.get("lot_id")),
            _to_int(vals.get("prescription_id")),
            _to_int(vals.get("order_id")),
            _to_int(vals.get("schedule_id")),
            _to_int(vals.get("administration_id")),
            _to_int(vals.get("line_id")),
            vals.get("source_key") or "",
        )

    def _make_digest_from_vals(self, vals):
        parts = self._make_digest_values_tuple(vals)
        raw = "|".join(map(str, parts))
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    def _make_digest_from_record(self, rec):
        vals = {
            "company_id": rec.company_id.id if rec.company_id else 0,
            "patient_id": rec.patient_id.id if rec.patient_id else 0,
            "alert_type": rec.alert_type or "",
            "product_id": rec.product_id.id if rec.product_id else 0,
            "lot_id": rec.lot_id.id if rec.lot_id else 0,
            "prescription_id": rec.prescription_id.id if rec.prescription_id else 0,
            "order_id": rec.order_id.id if rec.order_id else 0,
            "schedule_id": rec.schedule_id.id if rec.schedule_id else 0,
            "administration_id": rec.administration_id.id if rec.administration_id else 0,
            "line_id": rec.line_id.id if rec.line_id else 0,
            "source_key": rec.source_key or "",
        }
        return self._make_digest_from_vals(vals)

    @api.model
    def _upsert_get_domain(self, digest):
        return [("digest", "=", digest)]

    @api.model
    def upsert_alert(self, vals):
        """
        Create or update (deduplicate) an alert using its digest.
        - If a record with the same digest exists: increment occurrence_count, update last_seen_on,
          bump severity if higher, refresh description/recommendation/headline if provided, ensure 'open' state unless snoozed.
        - Else: create a new record.
        Returns: recordset (single record).
        """
        if not vals.get("company_id"):
            vals["company_id"] = self.env.company.id
        if not vals.get("detected_on"):
            vals["detected_on"] = _now()

        digest = vals.get("digest") or self._make_digest_from_vals(vals)
        vals["digest"] = digest

        existing = self.search(self._upsert_get_domain(digest), limit=1)
        if existing:
            updates = {
                "occurrence_count": existing.occurrence_count + 1,
                "last_seen_on": _now(),
            }
            # escalate severity if the new one is higher
            sev_order = ["info", "low", "medium", "high", "critical"]
            try:
                if vals.get("severity") and sev_order.index(vals["severity"]) > sev_order.index(existing.severity):
                    updates["severity"] = vals["severity"]
            except Exception:
                pass
            # refresh optional texts if provided
            for k in ("headline", "description", "recommendation"):
                if vals.get(k):
                    updates[k] = vals[k]
            # link updates if passed
            for k in ("order_id", "prescription_id", "schedule_id", "administration_id", "line_id", "product_id", "lot_id", "doctor_id"):
                if vals.get(k):
                    updates[k] = vals[k]
            # reopen if it was resolved/dismissed (policy: re-open on new occurrence)
            if existing.state in ("resolved", "dismissed"):
                updates["state"] = "open"
                updates["acknowledged_on"] = False
                updates["resolved_on"] = False
                updates["dismissed_on"] = False
            existing.write(updates)
            try:
                existing.message_post(body=_("Alert updated (occurrence #%s).") % existing.occurrence_count)
            except Exception:
                pass
            return existing
        # create new
        rec = self.create(vals)
        return rec

    # =========================================================================
    # ORM BASICS
    # =========================================================================
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("company_id"):
                vals["company_id"] = self.env.company.id
            if not vals.get("detected_on"):
                vals["detected_on"] = _now()
            if not vals.get("first_seen_on"):
                vals["first_seen_on"] = vals["detected_on"]
            vals["last_seen_on"] = vals.get("last_seen_on") or vals["detected_on"]
            # Precompute digest for SQL uniqueness
            vals["digest"] = vals.get("digest") or self._make_digest_from_vals(vals)
        recs = super().create(vals_list)
        return recs

    def write(self, vals):
        """Keep last_seen_on fresh if severity/state/headline/description changes significantly."""
        if any(k in vals for k in ("severity", "state", "headline", "description", "recommendation")):
            vals = dict(vals, last_seen_on=_now())
        res = super().write(vals)
        # Keep digest consistent if keys change (rare)
        digest_keys = {"company_id", "patient_id", "alert_type", "product_id", "lot_id",
                       "prescription_id", "order_id", "schedule_id", "administration_id", "line_id", "source_key"}
        if any(k in vals for k in digest_keys):
            for rec in self:
                new_digest = self._make_digest_from_record(rec)
                if rec.digest != new_digest:
                    rec.digest = new_digest
        return res

    # =========================================================================
    # CONSTRAINTS & ONCHANGE
    # =========================================================================
    @api.constrains("company_id", "patient_id", "order_id", "prescription_id", "schedule_id", "administration_id", "line_id")
    def _check_company_alignment(self):
        for rec in self:
            cmp = rec.company_id
            # verify across linked records (if they expose company_id)
            for ref in (rec.order_id, rec.prescription_id, rec.schedule_id, rec.administration_id, rec.line_id, rec.patient_id, rec.doctor_id):
                if ref and _has_field(ref, "company_id") and ref.company_id and ref.company_id != cmp:
                    raise ValidationError(_("Company mismatch between the alert and its related record(s)."))

    @api.constrains("alert_type", "severity")
    def _check_basic_fields(self):
        for rec in self:
            if not rec.alert_type:
                raise ValidationError(_("Alert Type is required."))
            if not rec.severity:
                raise ValidationError(_("Severity is required."))

    @api.onchange("order_id", "prescription_id", "schedule_id", "administration_id", "line_id")
    def _onchange_context_links(self):
        for rec in self:
            # Patient
            if not rec.patient_id:
                for obj in (rec.administration_id, rec.schedule_id, rec.order_id, rec.prescription_id, rec.line_id):
                    if obj and _has_field(obj, "patient_id") and obj.patient_id:
                        rec.patient_id = obj.patient_id
                        break
            # Doctor
            if not rec.doctor_id:
                for obj in (rec.administration_id, rec.schedule_id, rec.order_id, rec.prescription_id, rec.line_id):
                    if obj and _has_field(obj, "doctor_id") and obj.doctor_id:
                        rec.doctor_id = obj.doctor_id
                        break
            # Product
            if not rec.product_id:
                for obj in (rec.line_id, rec.schedule_id, rec.administration_id):
                    if obj and _has_field(obj, "product_id") and obj.product_id:
                        rec.product_id = obj.product_id
                        break

    # =========================================================================
    # ACTIONS: Workflow
    # =========================================================================
    def action_acknowledge(self):
        for rec in self:
            if rec.state == "open":
                rec.write({"state": "ack", "acknowledged_on": _now()})
                rec._audit_log("state_change", message=_("Alert acknowledged."), changes=[{"field": "state", "old": "open", "new": "ack"}])
        return True

    def action_resolve(self, note=None):
        for rec in self:
            if rec.state in ("open", "ack"):
                vals = {"state": "resolved", "resolved_on": _now()}
                rec.write(vals)
                body = _("Alert resolved.")
                if note:
                    body += " " + _("Note: %s") % note
                try:
                    rec.message_post(body=body)
                except Exception:
                    pass
                rec._audit_log("state_change", message=_("Alert resolved."), changes=[{"field": "state", "old": "open/ack", "new": "resolved"}])
        return True

    def action_dismiss(self, reason=None):
        for rec in self:
            if rec.state in ("open", "ack"):
                vals = {"state": "dismissed", "dismissed_on": _now()}
                rec.write(vals)
                body = _("Alert dismissed.")
                if reason:
                    body += " " + _("Reason: %s") % reason
                try:
                    rec.message_post(body=body)
                except Exception:
                    pass
                rec._audit_log("state_change", message=_("Alert dismissed."), changes=[{"field": "state", "old": "open/ack", "new": "dismissed"}])
        return True

    def action_reopen(self):
        for rec in self:
            if rec.state in ("resolved", "dismissed"):
                rec.write({"state": "open", "acknowledged_on": False, "resolved_on": False, "dismissed_on": False})
                rec._audit_log("state_change", message=_("Alert reopened."), changes=[{"field": "state", "old": "resolved/dismissed", "new": "open"}])
        return True

    def action_snooze(self, minutes=30):
        for rec in self:
            until = _now() + timedelta(minutes=minutes or 30)
            rec.write({"snooze_until": until})
            try:
                rec.message_post(body=_("Alert snoozed for %s minutes.") % (minutes or 30))
            except Exception:
                pass
        return True

    def action_assign_to(self, user_id=False, team_id=False):
        for rec in self:
            vals = {}
            if user_id:
                vals["assigned_user_id"] = user_id
            if team_id:
                vals["assigned_team_id"] = team_id
            if vals:
                rec.write(vals)
        return True

    # =========================================================================
    # UI HELPERS
    # =========================================================================
    def name_get(self):
        res = []
        for rec in self:
            label = rec.name or _("Alert")
            res.append((rec.id, label))
        return res

    def action_open_related(self):
        """
        Open the most specific related record (Administration > Schedule > Order > Prescription).
        """
        self.ensure_one()
        if self.administration_id:
            return {
                "name": _("Administration"),
                "type": "ir.actions.act_window",
                "res_model": "clinic.emar.administration",
                "view_mode": "form",
                "res_id": self.administration_id.id,
            }
        if self.schedule_id:
            return {
                "name": _("Schedule"),
                "type": "ir.actions.act_window",
                "res_model": "clinic.emar.schedule",
                "view_mode": "form",
                "res_id": self.schedule_id.id,
            }
        if self.order_id:
            return {
                "name": _("Order"),
                "type": "ir.actions.act_window",
                "res_model": "clinic.emar.order",
                "view_mode": "form",
                "res_id": self.order_id.id,
            }
        if self.prescription_id:
            return {
                "name": _("Prescription"),
                "type": "ir.actions.act_window",
                "res_model": "clinic.emar.prescription",
                "view_mode": "form",
                "res_id": self.prescription_id.id,
            }
        raise UserError(_("No related document to open."))

    # =========================================================================
    # FACTORY HELPERS (Convenience)
    # =========================================================================
    @api.model
    def raise_allergy(self, patient, product=None, **kwargs):
        """
        Raise or update an Allergy alert.
        kwargs may include: order_id, prescription_id, schedule_id, administration_id, line_id,
                            severity, headline, description, recommendation, doctor_id, source_key.
        """
        vals = {
            "company_id": patient.company_id.id if _has_field(patient, "company_id") and patient.company_id else self.env.company.id,
            "patient_id": patient.id,
            "doctor_id": kwargs.get("doctor_id") or False,
            "product_id": product.id if product else False,
            "alert_type": "allergy",
            "severity": kwargs.get("severity") or "critical",
            "headline": kwargs.get("headline") or _("Allergy risk detected"),
            "description": kwargs.get("description") or _("The selected medication is contraindicated due to a documented allergy."),
            "recommendation": kwargs.get("recommendation") or _("Review patient's allergy list and choose an alternative."),
            "order_id": kwargs.get("order_id") or False,
            "prescription_id": kwargs.get("prescription_id") or False,
            "schedule_id": kwargs.get("schedule_id") or False,
            "administration_id": kwargs.get("administration_id") or False,
            "line_id": kwargs.get("line_id") or False,
            "source_key": kwargs.get("source_key") or "",
        }
        return self.upsert_alert(vals)

    @api.model
    def raise_lot_expired(self, patient, product, lot, **kwargs):
        """
        Raise or update a Lot Expired alert.
        """
        vals = {
            "company_id": patient.company_id.id if _has_field(patient, "company_id") and patient.company_id else self.env.company.id,
            "patient_id": patient.id,
            "product_id": product.id if product else False,
            "lot_id": lot.id if lot else False,
            "alert_type": "lot_expired",
            "severity": kwargs.get("severity") or "high",
            "headline": kwargs.get("headline") or _("Lot is expired"),
            "description": kwargs.get("description") or _("The selected lot/serial has passed its expiration date."),
            "recommendation": kwargs.get("recommendation") or _("Choose a valid lot/serial or replace the product."),
            "order_id": kwargs.get("order_id") or False,
            "schedule_id": kwargs.get("schedule_id") or False,
            "administration_id": kwargs.get("administration_id") or False,
            "line_id": kwargs.get("line_id") or False,
            "source_key": kwargs.get("source_key") or "",
        }
        return self.upsert_alert(vals)

    @api.model
    def raise_inventory_shortage(self, patient, product, expected_qty, available_qty, **kwargs):
        """
        Raise or update an Inventory Shortage alert.
        """
        vals = {
            "company_id": patient.company_id.id if _has_field(patient, "company_id") and patient.company_id else self.env.company.id,
            "patient_id": patient.id,
            "product_id": product.id if product else False,
            "alert_type": "inventory_shortage",
            "severity": kwargs.get("severity") or "medium",
            "headline": kwargs.get("headline") or _("Insufficient stock for administration"),
            "description": kwargs.get("description") or _("Available stock is below the required quantity."),
            "recommendation": kwargs.get("recommendation") or _("Adjust dose, substitute product, or procure stock."),
            "expected_qty": expected_qty,
            "available_qty": available_qty,
            "order_id": kwargs.get("order_id") or False,
            "schedule_id": kwargs.get("schedule_id") or False,
            "line_id": kwargs.get("line_id") or False,
            "source_key": kwargs.get("source_key") or "",
        }
        return self.upsert_alert(vals)

    @api.model
    def raise_time_window(self, schedule, kind="missed_dose", **kwargs):
        """
        Raise or update a Time Window / Missed Dose alert based on a schedule.
        kind: 'time_window' or 'missed_dose'
        """
        patient = schedule.patient_id if _has_field(schedule, "patient_id") else False
        product = schedule.product_id if _has_field(schedule, "product_id") else False
        vals = {
            "company_id": schedule.company_id.id if _has_field(schedule, "company_id") and schedule.company_id else self.env.company.id,
            "patient_id": patient.id if patient else False,
            "product_id": product.id if product else False,
            "order_id": schedule.order_id.id if schedule.order_id else False,
            "schedule_id": schedule.id,
            "line_id": schedule.line_id.id if schedule.line_id else False,
            "alert_type": kind if kind in ("time_window", "missed_dose") else "time_window",
            "severity": kwargs.get("severity") or ("high" if kind == "missed_dose" else "medium"),
            "headline": kwargs.get("headline") or (_("Dose missed") if kind == "missed_dose" else _("Time window breach")),
            "description": kwargs.get("description") or _("The planned administration did not occur within the acceptable time window."),
            "recommendation": kwargs.get("recommendation") or _("Escalate to responsible staff and reschedule if clinically appropriate."),
            "source_key": kwargs.get("source_key") or "",
        }
        return self.upsert_alert(vals)

    @api.model
    def raise_billing_issue(self, header_record, message=None, **kwargs):
        """
        Raise or update a Billing Issue alert from a header (Prescription/Order/Administration).
        """
        patient = None
        product = None
        order = prescription = schedule = administration = line = False

        # Resolve context generically
        if header_record._name == "clinic.emar.order":
            order = header_record.id
            patient = header_record.patient_id
        elif header_record._name == "clinic.emar.prescription":
            prescription = header_record.id
            patient = header_record.patient_id
        elif header_record._name == "clinic.emar.administration":
            administration = header_record.id
            patient = header_record.patient_id
            product = header_record.product_id
            line = header_record.line_id and header_record.line_id.id or False

        vals = {
            "company_id": header_record.company_id.id if _has_field(header_record, "company_id") and header_record.company_id else self.env.company.id,
            "patient_id": patient and patient.id or False,
            "product_id": product and product.id or False,
            "order_id": order,
            "prescription_id": prescription,
            "administration_id": administration,
            "line_id": line,
            "alert_type": "billing_issue",
            "severity": kwargs.get("severity") or "medium",
            "headline": kwargs.get("headline") or _("Billing issue detected"),
            "description": message or kwargs.get("description") or _("An issue occurred while preparing or posting the invoice."),
            "recommendation": kwargs.get("recommendation") or _("Check payer settings, fiscal position, and product accounts/taxes."),
            "source_key": kwargs.get("source_key") or "",
        }
        return self.upsert_alert(vals)
