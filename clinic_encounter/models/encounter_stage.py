# -*- coding: utf-8 -*-
# ClinicOne — clinic_encounter
# File: models/encounter_stage.py
#
# Fungsi:
# - Mendefinisikan stage/tahap Encounter (Draft, In Progress, Done, Cancelled).
# - Menyediakan kontrol akses per stage (opsional via res.groups).
# - Kanban fold untuk stage yang "selesai/tertutup".
# - Hook saat masuk stage: jadwalkan aktivitas &/atau jalankan Server Action.
#
# Catatan integrasi:
# - Encounter (models/encounter.py) menggunakan field stage_id.state untuk derive 'state'.
# - Hook 'action_server_id' memungkinkan integrasi ringan ke:
#     • Reservasi room/queue ketika masuk 'In Progress'
#     • Notifikasi billing ketika 'Done'
#     • Pencatatan audit/QA ketika 'Cancelled'
#
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


_STAGE_SELECTION = [
    ("draft", "Draft"),
    ("in_progress", "In Progress"),
    ("done", "Done"),
    ("cancelled", "Cancelled"),
]


class ClinicEncounterStage(models.Model):
    _name = "clinic.encounter.stage"
    _description = "Encounter Stage"
    _order = "sequence, id"
    _check_company_auto = True

    # --------------------------------------------------------------------------------
    # Identitas & Perusahaan
    # --------------------------------------------------------------------------------
    name = fields.Char(required=True, index=True, translate=True)
    sequence = fields.Integer(default=10, index=True, help="Ordering for pipelines and kanban.")
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        index=True,
        help="If empty, the stage is global (usable by all companies).",
    )

    # --------------------------------------------------------------------------------
    # Status Fungsional (dipakai oleh clinic.encounter.state)
    # --------------------------------------------------------------------------------
    state = fields.Selection(
        selection=_STAGE_SELECTION,
        required=True,
        default="draft",
        index=True,
        help="Functional state reflected into encounter.state.",
    )
    is_closed = fields.Boolean(
        string="Closed Stage",
        compute="_compute_is_closed",
        store=True,
        help="True for 'done' or 'cancelled' stages.",
    )
    fold = fields.Boolean(
        string="Folded in Kanban",
        help="Fold this stage in kanban view.",
    )
    color = fields.Integer(string="Color Index")
    description = fields.Text(string="Description / SLA / Notes")

    # --------------------------------------------------------------------------------
    # Kebijakan & Validasi Opsional
    # --------------------------------------------------------------------------------
    allow_edit = fields.Boolean(
        string="Allow Editing in This Stage",
        default=True,
        help="If disabled, records in this stage should be treated as read-only by business logic.",
    )
    require_consent = fields.Boolean(
        string="Require Consent Before Enter",
        help="Block moving encounters to this stage unless patient consent_ok is set.",
    )
    require_procedures = fields.Boolean(
        string="Require Procedures Before Enter",
        help="Block moving encounters to this stage unless at least one planned procedure exists.",
    )

    # --------------------------------------------------------------------------------
    # Akses Berbasis Grup (opsional)
    # --------------------------------------------------------------------------------
    allowed_group_ids = fields.Many2many(
        "res.groups",
        "clinic_encounter_stage_group_rel",
        "stage_id",
        "group_id",
        string="Allowed Groups to Enter",
        help="If set, only users in these groups can move an encounter to this stage.",
    )

    # --------------------------------------------------------------------------------
    # Hook saat Memasuki Stage
    # --------------------------------------------------------------------------------
    activity_type_id = fields.Many2one(
        "mail.activity.type",
        string="Default Activity on Enter",
        help="Schedule this activity for the encounter owner when entering this stage.",
    )
    activity_summary = fields.Char(
        string="Activity Summary",
        help="Summary used when creating the default activity.",
        default=lambda self: _("Follow up Encounter Stage"),
    )
    action_server_id = fields.Many2one(
        "ir.actions.server",
        string="Server Action on Enter",
        domain=[("state", "=", "code")],
        help="Optional server action to execute when an encounter enters this stage.",
    )

    # --------------------------------------------------------------------------------
    # Komputasi & Onchange
    # --------------------------------------------------------------------------------
    @api.depends("state")
    def _compute_is_closed(self):
        for rec in self:
            rec.is_closed = rec.state in ("done", "cancelled")

    @api.onchange("state")
    def _onchange_state(self):
        # Default: fold-kanban untuk stage closed
        if self.state in ("done", "cancelled"):
            self.fold = True

    # --------------------------------------------------------------------------------
    # Validasi & Constraint
    # --------------------------------------------------------------------------------
    _constraint_uniq_stage_name_company = models.Constraint(
        'unique(name, company_id)',
        'Stage name must be unique per company.',
    )

    @api.constrains("require_consent", "state")
    def _check_require_consent_consistency(self):
        # Tidak ada larangan, ini placeholder jika ingin aturan tambahan.
        for _rec in self:
            pass

    # --------------------------------------------------------------------------------
    # Utilitas untuk Encounter (dipanggil oleh model encounter)
    # --------------------------------------------------------------------------------
    def check_user_can_enter(self, user=None):
        """Validasi grup yang diizinkan memasuki stage ini."""
        self.ensure_one()
        user = user or self.env.user
        if self.allowed_group_ids:
            if not (user.groups_id & self.allowed_group_ids):
                raise UserError(
                    _(
                        "You are not allowed to move encounters to the stage '%s'."
                    )
                    % (self.display_name,)
                )
        return True

    def check_business_requirements(self, encounter):
        """Validasi bisnis ketika encounter akan dipindahkan ke stage ini."""
        self.ensure_one()
        if self.require_consent and not getattr(encounter, "consent_ok", False):
            raise ValidationError(
                _("Consent is required before moving to stage '%s'.") % self.display_name
            )
        if self.require_procedures and not encounter.procedure_line_ids:
            raise ValidationError(
                _("At least one planned procedure is required before moving to stage '%s'.")
                % self.display_name
            )
        # Jika stage scoped by company, pastikan company sesuai
        if self.company_id and encounter.company_id and self.company_id != encounter.company_id:
            raise ValidationError(
                _("Stage '%s' belongs to another company.") % self.display_name
            )
        return True

    def trigger_on_enter(self, encounter):
        """
        Dipanggil saat encounter memasuki stage ini.
        - Jadwalkan aktivitas default (jika di-set).
        - Jalankan server action (jika di-set).
        """
        self.ensure_one()
        # Aktivitas default
        if self.activity_type_id:
            try:
                encounter.activity_schedule(
                    self.activity_type_id.xml_id or self.activity_type_id.id,
                    summary=self.activity_summary or _("Follow up"),
                    user_id=encounter.user_id.id or self.env.user.id,
                )
            except Exception:
                # Jangan blok workflow hanya karena gagal aktivitas
                pass

        # Jalankan server action (kode python aman yang dikelola admin)
        if self.action_server_id:
            try:
                # Context membawa active_model/active_id untuk server action
                ctx = dict(self.env.context, active_model=encounter._name, active_id=encounter.id, active_ids=encounter.ids)
                self.action_server_id.with_context(ctx).run()
            except Exception as e:
                # Untuk safety, bungkus sebagai UserError agar admin tahu
                raise UserError(_("Server Action failed on stage enter: %s") % e)

    # --------------------------------------------------------------------------------
    # Batch Helper (opsional untuk mass-stage update)
    # --------------------------------------------------------------------------------
    def apply_to_encounters(self, encounter_ids):
        """
        Ubah stage untuk sekumpulan encounter (IDs atau recordset).
        Melakukan validasi grup & business requirement per encounter dan trigger hook.
        """
        self.ensure_one()
        encounters = encounter_ids
        if not isinstance(encounter_ids, models.BaseModel):
            encounters = self.env["clinic.encounter"].browse(encounter_ids)

        # Validasi akses user untuk stage ini
        self.check_user_can_enter()

        # Validasi & apply
        for enc in encounters:
            self.check_business_requirements(enc)
            enc.write({"stage_id": self.id})
            self.trigger_on_enter(enc)
        return True

    # --------------------------------------------------------------------------------
    # Name & Label
    # --------------------------------------------------------------------------------
    @api.depends("name", "state")
    def _compute_display_name(self):
        label_by_state = {
            "draft": _("Draft"),
            "in_progress": _("In Progress"),
            "done": _("Done"),
            "cancelled": _("Cancelled"),
        }
        for rec in self:
            badge = label_by_state.get(rec.state, rec.state or "")
            rec.display_name = f"{rec.name or ''} [{badge}]"

    # --------------------------------------------------------------------------------
    # Unlink Proteksi
    # --------------------------------------------------------------------------------
    def unlink(self):
        # Cegah penghapusan jika stage dipakai encounter
        Encounter = self.env["clinic.encounter"]
        for stage in self:
            used = Encounter.search_count([("stage_id", "=", stage.id)], limit=1)
            if used:
                raise UserError(
                    _("Cannot delete stage '%s' because it is in use by encounters.") % stage.display_name
                )
        return super().unlink()

    # --------------------------------------------------------------------------------
    # Default Stage Utilities (opsional)
    # --------------------------------------------------------------------------------
    @api.model
    def stage_for_state(self, state_code, company=None):
        """Cari stage pertama untuk state tertentu. Jika tidak ada, return False."""
        company = company or self.env.company
        stage = self.search(
            [("state", "=", state_code), ("company_id", "in", [False, company.id])],
            order="company_id, sequence",
            limit=1,
        )
        return stage
