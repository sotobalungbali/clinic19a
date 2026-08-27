
# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, AccessError, UserError


class ResUsers(models.Model):
    _inherit = 'res.users'

    # -------------------------------------------------------------------------
    # BRANCH ACCESS MODELING
    # -------------------------------------------------------------------------
    allowed_branch_ids = fields.Many2many(
        'clinic.branch',
        'res_users_clinic_branch_rel',  # rel table
        'user_id', 'branch_id',
        string='Allowed Branches',
        help='Daftar cabang yang boleh diakses user ini. Record rules akan '
             'membatasi visibilitas data berdasarkan daftar ini.',
    )

    working_branch_id = fields.Many2one(
        'clinic.branch',
        string='Working Branch',
        domain='[("id", "in", allowed_branch_ids)]',
        check_company=True,
        help='Cabang aktif (konteks kerja) untuk transaksi & default nilai.',
        default=lambda self: self._default_working_branch_id(),
    )

    allowed_branch_count = fields.Integer(
        string='# Allowed Branches',
        compute='_compute_branch_counts',
        help='Jumlah cabang yang diizinkan untuk user ini.'
    )

    # Informasi turunan untuk laporan/UX
    working_branch_tz = fields.Char(
        string='Working Branch Timezone',
        compute='_compute_working_branch_meta',
        help='Timezone dari working branch, berguna untuk jadwal/SLA di UI.'
    )

    # -------------------------------------------------------------------------
    # DEFAULTS
    # -------------------------------------------------------------------------
    @api.model
    def _default_working_branch_id(self):
        """
        Urutan default:
        1) context['branch_id'] jika valid & diizinkan
        2) company.default_branch_id jika diizinkan
        3) allowed_branch_ids pertama (dengan company aktif)
        4) False
        """
        user = self.env.user
        Branch = self.env['clinic.branch']
        Company = self.env.company

        # 1) context
        ctx_bid = self.env.context.get('branch_id')
        if ctx_bid:
            b = Branch.browse(int(ctx_bid)).exists()
            if b and self._is_branch_allowed_for(user, b):
                return b.id

        # 2) company default
        comp = Company
        if 'default_branch_id' in comp._fields:
            db = comp.sudo().default_branch_id
            if db and self._is_branch_allowed_for(user, db):
                return db.id

        # 3) first allowed (in active company if possible)
        allowed = self._user_allowed_branches(user=user, company=comp)
        return allowed[:1].id if allowed else False

    # -------------------------------------------------------------------------
    # COMPUTE
    # -------------------------------------------------------------------------
    @api.depends('allowed_branch_ids')
    def _compute_branch_counts(self):
        for user in self:
            user.allowed_branch_count = len(user.allowed_branch_ids)

    @api.depends('working_branch_id', 'working_branch_id.tz')
    def _compute_working_branch_meta(self):
        for user in self:
            user.working_branch_tz = user.working_branch_id.tz if user.working_branch_id else False

    # -------------------------------------------------------------------------
    # ONCHANGE
    # -------------------------------------------------------------------------
    @api.onchange('allowed_branch_ids')
    def _onchange_allowed_branch_ids(self):
        """
        Pastikan working_branch tetap valid. Jika tidak, pilih alternatif dari allowed_branch_ids.
        """
        if self.working_branch_id and self.allowed_branch_ids:
            if self.working_branch_id not in self.allowed_branch_ids:
                # pilih cabang pertama yang allowed; atau kosongkan
                self.working_branch_id = self.allowed_branch_ids[:1] or False
        elif not self.allowed_branch_ids:
            self.working_branch_id = False

    @api.onchange('company_id')
    def _onchange_company_id(self):
        """
        Ketika company berubah:
        - Jika working_branch tidak match company, coba set ke default company.
        - Bila tidak ada, pilih allowed branch pertama pada company tsb.
        """
        if not self.company_id:
            return
        if self.working_branch_id and self.working_branch_id.company_id != self.company_id:
            # coba pakai default company
            db = False
            if 'default_branch_id' in self.company_id._fields:
                db = self.company_id.sudo().default_branch_id
                if db and db in self.allowed_branch_ids:
                    self.working_branch_id = db
                    return
            # fallback: allowed branch pertama dengan company tsb
            alt = self.allowed_branch_ids.filtered(lambda b: b.company_id == self.company_id)[:1]
            self.working_branch_id = alt or False

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains('working_branch_id', 'allowed_branch_ids', 'company_id')
    def _check_branch_company_consistency(self):
        """
        - working_branch.company harus se-company dengan user.company
        - working_branch harus ⊆ allowed_branch_ids (bila ada allowed)
        - allowed_branch_ids harus se-company dengan salah satu user.allowed_company_ids (opsional)
        """
        for user in self:
            # Konsistensi company
            if user.working_branch_id and user.working_branch_id.company_id != user.company_id:
                raise ValidationError(
                    _("Working branch's company must match the user's current company.")
                )
            # Working ⊆ Allowed
            if user.working_branch_id and user.allowed_branch_ids:
                if user.working_branch_id not in user.allowed_branch_ids:
                    raise ValidationError(_("Working branch must be among the allowed branches."))

            # Allowed branch company ⊆ allowed companies (bila ada)
            # (res.users memiliki allowed_company_ids)
            if 'allowed_company_ids' in user._fields and user.allowed_company_ids:
                invalid = user.allowed_branch_ids.filtered(
                    lambda b: b.company_id and b.company_id not in user.allowed_company_ids
                )
                if invalid:
                    raise ValidationError(_(
                        "Some allowed branches belong to companies that are not allowed for this user."
                    ))

    # -------------------------------------------------------------------------
    # CREATE / WRITE (GUARDRAILS & AUTO-FIX)
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        """
        Guard:
        - Jika diisi allowed_branch_ids namun working_branch tidak diisi -> set otomatis.
        - Jika allowed_branch_ids kosong & company punya default_branch -> tambahkan default (opsional).
        - Non manager tidak boleh mengubah allowed_branch_ids user lain.
        """
        self._check_permission_on_branch_fields(vals_list)

        users = super().create(vals_list)

        # Auto-fix setelah create
        for user, vals in zip(users, vals_list):
            # Jika working_branch kosong tetapi ada allowed, setkan yang pertama
            if not user.working_branch_id and user.allowed_branch_ids:
                user.working_branch_id = user.allowed_branch_ids[:1]

            # Jika allowed kosong & company punya default -> tambahkan (tidak memaksa)
            if not user.allowed_branch_ids and 'default_branch_id' in user.company_id._fields:
                db = user.company_id.sudo().default_branch_id
                if db:
                    try:
                        user.write({'allowed_branch_ids': [(4, db.id)]})
                        if not user.working_branch_id:
                            user.working_branch_id = db
                    except Exception:
                        # Jangan gagalkan create bila gagal menambah allowed
                        pass

        return users

    def write(self, vals):
        """
        Guard:
        - Non manager tidak boleh mengubah allowed_branch_ids / working_branch_id user lain.
        - Konsistensi: working_branch ∈ allowed_branch_ids dan company cocok.
        - Auto-fix kecil ketika company/allowed berubah.
        """
        self._check_permission_on_branch_fields([vals])

        # Upper guard: jika mengubah user lain & bukan manager -> larang
        if any(key in vals for key in ('allowed_branch_ids', 'working_branch_id')):
            if not self.env.user.has_group('clinic_branch.group_branch_manager'):
                # mengizinkan user mengubah miliknya sendiri
                target_others = self.filtered(lambda u: u.id != self.env.user.id)
                if target_others:
                    raise AccessError(_("You cannot change another user's branch settings."))

        res = super().write(vals)

        # Post-fix konsistensi ringan
        if 'allowed_branch_ids' in vals or 'company_id' in vals or 'working_branch_id' in vals:
            for user in self:
                # Working harus allowed
                if user.working_branch_id and user.allowed_branch_ids and user.working_branch_id not in user.allowed_branch_ids:
                    # pilih alternatif pada company user
                    alt = user.allowed_branch_ids.filtered(lambda b: b.company_id == user.company_id)[:1]
                    user.working_branch_id = alt or False

                # Company harus cocok
                if user.working_branch_id and user.working_branch_id.company_id != user.company_id:
                    # coba default company
                    db = False
                    if 'default_branch_id' in user.company_id._fields:
                        db = user.company_id.sudo().default_branch_id
                        if db and (not user.allowed_branch_ids or db in user.allowed_branch_ids):
                            user.working_branch_id = db
                            continue
                    # fallback: allowed pertama di company
                    alt = user.allowed_branch_ids.filtered(lambda b: b.company_id == user.company_id)[:1]
                    user.working_branch_id = alt or False

        return res

    # -------------------------------------------------------------------------
    # PERMISSIONS
    # -------------------------------------------------------------------------
    def _check_permission_on_branch_fields(self, vals_list):
        """
        Mencegah user non-manager mengubah field branch milik user lain saat create/write batch.
        Dipanggil dari create()/write().
        """
        # Jika environment mengubah user selain self.env.user
        # dan perubahan menyentuh field "branch", wajib group manager.
        touches_branch_field = any(
            any(k in vals for k in ('allowed_branch_ids', 'working_branch_id'))
            for vals in vals_list if isinstance(vals, dict)
        )
        if not touches_branch_field:
            return

        if self.env.su:  # superuser bypass
            return

        if self.env.user.has_group('clinic_branch.group_branch_manager'):
            return

        # create(): self belum ada; write(): self ada
        if self:
            others = self.filtered(lambda u: u.id != self.env.user.id)
            if others:
                raise AccessError(_("Only Branch Managers can change other users' branch settings."))

    # -------------------------------------------------------------------------
    # HELPERS (INTEGRASI SOFT-COUPLED)
    # -------------------------------------------------------------------------
    @api.model
    def _user_allowed_branches(self, user=None, company=None):
        """
        Kembalikan recordset branch yang diperbolehkan untuk user (soft fallback):
        - Jika user.allowed_branch_ids ada -> gunakan itu (filter by company jika diberikan).
        - Kalau kosong -> fallback seluruh branch di company aktif (aman untuk single-company).
        """
        user = user or self.env.user
        Branch = self.env['clinic.branch'].sudo()
        company = company or self.env.company

        allowed = user.allowed_branch_ids
        if allowed:
            if company:
                allowed = allowed.filtered(lambda b: b.company_id == company)
            return allowed

        dom = []
        if company:
            dom.append(('company_id', '=', company.id))
        return Branch.search(dom)

    @api.model
    def _is_branch_allowed_for(self, user, branch):
        if not branch:
            return False
        allowed = self._user_allowed_branches(user=user, company=branch.company_id)
        return branch.id in allowed.ids

    def with_branch(self, branch):
        """
        Helper untuk menerapkan context branch pada env saat ini (berguna untuk pembuatan data turunan).
        """
        branch = branch if isinstance(branch, models.BaseModel) else self.env['clinic.branch'].browse(branch)
        return self.with_context(branch_id=branch.id if branch else False)

    def switch_working_branch(self, branch_id):
        """
        Ganti working_branch user (dipakai wizard atau UX).
        Validasi:
        - branch harus diizinkan
        - company harus cocok
        """
        self.ensure_one()
        branch = self.env['clinic.branch'].browse(branch_id).exists()
        if not branch:
            raise UserError(_("Selected branch does not exist."))
        if not self._is_branch_allowed_for(self, branch):
            raise AccessError(_("You are not allowed to switch to this branch."))
        if branch.company_id != self.company_id:
            # optional: izinkan jika user juga berpindah company (kebijakan organisasi).
            # Di sini kita larang untuk menghindari kebingungan UI.
            raise ValidationError(_("Branch company must match your current company."))
        self.working_branch_id = branch.id
        # opsional: kembalikan env ber-context
        return True

    # -------------------------------------------------------------------------
    # ACTIONS (UI)
    # -------------------------------------------------------------------------
    def action_view_allowed_branches(self):
        """
        Buka daftar cabang yang diizinkan untuk user ini.
        """
        self.ensure_one()
        return {
            'name': _('Allowed Branches'),
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.branch',
            'view_mode': 'tree,form,kanban,search',
            'domain': [('id', 'in', self.allowed_branch_ids.ids)],
            'target': 'current',
            'context': {'default_company_id': self.company_id.id},
        }

    def action_switch_branch_dialog(self):
        """
        (Opsional) Arahkan ke wizard ganti branch bila tersedia.
        """
        self.ensure_one()
        try:
            act = self.env.ref('clinic_branch.action_branch_switch_wizard').read()[0]
            act.setdefault('context', {})
            act['context'] = dict(act['context'],
                                  default_user_id=self.id,
                                  default_current_branch_id=self.working_branch_id.id)
            return act
        except Exception:
            raise UserError(_("Branch switch wizard is not available. Please contact your administrator."))

