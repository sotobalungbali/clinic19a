# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ClinicTreatmentSessionStage(models.Model):
    """
    Stage/kolom kanban untuk Clinic Treatment Session.

    Peran utama model ini:
      - Mengelompokkan dan mem-visualisasikan sesi (clinic.treatment.session) dalam
        bentuk board kanban (mis. Draft, Confirmed, In Progress, Done, No-show, Cancelled).
      - Menyediakan "technical_state" yang disinkronkan dengan field state di
        clinic.treatment.session, sehingga:
          * Stage tertentu identik dengan state tertentu (mapping satu-ke-satu),
            atau
          * Beberapa stage berbeda boleh memetakan ke technical_state yang sama
            (mis. beberapa variasi "In Progress").
      - Menjadi titik integrasi untuk addon lain (mis. reporting, SLA, workflow
        khusus, dsb) di ekosistem ClinicOne.

    Integrasi dengan 39 addon ClinicOne terjadi terutama lewat:
      - Relasi ke clinic.treatment.session (session_ids)
      - Field company_id untuk multi-company
      - Field technical_state yang dipakai oleh treatment_session._sync_stage_with_state()
    """

    _name = "clinic.treatment.session.stage"
    _description = "Clinic Treatment Session Stage"
    _order = "sequence, id"
    _rec_name = "name"

    # -------------------------------------------------------------------------
    # BASIC INFO
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Stage Name",
        required=True,
        translate=True,
        help="Name of the stage as shown in kanban and other views.",
    )

    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Order of the stage. Lower values appear first in kanban.",
    )

    active = fields.Boolean(
        string="Active",
        default=True,
        help="Uncheck this to archive the stage without deleting it.",
    )

    description = fields.Text(
        string="Description",
        help="Internal description or guideline for this stage.",
    )

    color = fields.Integer(
        string="Color Index",
        help="Color index for kanban cards when grouped by stage.",
    )

    fold = fields.Boolean(
        string="Folded in Kanban",
        help=(
            "If enabled, this stage will be folded by default in the kanban view. "
            "Useful for 'Done', 'Cancelled', or 'No-show' stages."
        ),
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        index=True,
        help="Company that owns this stage. Empty means shared across companies.",
    )

    # -------------------------------------------------------------------------
    # TECHNICAL STATE MAPPING (SYNC DENGAN clinic.treatment.session.state)
    # -------------------------------------------------------------------------
    technical_state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("in_progress", "In Progress"),
            ("done", "Done"),
            ("no_show", "No-show"),
            ("cancelled", "Cancelled"),
        ],
        string="Technical State",
        required=True,
        help=(
            "Technical state that this stage represents. It must be aligned "
            "with the 'Status' field on the treatment session.\n\n"
            "This allows automatic synchronization between session status "
            "and kanban stage."
        ),
    )

    is_default = fields.Boolean(
        string="Default Stage",
        help=(
            "If enabled, this stage will be used as the default stage for its "
            "technical state (per company) when creating new sessions."
        ),
    )

    is_final = fields.Boolean(
        string="Final Stage",
        help=(
            "Check this when this stage represents a final state for the session "
            "workflow (e.g., Done / No-show / Cancelled). This can be used by "
            "reporting or SLA modules."
        ),
    )

    # Legend seperti di CRM/Pipeline; bermanfaat untuk UI Kanban
    legend_normal = fields.Char(
        string="Kanban Legend (Normal)",
        default=lambda self: _("In Progress"),
        translate=True,
        help=(
            "Label shown in kanban for the normal status. This is purely cosmetic "
            "and used for tooltips or colored bars."
        ),
    )

    legend_done = fields.Char(
        string="Kanban Legend (Done)",
        default=lambda self: _("Ready / Completed"),
        translate=True,
        help="Label used when a session in this stage is considered done.",
    )

    legend_blocked = fields.Char(
        string="Kanban Legend (Blocked)",
        default=lambda self: _("Blocked"),
        translate=True,
        help="Label used when a session in this stage is blocked.",
    )

    # -------------------------------------------------------------------------
    # RELATIONS KE SESSION
    # -------------------------------------------------------------------------
    session_ids = fields.One2many(
        "clinic.treatment.session",
        "stage_id",
        string="Sessions",
        help="Sessions currently assigned to this stage.",
    )

    sessions_count = fields.Integer(
        string="Sessions Count",
        compute="_compute_sessions_count",
        help="Number of sessions currently in this stage.",
    )

    # -------------------------------------------------------------------------
    # SQL CONSTRAINTS
    # -------------------------------------------------------------------------
    _name_company_unique = models.Constraint(
        "UNIQUE(name, company_id)",
        "The stage name must be unique per company.",
    )

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------
    @api.depends("session_ids")
    def _compute_sessions_count(self):
        """
        Hitung jumlah sesi yang berada di stage ini.

        Catatan:
          - Untuk performa besar, modul reporting ClinicOne bisa override
            menggunakan read_group, tapi default compute seperti ini cukup
            untuk kebanyakan kasus.
        """
        for stage in self:
            stage.sessions_count = len(stage.session_ids)

    # -------------------------------------------------------------------------
    # ORM OVERRIDES
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        """Create stages using the Odoo 19 multi-create contract.

        The historical implementation expected one dict, while Odoo 19 may
        invoke model ``create`` with a list of value dictionaries even when
        the caller supplies a single logical record.
        """
        prepared = []

        for values in vals_list:
            vals = dict(values)

            if not vals.get("company_id"):
                vals["company_id"] = self.env.company.id

            technical_state = vals.get("technical_state")
            if technical_state in ("done", "no_show", "cancelled"):
                vals.setdefault("is_final", True)
                vals.setdefault("fold", True)

            prepared.append(vals)

        stages = super().create(prepared)
        stages._ensure_single_default_per_state()
        return stages

    def write(self, vals):
        """
        - Jika is_default diubah menjadi True, pastikan stage lain dengan
          technical_state + company sama di-set False.
        """
        result = super(ClinicTreatmentSessionStage, self).write(vals)
        if "is_default" in vals or "technical_state" in vals or "company_id" in vals:
            self._ensure_single_default_per_state()
        return result

    def unlink(self):
        """
        - Jangan hapus stage yang masih punya session aktif (optional)
          kecuali user paham implikasinya. Di sini kita cegah, dan arahkan
          user untuk memindahkan sesi dulu atau archive stage.
        """
        for stage in self:
            if stage.session_ids:
                raise ValidationError(
                    _(
                        "You cannot delete the stage '%s' because there are still "
                        "sessions assigned to it. Please move or archive those "
                        "sessions before deleting the stage."
                    )
                    % (stage.name,)
                )
        return super(ClinicTreatmentSessionStage, self).unlink()

    # -------------------------------------------------------------------------
    # HELPER METHODS
    # -------------------------------------------------------------------------
    def _ensure_single_default_per_state(self):
        """
        Pastikan hanya satu stage dengan is_default=True per
        (company_id, technical_state).

        Jika ada lebih dari satu:
          - stage yang baru di-set default tetap True
          - stage lain pada kombinasi yang sama di-set False
        """
        for stage in self:
            if not stage.is_default:
                continue
            domain = [
                ("id", "!=", stage.id),
                ("technical_state", "=", stage.technical_state),
                ("is_default", "=", True),
            ]
            # Company-aware (company_id sama atau sama-sama False)
            if stage.company_id:
                domain.append(("company_id", "=", stage.company_id.id))
            else:
                domain.append(("company_id", "=", False))

            others = self.search(domain)
            if others:
                others.write({"is_default": False})

    @api.model
    def get_default_stage(self, company_id=False, technical_state=False):
        """
        Helper untuk mencari default stage berdasarkan:
          - company_id (opsional; default env.company)
          - technical_state (opsional; bisa None → cari stage 'draft')

        Digunakan misalnya ketika:
          - Membuat clinic.treatment.session baru
          - Mengubah state session dan ingin sync kanban stage.

        Return:
          recordset clinic.treatment.session.stage (bisa kosong).
        """
        if not company_id:
            company_id = self.env.company.id

        if not technical_state:
            technical_state = "draft"

        domain = [
            ("technical_state", "=", technical_state),
            "|",
            ("company_id", "=", False),
            ("company_id", "=", company_id),
        ]

        # Cari yang is_default dulu
        stage = self.search(domain + [("is_default", "=", True)], limit=1)
        if not stage:
            # fallback ke stage pertama berdasarkan sequence
            stage = self.search(domain, order="sequence, id", limit=1)
        return stage

    # -------------------------------------------------------------------------
    # ACTIONS / SMART BUTTON
    # -------------------------------------------------------------------------
    def action_view_sessions(self):
        """
        Smart button dari form stage untuk melihat semua sesi yang berada
        di stage ini. Ini juga jadi titik integrasi UI dengan model
        clinic.treatment.session.
        """
        self.ensure_one()
        action = self.env.ref(
            "clinic_treatment_session.action_clinic_treatment_session"
        ).read()[0]
        action["domain"] = [("stage_id", "=", self.id)]
        action["context"] = {
            "default_stage_id": self.id,
            "search_default_group_by_stage": 1,
        }
        return action

    # -------------------------------------------------------------------------
    # DISPLAY HELPERS
    # -------------------------------------------------------------------------
    def name_get(self):
        """
        Tampilkan nama stage dengan label state teknis untuk
        memudahkan konfigurasi multi-stage.

        Format:
          "<Stage Name> [Status: Draft]"
        """
        result = []
        state_labels = dict(self._fields["technical_state"].selection)
        for stage in self:
            state_label = state_labels.get(stage.technical_state, stage.technical_state)
            name = "%s [%s: %s]" % (
                stage.name,
                _("Status"),
                state_label,
            )
            result.append((stage.id, name))
        return result

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("technical_state", "is_final")
    def _check_final_flag(self):
        """
        Validasi sederhana:
          - Jika technical_state in ('done', 'no_show', 'cancelled'),
            wajar kalau is_final=True (kalau False masih boleh, tapi boleh
            diberi peringatan / logik lain di modul lanjutan).
          - Jika technical_state 'draft', 'confirmed', 'in_progress' dan
            is_final=True, ini tidak dilarang, tapi bisa jadi warning untuk
            modul SLA (tidak kita hard-block di sini supaya fleksibel).
        Saat ini tidak kita raise error, hanya placeholder untuk future
        extension. Dibiarkan kosong agar tidak membatasi fleksibilitas.
        """
        # Tidak ada error; placeholder for future override by other modules.
        return True
