
# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, AccessError, UserError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # sudah di cinic_audit
    # is_doctor = fields.Boolean(
    #     string="Is a Doctor",
    #     help="Enable this to indicate that this contact is a doctor."
    # )

    # -------------------------------------------------------------------------
    # BRANCH ASSIGNMENT (optional on partner)
    # -------------------------------------------------------------------------
    # Catatan: Partner di Odoo bisa "shared" (company_id=False). Maka:
    # - branch_id opsional (boleh False)
    # - check_company=True agar konsistensi otomatis saat company_id ada
    # - domain dinamis mengikuti allowed branches user
    partner_allowed_branch_ids = fields.Many2many(
        'clinic.branch',
        string='Allowed Branches (Virtual)',
        compute='_compute_partner_allowed_branches',
        help='Daftar cabang yang boleh dipilih sesuai hak akses user saat ini.'
    )

    branch_id = fields.Many2one(
        'clinic.branch',
        string='Branch',
        required=False,
        index=True,
        check_company=True,   # validasi otomatis: jika partner.company_id ada, harus se-company dengan branch
        domain='[("id", "in", partner_allowed_branch_ids)]',
        help='Cabang tempat partner ini dikelola. Opsional. '
             'Jika diisi, cabang harus sesuai company (jika company_id diisi).'
    )

    branch_tz = fields.Char(
        string='Branch Timezone',
        compute='_compute_branch_meta',
        help='Timezone cabang; mempermudah penjadwalan & komunikasi.'
    )
    branch_company_id = fields.Many2one(
        'res.company',
        string='Branch Company',
        compute='_compute_branch_meta'
    )

    # -------------------------------------------------------------------------
    # DEFAULTS
    # -------------------------------------------------------------------------
    @api.model
    def _default_branch_for_partner(self, vals=None):
        """
        Default branch untuk partner:
        1) context['branch_id'] (jika valid & diizinkan)
        2) parent/commercial partner.branch_id (jika ada)
        3) user.working_branch_id (jika diizinkan)
        4) company.default_branch_id (jika diizinkan)
        5) allowed branches pertama
        """
        Branch = self.env['clinic.branch']
        user = self.env.user
        company = self.env.company

        # 1) context
        ctx_bid = self.env.context.get('branch_id')
        if ctx_bid:
            b = Branch.browse(int(ctx_bid)).exists()
            if b and self._is_branch_allowed_for_user(b):
                return b.id

        # 2) parent/commercial partner (dari vals jika tersedia)
        if vals:
            parent_id = vals.get('parent_id') or vals.get('commercial_partner_id')
            if parent_id:
                parent = self.browse(parent_id) if isinstance(parent_id, int) else parent_id
                parent = parent.exists()
                if parent and parent.branch_id and self._is_branch_allowed_for_user(parent.branch_id):
                    return parent.branch_id.id

        # 3) working_branch_id (soft check)
        if 'working_branch_id' in user._fields:
            wb = user.sudo().working_branch_id
            if wb and self._is_branch_allowed_for_user(wb):
                return wb.id

        # 4) company.default_branch_id (soft check)
        comp = company
        if 'default_branch_id' in comp._fields:
            db = comp.sudo().default_branch_id
            if db and self._is_branch_allowed_for_user(db):
                return db.id

        # 5) fallback: allowed branches
        allowed = self._user_allowed_branches(company=company)
        return allowed[:1].id if allowed else False

    # -------------------------------------------------------------------------
    # COMPUTE
    # -------------------------------------------------------------------------
    @api.depends_context('uid', 'company')
    def _compute_partner_allowed_branches(self):
        for rec in self:
            rec.partner_allowed_branch_ids = rec._user_allowed_branches(company=rec.company_id or self.env.company)

    @api.depends('branch_id', 'branch_id.tz', 'branch_id.company_id')
    def _compute_branch_meta(self):
        for rec in self:
            rec.branch_tz = rec.branch_id.tz if rec.branch_id else False
            rec.branch_company_id = rec.branch_id.company_id if rec.branch_id else False

    # -------------------------------------------------------------------------
    # ONCHANGE
    # -------------------------------------------------------------------------
    @api.onchange('company_id')
    def _onchange_company_id_branch_guard(self):
        """
        Jika company partner berubah & tidak cocok dengan branch, kosongkan branch (agar dipilih ulang).
        """
        for rec in self:
            if rec.company_id and rec.branch_id and rec.branch_id.company_id != rec.company_id:
                rec.branch_id = False  # pilih ulang sesuai company

    @api.onchange('parent_id')
    def _onchange_parent_inherit_branch(self):
        """
        Jika parent dipilih dan partner belum punya branch, warisi dari parent.
        """
        for rec in self:
            if rec.parent_id and not rec.branch_id and rec.parent_id.branch_id:
                if rec._is_branch_allowed_for_user(rec.parent_id.branch_id):
                    rec.branch_id = rec.parent_id.branch_id

    @api.onchange('branch_id')
    def _onchange_branch_sync_company(self):
        """
        Jika branch dipilih dan partner.company_id kosong, set company sesuai branch.
        Jika company ada tapi berbeda, tampilkan peringatan & kosongkan branch.
        """
        for rec in self:
            if rec.branch_id:
                if rec.company_id:
                    if rec.branch_id.company_id != rec.company_id:
                        rec.branch_id = False
                        return {
                            'warning': {
                                'title': _('Branch/company mismatch'),
                                'message': _('Selected branch belongs to a different company than this partner.')
                            }
                        }
                else:
                    # sinkronkan company hanya bila partner saat ini belum punya company
                    rec.company_id = rec.branch_id.company_id

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains('branch_id', 'company_id')
    def _check_branch_company_consistency(self):
        """
        Jika company_id ada, branch.company_id harus sama. Jika branch diisi, pastikan user berhak.
        """
        for rec in self:
            if rec.branch_id and rec.company_id and rec.branch_id.company_id != rec.company_id:
                raise ValidationError(_("Branch's company must match the partner's company."))
            if rec.branch_id and not rec._is_branch_allowed_for_user(rec.branch_id):
                raise AccessError(_("You are not allowed to assign this branch to the partner."))

    # -------------------------------------------------------------------------
    # CREATE / WRITE
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        """
        - Tetapkan default branch (opsional) mengikuti urutan default.
        - Guard hak akses terhadap branch yang dipilih.
        - Sinkronkan company bila partner belum punya company dan branch ditentukan.
        - Warisi branch dari parent/commercial partner jika memungkinkan.
        """
        for vals in vals_list:
            # default branch jika tidak diisi
            if not vals.get('branch_id'):
                default_bid = self._default_branch_for_partner(vals=vals)
                if default_bid:
                    vals['branch_id'] = default_bid

            # warisi dari parent/commercial jika masih belum ada
            if not vals.get('branch_id'):
                parent_id = vals.get('parent_id') or vals.get('commercial_partner_id')
                if parent_id:
                    parent = self.browse(parent_id) if isinstance(parent_id, int) else parent_id
                    parent = parent.exists()
                    if parent and parent.branch_id and self._is_branch_allowed_for_user(parent.branch_id):
                        vals['branch_id'] = parent.branch_id.id

            # sinkronkan company jika kosong
            if vals.get('branch_id') and not vals.get('company_id'):
                b = self.env['clinic.branch'].browse(vals['branch_id'])
                if b.exists():
                    vals['company_id'] = b.company_id.id

            # guard hak akses terhadap branch
            if vals.get('branch_id'):
                b = self.env['clinic.branch'].browse(vals['branch_id'])
                if not self._is_branch_allowed_for_user(b):
                    raise AccessError(_("You are not allowed to create a partner in this branch."))

            # konsistensi branch ↔ company jika company sudah diisi
            if vals.get('branch_id') and vals.get('company_id'):
                b = self.env['clinic.branch'].browse(vals['branch_id'])
                if b.exists() and b.company_id.id != vals['company_id']:
                    raise ValidationError(_("Selected branch belongs to a different company."))

        partners = super().create(vals_list)
        return partners

    def write(self, vals):
        """
        - Menjaga konsistensi ketika branch/company berubah.
        - Guard hak akses untuk perubahan branch.
        - Jika parent berganti & branch kosong → warisi branch parent.
        """
        change_branch = 'branch_id' in vals
        change_company = 'company_id' in vals

        if change_branch and vals.get('branch_id'):
            new_branch = self.env['clinic.branch'].browse(vals['branch_id'])
            if new_branch.exists() and not self._is_branch_allowed_for_user(new_branch):
                raise AccessError(_("You are not allowed to move this partner to the selected branch."))

        # Konsistensi branch<->company:
        if change_branch and vals.get('branch_id'):
            new_branch = self.env['clinic.branch'].browse(vals['branch_id'])
            if change_company and vals.get('company_id'):
                new_company = self.env['res.company'].browse(vals['company_id'])
                if new_branch.company_id != new_company:
                    raise ValidationError(_("Branch company and partner company must match."))
            else:
                # jika company tidak ikut diubah & partner.company_id False → sinkronkan
                for rec in self:
                    if not rec.company_id:
                        vals.setdefault('company_id', new_branch.company_id.id)
                    elif rec.company_id != new_branch.company_id:
                        # jika partner sudah punya company beda → tolak
                        raise ValidationError(_("Partner already belongs to a different company than the selected branch."))

        if change_company and vals.get('company_id') and not change_branch:
            new_company = self.env['res.company'].browse(vals['company_id'])
            conflict = self.filtered(lambda r: r.branch_id and r.branch_id.company_id != new_company)
            if conflict:
                # kosongkan branch agar dipilih ulang sesuai company baru
                vals['branch_id'] = False

        res = super().write(vals)

        # Warisi branch dari parent bila branch kosong & parent ada
        if 'parent_id' in vals and not vals.get('branch_id'):
            for rec in self:
                if rec.parent_id and not rec.branch_id and rec.parent_id.branch_id:
                    if rec._is_branch_allowed_for_user(rec.parent_id.branch_id):
                        try:
                            rec.write({'branch_id': rec.parent_id.branch_id.id})
                        except Exception:
                            # jangan gagalkan write utama
                            pass

        return res

    # -------------------------------------------------------------------------
    # HELPERS (soft-coupled, tanpa dependensi keras)
    # -------------------------------------------------------------------------
    def _user_allowed_branches(self, user=None, company=None):
        """
        Recordset branch yang diizinkan untuk user saat ini.
        Jika user memiliki allowed_branch_ids → gunakan (filter by company jika diberikan).
        Jika tidak, fallback ke seluruh branch di company aktif.
        """
        user = user or self.env.user
        Branch = self.env['clinic.branch'].sudo()
        company = company or self.env.company

        if 'allowed_branch_ids' in user._fields and user.allowed_branch_ids:
            allowed = user.sudo().allowed_branch_ids
            if company:
                allowed = allowed.filtered(lambda b: b.company_id == company)
            return allowed

        dom = []
        if company:
            dom.append(('company_id', '=', company.id))
        return Branch.search(dom)

    def _is_branch_allowed_for_user(self, branch):
        if not branch:
            return False
        allowed = self._user_allowed_branches(company=branch.company_id)
        return branch.id in allowed.ids

    def with_branch(self, branch):
        """
        Terapkan context branch untuk operasi turunan (dipakai bridge lain).
        """
        branch = branch if isinstance(branch, models.BaseModel) else self.env['clinic.branch'].browse(branch)
        return self.with_context(branch_id=branch.id if branch else False)

    # -------------------------------------------------------------------------
    # ACTIONS (opsional, bantu navigasi)
    # -------------------------------------------------------------------------
    def action_open_branch(self):
        """
        Buka form cabang yang terhubung dengan partner ini.
        """
        self.ensure_one()
        if not self.branch_id:
            raise UserError(_("Partner has no branch assigned."))
        return {
            'name': _('Branch'),
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.branch',
            'view_mode': 'form',
            'res_id': self.branch_id.id,
            'target': 'current',
        }

