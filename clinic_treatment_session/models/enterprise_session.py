# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class ClinicTreatmentSessionEnterprise(models.Model):
    """Enterprise workflow overlay for the historical Treatment Session model.

    The legacy model remains the public contract owner. This file only adds
    canonical ClinicOne links and hardens workflow semantics that were unsafe
    to enforce through UI visibility alone.
    """

    _inherit = "clinic.treatment.session"

    branch_id = fields.Many2one(
        "clinic.branch",
        string="Branch",
        index=True,
        check_company=True,
        tracking=True,
        domain="[('company_id', '=', company_id)]",
    )
    clinic_patient_id = fields.Many2one(
        "clinic.patient",
        string="Clinic Patient",
        compute="_compute_canonical_links",
        store=True,
        index=True,
        readonly=True,
    )
    doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Clinic Doctor",
        index=True,
        check_company=True,
        tracking=True,
    )
    encounter_id = fields.Many2one(
        "clinic.encounter",
        string="Encounter",
        index=True,
        check_company=True,
        tracking=True,
    )
    referral_id = fields.Many2one(
        "clinic.referral",
        string="Referral",
        index=True,
        check_company=True,
        tracking=True,
    )
    package_allocation_id = fields.Many2one(
        "clinic.package.allocation",
        string="Package Allocation",
        index=True,
        check_company=True,
        ondelete="restrict",
    )
    package_allocation_line_id = fields.Many2one(
        "clinic.package.allocation.line",
        string="Package Allocation Line",
        index=True,
        check_company=True,
        ondelete="restrict",
    )
    package_usage_id = fields.Many2one(
        "clinic.package.usage",
        string="Package Usage",
        compute="_compute_package_usage_id",
        readonly=True,
    )

    actual_start_datetime = fields.Datetime(
        string="Actual Start",
        tracking=True,
        copy=False,
        index=True,
    )
    actual_end_datetime = fields.Datetime(
        string="Actual End",
        tracking=True,
        copy=False,
        index=True,
    )
    execution_duration_minutes = fields.Float(
        string="Actual Duration (min)",
        compute="_compute_execution_metrics",
        store=True,
    )
    duration_variance_minutes = fields.Float(
        string="Duration Variance (min)",
        compute="_compute_execution_metrics",
        store=True,
    )

    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )
    amount_untaxed = fields.Monetary(
        compute="_compute_session_amounts",
        currency_field="currency_id",
        store=True,
    )
    amount_total = fields.Monetary(
        compute="_compute_session_amounts",
        currency_field="currency_id",
        store=True,
    )

    billing_invoice_id = fields.Many2one(
        "clinic.billing.invoice",
        string="Clinic Billing Invoice",
        index=True,
        check_company=True,
        copy=False,
    )
    billing_state = fields.Selection(
        related="billing_invoice_id.state",
        string="Billing Status",
        readonly=True,
    )
    is_fully_invoiced = fields.Boolean(
        string="Fully Invoiced / Paid",
        compute="_compute_is_fully_invoiced",
        store=True,
    )

    line_count = fields.Integer(compute="_compute_operational_counts")
    consumed_line_count = fields.Integer(compute="_compute_operational_counts")
    billable_line_count = fields.Integer(compute="_compute_operational_counts")
    stock_move_count = fields.Integer(compute="_compute_operational_counts")
    audit_event_count = fields.Integer(compute="_compute_operational_counts")

    _workflow_states = {
        "draft": {"confirmed", "in_progress", "done", "cancelled", "no_show"},
        "confirmed": {"in_progress", "done", "cancelled", "no_show"},
        "in_progress": {"done", "cancelled"},
        "done": set(),
        "no_show": set(),
        "cancelled": {"draft"},
    }

    @api.depends("patient_id")
    def _compute_canonical_links(self):
        for session in self:
            session.clinic_patient_id = (
                session.patient_id.patient_id
                if session.patient_id
                and "patient_id" in session.patient_id._fields
                else False
            )

    @api.depends("booking_id.package_usage_id")
    def _compute_package_usage_id(self):
        for session in self:
            session.package_usage_id = (
                session.booking_id.package_usage_id
                if session.booking_id
                and "package_usage_id" in session.booking_id._fields
                else False
            )

    @api.depends(
        "actual_start_datetime",
        "actual_end_datetime",
        "duration_planned",
    )
    def _compute_execution_metrics(self):
        for session in self:
            actual_minutes = 0.0
            if session.actual_start_datetime and session.actual_end_datetime:
                delta = (
                    session.actual_end_datetime
                    - session.actual_start_datetime
                )
                actual_minutes = max(
                    delta.total_seconds() / 60.0,
                    0.0,
                )

            session.execution_duration_minutes = actual_minutes
            session.duration_variance_minutes = (
                actual_minutes - (session.duration_planned or 0.0)
                if actual_minutes
                else 0.0
            )

    @api.depends(
        "line_ids.price_subtotal",
        "line_ids.price_total",
        "line_ids.is_billable",
        "line_ids.display_type",
    )
    def _compute_session_amounts(self):
        for session in self:
            billable = session.line_ids.filtered(
                lambda line: (
                    line.display_type == "line"
                    and line.is_billable
                )
            )
            session.amount_untaxed = sum(
                billable.mapped("price_subtotal")
            )
            session.amount_total = sum(
                billable.mapped("price_total")
            )

    @api.depends(
        "move_id.payment_state",
        "billing_invoice_id.state",
        "billing_invoice_id.payment_state",
    )
    def _compute_is_fully_invoiced(self):
        for session in self:
            standard_paid = bool(
                session.move_id
                and session.move_id.payment_state
                in ("paid", "in_payment")
            )
            clinic_paid = bool(
                session.billing_invoice_id
                and (
                    session.billing_invoice_id.state == "paid"
                    or session.billing_invoice_id.payment_state == "paid"
                )
            )
            session.is_fully_invoiced = standard_paid or clinic_paid

    def _compute_operational_counts(self):
        AuditEvent = self.env["clinic.audit.event"]
        for session in self:
            session.line_count = len(session.line_ids)
            session.consumed_line_count = len(
                session.line_ids.filtered(
                    lambda line: line.consumption_state == "consumed"
                )
            )
            session.billable_line_count = len(
                session.line_ids.filtered(
                    lambda line: (
                        line.display_type == "line"
                        and line.is_billable
                    )
                )
            )
            session.stock_move_count = len(
                session.line_ids.mapped("stock_move_id")
            )
            session.audit_event_count = AuditEvent.search_count(
                [
                    ("ref_model", "=", session._name),
                    ("ref_res_id", "=", session.id),
                ]
            )

    @api.constrains(
        "company_id",
        "branch_id",
        "doctor_id",
        "encounter_id",
        "referral_id",
        "package_allocation_id",
        "package_allocation_line_id",
    )
    def _check_enterprise_company_scope(self):
        for session in self:
            company = session.company_id
            for record, label in (
                (session.branch_id, _("Branch")),
                (session.doctor_id, _("Clinic Doctor")),
                (session.encounter_id, _("Encounter")),
                (session.referral_id, _("Referral")),
                (session.package_allocation_id, _("Package Allocation")),
                (
                    session.package_allocation_line_id,
                    _("Package Allocation Line"),
                ),
            ):
                if (
                    record
                    and "company_id" in record._fields
                    and record.company_id
                    and record.company_id != company
                ):
                    raise ValidationError(
                        _("%s belongs to another company.") % label
                    )

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for values in vals_list:
            vals = dict(values)
            self._prepare_enterprise_defaults(vals)
            prepared.append(vals)

        sessions = super().create(prepared)
        sessions._sync_enterprise_links_from_booking()
        sessions._sync_stage_with_state()
        return sessions

    def write(self, vals):
        # A status field is a workflow contract, not a free-edit selection.
        if (
            "state" in vals
            and not self.env.context.get(
                "clinic_treatment_session_workflow"
            )
        ):
            for session in self:
                session._check_state_transition(
                    session.state,
                    vals["state"],
                )

        result = super().write(vals)

        if "booking_id" in vals:
            self._sync_enterprise_links_from_booking()

        return result

    def _prepare_enterprise_defaults(self, vals):
        """Populate canonical scope from already-provided upstream records."""
        booking = (
            self.env["booking.booking"].browse(vals["booking_id"])
            if vals.get("booking_id")
            else False
        )
        patient = (
            self.env["res.partner"].browse(vals["patient_id"])
            if vals.get("patient_id")
            else booking.patient_id
            if booking
            else False
        )

        if booking:
            vals.setdefault("company_id", booking.company_id.id)

            if booking.doctor_id:
                vals.setdefault("doctor_id", booking.doctor_id.id)

            if "referral_id" in booking._fields and booking.referral_id:
                vals.setdefault("referral_id", booking.referral_id.id)

            if booking.appointment_id and not vals.get("encounter_id"):
                encounter = self.env["clinic.encounter"].search(
                    [
                        ("appointment_id", "=", booking.appointment_id.id),
                        ("company_id", "=", booking.company_id.id),
                    ],
                    order="id desc",
                    limit=1,
                )
                if encounter:
                    vals["encounter_id"] = encounter.id

            if (
                "package_allocation_id" in booking._fields
                and booking.package_allocation_id
            ):
                vals.setdefault(
                    "package_allocation_id",
                    booking.package_allocation_id.id,
                )

            if (
                "package_allocation_line_id" in booking._fields
                and booking.package_allocation_line_id
            ):
                vals.setdefault(
                    "package_allocation_line_id",
                    booking.package_allocation_line_id.id,
                )

        if patient and "branch_id" in patient._fields and patient.branch_id:
            vals.setdefault("branch_id", patient.branch_id.id)

    def _sync_enterprise_links_from_booking(self):
        """Backfill additive links without changing historical ownership."""
        for session in self:
            booking = session.booking_id
            if not booking:
                continue

            values = {}
            if booking.doctor_id and not session.doctor_id:
                values["doctor_id"] = booking.doctor_id.id

            if (
                "referral_id" in booking._fields
                and booking.referral_id
                and not session.referral_id
            ):
                values["referral_id"] = booking.referral_id.id

            if (
                booking.appointment_id
                and not session.encounter_id
            ):
                encounter = self.env["clinic.encounter"].search(
                    [
                        ("appointment_id", "=", booking.appointment_id.id),
                        ("company_id", "=", booking.company_id.id),
                    ],
                    order="id desc",
                    limit=1,
                )
                if encounter:
                    values["encounter_id"] = encounter.id

            if (
                "package_allocation_id" in booking._fields
                and booking.package_allocation_id
                and not session.package_allocation_id
            ):
                values["package_allocation_id"] = (
                    booking.package_allocation_id.id
                )

            if (
                "package_allocation_line_id" in booking._fields
                and booking.package_allocation_line_id
                and not session.package_allocation_line_id
            ):
                values["package_allocation_line_id"] = (
                    booking.package_allocation_line_id.id
                )

            if values:
                session.with_context(
                    clinic_treatment_session_workflow=True
                ).write(values)

    def _sync_stage_with_state(self):
        """Synchronize Kanban stage using the session company and state."""
        Stage = self.env["clinic.treatment.session.stage"].sudo()
        for session in self:
            target = Stage.get_default_stage(
                company_id=session.company_id.id,
                technical_state=session.state,
            )
            if target and session.stage_id != target:
                session.stage_id = target.id
        return True

    def _check_state_transition(self, old_state, new_state):
        if old_state == new_state:
            return

        if new_state not in self._workflow_states.get(
            old_state,
            set(),
        ):
            raise ValidationError(
                _("Invalid Treatment Session transition: %s → %s.")
                % (old_state, new_state)
            )

    def _require_manager(self):
        if not self.env.user.has_group(
            "clinic_treatment_session."
            "group_treatment_session_manager"
        ):
            raise AccessError(
                _("Treatment Session Manager access is required.")
            )

    def _require_clinician(self):
        if not (
            self.env.user.has_group(
                "clinic_treatment_session."
                "group_treatment_session_clinician"
            )
            or self.env.user.has_group(
                "clinic_treatment_session."
                "group_treatment_session_manager"
            )
        ):
            raise AccessError(
                _("Treatment Session Clinician access is required.")
            )

    def _workflow_write(self, values):
        return self.with_context(
            clinic_treatment_session_workflow=True
        ).write(values)

    def _check_operational_conflicts(self):
        """Enforce optional doctor/room overlap protection at workflow time."""
        Param = self.env["ir.config_parameter"].sudo()
        check_doctor = Param.get_param(
            "clinic_treatment_session.prevent_doctor_overlap",
            "1",
        ) in ("1", "True", "true")
        check_room = Param.get_param(
            "clinic_treatment_session.prevent_room_overlap",
            "1",
        ) in ("1", "True", "true")

        for session in self:
            if not session.start_datetime or not session.end_datetime:
                continue

            common = [
                ("id", "!=", session.id),
                ("company_id", "=", session.company_id.id),
                ("state", "in", ("confirmed", "in_progress")),
                ("start_datetime", "<", session.end_datetime),
                ("end_datetime", ">", session.start_datetime),
            ]

            if check_doctor and session.doctor_id:
                conflict = self.search(
                    common + [("doctor_id", "=", session.doctor_id.id)],
                    limit=1,
                )
                if conflict:
                    raise ValidationError(
                        _(
                            "Clinic Doctor is already assigned to overlapping "
                            "session %s."
                        )
                        % conflict.display_name
                    )

            if check_room and session.room_id:
                conflict = self.search(
                    common + [("room_id", "=", session.room_id.id)],
                    limit=1,
                )
                if conflict:
                    raise ValidationError(
                        _(
                            "Room is already assigned to overlapping "
                            "session %s."
                        )
                        % conflict.display_name
                    )

    def action_confirm(self):
        self._check_operational_conflicts()
        for session in self:
            if session.state == "draft":
                session._workflow_write({"state": "confirmed"})
                session._sync_stage_with_state()
        return True

    def action_start(self):
        self._require_clinician()
        self._check_operational_conflicts()
        now = fields.Datetime.now()

        for session in self:
            if session.state not in ("draft", "confirmed"):
                continue
            session._workflow_write(
                {
                    "state": "in_progress",
                    "actual_start_datetime": (
                        session.actual_start_datetime or now
                    ),
                }
            )
            session._sync_stage_with_state()

        return True

    def action_prepare_consumption(self):
        """Move planned stock-relevant lines to Ready in one controlled action."""
        self._require_clinician()
        for session in self:
            if session.state not in ("confirmed", "in_progress"):
                raise ValidationError(
                    _(
                        "Consumption can be prepared only for Confirmed or "
                        "In Progress sessions."
                    )
                )
            planned = session.line_ids.filtered(
                lambda line: (
                    line.display_type == "line"
                    and line.consumption_state == "planned"
                )
            )
            planned.action_mark_ready()
        return True

    def action_consume_ready_lines(self):
        """Consume all Ready stock-relevant lines through line-level safeguards."""
        self._require_clinician()
        for session in self:
            if session.state not in ("confirmed", "in_progress"):
                raise ValidationError(
                    _(
                        "Materials can be consumed only for Confirmed or "
                        "In Progress sessions."
                    )
                )
            ready = session.line_ids.filtered(
                lambda line: (
                    line.display_type == "line"
                    and line.consumption_state == "ready"
                )
            )
            ready.action_mark_consumed()
        return True

    def action_done(self):
        self._require_clinician()
        now = fields.Datetime.now()

        for session in self:
            if session.state not in (
                "draft",
                "confirmed",
                "in_progress",
            ):
                continue

            values = {
                "state": "done",
                "actual_start_datetime": (
                    session.actual_start_datetime or now
                ),
                "actual_end_datetime": now,
            }
            session._workflow_write(values)
            session._sync_stage_with_state()
            session._post_done_hook()

        return True

    def action_no_show(self):
        for session in self:
            if session.state in ("draft", "confirmed"):
                session._workflow_write({"state": "no_show"})
                session._sync_stage_with_state()
        return True

    def action_cancel(self):
        for session in self:
            if session.state in ("done", "no_show"):
                raise UserError(
                    _(
                        "Done or No-show sessions cannot be cancelled. "
                        "Use a documented correction workflow instead."
                    )
                )
            if session.state != "cancelled":
                session._workflow_write({"state": "cancelled"})
                session._sync_stage_with_state()
        return True

    def action_reset_draft(self):
        self._require_manager()
        for session in self:
            if session.state not in ("cancelled", "no_show"):
                raise ValidationError(
                    _(
                        "Only Cancelled or No-show sessions may be "
                        "reset to Draft."
                    )
                )
            session._workflow_write(
                {
                    "state": "draft",
                    "actual_start_datetime": False,
                    "actual_end_datetime": False,
                }
            )
            session._sync_stage_with_state()
        return True

    @api.model
    def cron_mark_auto_no_show(self):
        """Mark overdue unstarted sessions No-show in a bounded batch."""
        Param = self.env["ir.config_parameter"].sudo()
        enabled = Param.get_param(
            "clinic_treatment_session.auto_no_show_enabled",
            "0",
        ) in ("1", "True", "true")
        if not enabled:
            return True

        try:
            hours = int(
                Param.get_param(
                    "clinic_treatment_session.auto_no_show_hours",
                    "2",
                )
            )
        except (TypeError, ValueError):
            hours = 2

        cutoff = fields.Datetime.subtract(
            fields.Datetime.now(),
            hours=max(hours, 0),
        )
        due = self.search(
            [
                ("state", "in", ("draft", "confirmed")),
                ("start_datetime", "!=", False),
                ("start_datetime", "<=", cutoff),
            ],
            limit=200,
        )
        for session in due:
            session._workflow_write({"state": "no_show"})
            session._sync_stage_with_state()

        return True

    def _post_done_hook(self):
        """Preserve the historical hook and optionally create Billing."""
        result = super()._post_done_hook()

        Param = self.env["ir.config_parameter"].sudo()
        auto_billing = Param.get_param(
            "clinic_treatment_session.auto_create_billing",
            "0",
        ) in ("1", "True", "true")
        billing_mode = Param.get_param(
            "clinic_treatment_session.billing_mode",
            "clinic_billing",
        )

        if auto_billing and billing_mode == "clinic_billing":
            if not self.billing_invoice_id:
                self.action_create_clinic_billing()
        elif auto_billing and billing_mode == "account_invoice":
            if not self.move_id:
                self.action_create_invoice()

        return result
