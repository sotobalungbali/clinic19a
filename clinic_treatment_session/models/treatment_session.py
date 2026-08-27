# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

import datetime


class ClinicTreatmentSession(models.Model):
    """
    Core execution model for ClinicOne treatment workflow.

    This model merepresentasikan 1 sesi tindakan/treatment di klinik,
    menghubungkan berbagai addon ClinicOne:
      - clinic_patient    → patient_id (res.partner dengan is_patient=True)
      - clinic_doctor     → clinic_doctor_id (hr.employee)
      - clinic_booking    → booking_id, room_id
      - clinic_treatment_catalog → treatment_id
      - clinic_billing    → billing_invoice_id (clinic.billing.invoice)
      - Accounting (Odoo) → move_id (account.move, out_invoice)
      - Addon lain dapat meng-extend model ini via _inherit dan field tambahan.
    """

    _name = "clinic.treatment.session"
    _description = "Clinic Treatment Session"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "start_datetime desc, id desc"
    _rec_name = "display_name"

    # -------------------------------------------------------------------------
    # Core Identity
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Session Number",
        required=True,
        copy=False,
        default="New",
        readonly=True,
        tracking=True,
        help="Unique session number generated from a sequence.",
    )

    display_name = fields.Char(
        string="Display Name",
        compute="_compute_display_name",
        store=True,
    )

    active = fields.Boolean(
        string="Active",
        default=True,
        tracking=True,
        help="Uncheck to archive the session without deleting it.",
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
        tracking=True,
    )

    color = fields.Integer(
        string="Color Index",
        help="Used to colorize sessions in kanban or calendar views.",
    )

    # -------------------------------------------------------------------------
    # Relations: Patient, Doctor, Treatment, Booking, Room
    # -------------------------------------------------------------------------
    patient_id = fields.Many2one(
        "res.partner",
        string="Patient",
        required=True,
        index=True,
        tracking=True,
        domain=[("is_patient", "=", True)],
        help="Person receiving the treatment; must be flagged as a patient.",
    )

    patient_phone = fields.Char(
        string="Patient Mobile",
        related="patient_id.phone",
        readonly=True,
    )

    patient_email = fields.Char(
        string="Patient Email",
        related="patient_id.email",
        readonly=True,
    )

    clinic_doctor_id = fields.Many2one(
        "hr.employee",
        string="Doctor / Therapist",
        index=True,
        tracking=True,
        help="Doctor or therapist responsible for this session.",
    )

    doctor_user_id = fields.Many2one(
        "res.users",
        string="Doctor User",
        related="clinic_doctor_id.user_id",
        readonly=True,
    )

    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment",
        index=True,
        tracking=True,
        help="Treatment template from Clinic Treatment Catalog.",
    )

    booking_id = fields.Many2one(
        "booking.booking",
        string="Booking",
        index=True,
        tracking=True,
        help="Original booking that planned this session.",
    )

    booking_state = fields.Selection(
        related="booking_id.state",
        string="Booking Status",
        readonly=True,
    )

    room_id = fields.Many2one(
        "booking.room",
        string="Room / Device",
        index=True,
        tracking=True,
        help="Room or device used for this treatment session.",
    )

    # -------------------------------------------------------------------------
    # Time & Duration
    # -------------------------------------------------------------------------
    start_datetime = fields.Datetime(
        string="Planned Start",
        required=True,
        tracking=True,
        help="Planned start datetime of the session.",
    )

    end_datetime = fields.Datetime(
        string="Planned End",
        tracking=True,
        help="Planned/actual end datetime of the session.",
    )

    duration_planned = fields.Float(
        string="Planned Duration (min)",
        help="Planned duration in minutes, usually derived from the catalog or booking.",
    )

    duration_actual = fields.Float(
        string="Actual Duration (min)",
        compute="_compute_duration_actual",
        store=True,
        help="Computed from Start and End datetime.",
    )

    is_overtime = fields.Boolean(
        string="Overtime",
        compute="_compute_is_overtime",
        store=True,
        index=True,
        help=(
            "Checked when actual duration exceeds planned duration. "
            "Stored because the value depends only on stored session "
            "duration fields and is used in Search/Analytics domains."
        ),
    )

    # -------------------------------------------------------------------------
    # Status & Stage
    # -------------------------------------------------------------------------
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("in_progress", "In Progress"),
            ("done", "Done"),
            ("no_show", "No-show"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        index=True,
        tracking=True,
        required=True,
    )

    stage_id = fields.Many2one(
        "clinic.treatment.session.stage",
        string="Stage",
        tracking=True,
        help="Visual stage used for kanban board. Usually aligned with the state.",
    )

    can_edit = fields.Boolean(
        string="Can Edit",
        compute="_compute_can_edit",
        help="Technical helper to disable editing in non-editable states.",
    )

    # -------------------------------------------------------------------------
    # Notes & Clinical Information
    # -------------------------------------------------------------------------
    note_internal = fields.Text(
        string="Internal Notes",
        help="Internal remarks visible only to clinic staff.",
    )

    note_public = fields.Text(
        string="Public Notes",
        help="Notes that are safe to show to the patient or portal.",
    )

    chief_complaint = fields.Text(
        string="Chief Complaint",
        help="Patient's primary complaint or reason for the visit.",
    )

    objective_notes = fields.Text(
        string="Objective / Findings",
        help="Objective findings from examination.",
    )

    assessment = fields.Text(
        string="Assessment",
        help="Clinical assessment or diagnosis summary.",
    )

    plan = fields.Text(
        string="Plan / Recommendation",
        help="Treatment plan, follow-up recommendations, or lifestyle advice.",
    )

    contraindication_flag = fields.Boolean(
        string="Has Contraindication?",
        tracking=True,
        help="Indicates that this session has some contraindications or special precautions.",
    )

    # Cancellation / No-show reasons
    cancellation_reason = fields.Text(
        string="Cancellation Reason",
        help="Reason why this session was cancelled.",
    )

    no_show_reason = fields.Text(
        string="No-show Reason",
        help="Explanation why the patient did not show up.",
    )

    # -------------------------------------------------------------------------
    # Lines / Steps / Consumables
    # -------------------------------------------------------------------------
    line_ids = fields.One2many(
        "clinic.treatment.session.line",
        "session_id",
        string="Session Details / Consumables",
        help="Detailed steps, consumables, or sub-treatments performed during the session.",
    )

    # -------------------------------------------------------------------------
    # Billing & Accounting Integration
    # -------------------------------------------------------------------------
    # billing_invoice_id = fields.Many2one(
    #     "clinic.billing.invoice",
    #     string="Clinic Billing",
    #     readonly=True,
    #     copy=False,
    #     help=(
    #         "Linked clinic billing invoice if this session was billed via the "
    #         "Clinic Billing module."
    #     ),
    # )

    move_id = fields.Many2one(
        "account.move",
        string="Customer Invoice",
        readonly=True,
        copy=False,
        help="Accounting invoice related to this session, if any.",
    )

    # is_fully_invoiced = fields.Boolean(
    #     string="Fully Invoiced?",
    #     compute="_compute_is_fully_invoiced",
    #     help="Technical flag indicating whether this session is fully invoiced & paid.",
    # )

    # -------------------------------------------------------------------------
    # Meta: Attachments & Activities
    # -------------------------------------------------------------------------
    attachment_count = fields.Integer(
        string="Attachments",
        compute="_compute_attachment_count",
    )

    activity_count = fields.Integer(
        string="Activities",
        compute="_compute_activity_count",
    )

    # -------------------------------------------------------------------------
    # ORM & TECHNICAL
    # -------------------------------------------------------------------------
    _name_company_unique = models.Constraint(
        "UNIQUE(name, company_id)",
        "Session number must be unique per company.",
    )

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------
