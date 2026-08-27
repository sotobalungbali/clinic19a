
# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, AccessError, UserError


"""
ClinicOne — clinic_branch
File: models/stock_warehouse_inherit.py

Tujuan
------
- Menambahkan field branch pada stock.warehouse (opsional tapi direkomendasikan)
- Menjaga konsistensi multi-company (branch.company == warehouse.company)
- Domain branch mengikuti hak akses user (allowed branches)
- Default pintar: context['branch_id'] → user.working_branch → company.default_branch → allowed pertama
- Smart buttons: melihat Branch yang memakai warehouse ini (sebagai default), dan lokasi cabang terkait
- Utilities integrasi: mapping nilai untuk modul downstream (inventory flow, booking/room device, billing, reports, dsb.)

Catatan
-------
- Tidak mewarisi clinic.branch.mixin untuk menghindari perubahan perilaku bawaan stock.warehouse.
- Field branch_id di sini bersifat opsional agar tetap kompatibel dengan perusahaan yang menggunakan 1 warehouse lintas cabang.
"""


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    # -------------------------------------------------------------------------
    # BRANCH FIELDS & DOMAINS
    # -------------------------------------------------------------------------
    warehouse_allowed_branch_ids = fields.Many2many(
        'clinic.branch',
        string='Allowed Branches (Virtual)',
        compute='_compute_warehouse_allowed_branches',
        help='Daftar cabang yang boleh dipilih sebagai branch pada warehouse ini, '
             'berdasarkan hak akses user dan company aktif.'
    )

    branch_id = fields.Many2one(
        'clinic.branch',
        string='Branch',
        index=True,
        required=False,  # opsional; isi bila warehouse ini memang khusus cabang tertentu
        domain='[("id", "in", warehouse_allowed_branch_ids), ("company_id", "=", company_id)]',
        check_company=True,
        default=lambda self: self._default_branch_for_warehouse(),
        help='Cabang utama yang menggunakan warehouse ini. Opsional.'
    )

    # Pelaporan & Navigasi
    branch_usage_count = fields.Integer(
        string='Used by Branches',
        compute='_compute_counts',
        help='Berapa cabang yang menetapkan warehouse ini sebagai default.'
    )
    branch_location_count = fields.Integer(
        string='Branch Locations',
        compute='_compute_counts',
        help='Berapa location (clinic.branch.location) yang memetakan warehouse ini.'
    )

    # Info turunan (UX)
    branch_company_id = fields.Many2one(
        'res.company',
        string='Branch Company',
        compute='_compute_branch_meta'
    )
    branch_tz = fields.Char(
        string='Branch Timezone',
        compute='_compute_branch_meta'
    )

    # -------------------------------------------------------------------------
    # DEFAULTS / ALLOWED
    # -------------------------------------------------------------------------
    @api.model
    def _default_branch_for_warehouse(self):
        """
        Urutan default:
        1) context['branch_id'] jika valid & diizinkan
        2) user.working_branch_id (jika ada & diizinkan)
        3) company.default_branch_id (jika ada & diizinkan)
        4) allowed branches pertama di company aktif
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

        # 2) working branch (soft)
        if 'working_branch_id' in user._fields:
            wb = user.sudo().working_branch_id
            if wb and self._is_branch_allowed_for_user(wb):
                return wb.id

        # 3) company default (soft)
        if 'default_branch_id' in company._fields:
            db = company.sudo().default_branch_id
            if db and self._is_branch_allowed_for_user(db):
                return db.id

        # 4) fallback
        allowed = self._user_allowed_branches(company=company)
        return allowed[:1].id if allowed else False

    @api.depends_context('uid', 'company')
    def _compute_warehouse_allowed_branches(self):
        for rec in self:
            rec.warehouse_allowed_branch_ids = rec._user_allowed_branches(company=rec.company_id or self.env.company)

    # -------------------------------------------------------------------------
    # COMPUTE
    # -------------------------------------------------------------------------
    @api.depends('branch_id', 'branch_id.company_id', 'branch_id.tz')
    def _compute_branch_meta(self):
        for rec in self:
            rec.branch_company_id = rec.branch_id.company_id if rec.branch_id else False
            rec.branch_tz = rec.branch_id.tz if rec.branch_id else False

    # @api.depends('id', 'company_id')
    @api.depends('company_id')
    def _compute_counts(self):
        Branch = self.env['clinic.branch'].sudo()
        BranchLoc = self.env['clinic.branch.location'].sudo()
        for rec in self:
            try:
                rec.branch_usage_count = Branch.search_count([('default_warehouse_id', '=', rec.id)])
            except Exception:
                rec.branch_usage_count = 0
            try:
                rec.branch_location_count = BranchLoc.search_count([('warehouse_id', '=', rec.id)])
            except Exception:
                rec.branch_location_count = 0

    # -------------------------------------------------------------------------
    # ONCHANGE
    # -------------------------------------------------------------------------
    @api.onchange('company_id')
    def _onchange_company_id_branch_guard(self):
        """
        Bila company warehouse berubah:
        - Kosongkan branch jika tidak se-company
        - Tawarkan default branch pada company baru (jika ada)
        """
        for rec in self:
            if rec.company_id:
                if rec.branch_id and rec.branch_id.company_id != rec.company_id:
                    rec.branch_id = False
                if not rec.branch_id:
                    # coba pasang default perusahaan bila diizinkan
                    if 'default_branch_id' in rec.company_id._fields:
                        db = rec.company_id.sudo().default_branch_id
                        if db and rec._is_branch_allowed_for_user(db):
                            rec.branch_id = db

    @api.onchange('branch_id')
    def _onchange_branch_sync_company(self):
        """
        Sinkronkan company dari branch bila company belum diisi.
        """
        for rec in self:
            if rec.branch_id and not rec.company_id:
                rec.company_id = rec.branch_id.company_id

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains('branch_id', 'company_id')
    def _check_branch_company_consistency(self):
        for rec in self:
            if rec.branch_id and rec.company_id and rec.branch_id.company_id != rec.company_id:
                raise ValidationError(_("Warehouse's branch company must match the warehouse's company."))

    # -------------------------------------------------------------------------
    # CREATE / WRITE
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        """
        - Set branch default bila tidak diisi (mengikuti _default_branch_for_warehouse)
        - Sinkronkan company dari branch bila company kosong
        - Guard hak akses memilih branch
        """
        for vals in vals_list:
            # default branch
            if not vals.get('branch_id'):
                default_bid = self._default_branch_for_warehouse()
                if default_bid:
                    vals['branch_id'] = default_bid

            # sinkron company dari branch
            if vals.get('branch_id') and not vals.get('company_id'):
                b = self.env['clinic.branch'].browse(vals['branch_id'])
                if b.exists():
                    vals['company_id'] = b.company_id.id

            # guard hak akses memilih branch
            if vals.get('branch_id'):
                b = self.env['clinic.branch'].browse(vals['branch_id'])
                if not self._is_branch_allowed_for_user(b):
                    raise AccessError(_("You are not allowed to assign this branch to the warehouse."))

            # konsistensi branch ↔ company jika company sudah diisi
            if vals.get('branch_id') and vals.get('company_id'):
                b = self.env['clinic.branch'].browse(vals['branch_id'])
                if b.exists() and b.company_id.id != vals['company_id']:
                    raise ValidationError(_("Selected branch belongs to a different company."))

        ws = super().create(vals_list)
        return ws

    def write(self, vals):
        """
        - Jaga konsistensi saat branch/company berubah
        - Jika company berubah tanpa ubah branch → kosongkan branch bila tidak se-company
        """
        change_branch = 'branch_id' in vals
        change_company = 'company_id' in vals

        # Guard hak akses & konsistensi branch<->company
        if change_branch and vals.get('branch_id'):
            new_branch = self.env['clinic.branch'].browse(vals['branch_id'])
            if new_branch.exists() and not self._is_branch_allowed_for_user(new_branch):
                raise AccessError(_("You are not allowed to move this warehouse to the selected branch."))
            if change_company and vals.get('company_id'):
                new_company = self.env['res.company'].browse(vals['company_id'])
                if new_branch.company_id != new_company:
                    raise ValidationError(_("Branch company and warehouse company must match."))
            else:
                # sinkron company jika belum diisi / berbeda
                for rec in self:
                    if not rec.company_id:
                        vals.setdefault('company_id', new_branch.company_id.id)
                    elif rec.company_id != new_branch.company_id:
                        raise ValidationError(_("Warehouse already belongs to a different company than the selected branch."))

        if change_company and vals.get('company_id') and not change_branch:
            new_company = self.env['res.company'].browse(vals['company_id'])
            conflict = self.filtered(lambda r: r.branch_id and r.branch_id.company_id != new_company)
            if conflict:
                # kosongkan branch agar dipilih ulang sesuai company baru
                vals['branch_id'] = False

        return super().write(vals)

    # -------------------------------------------------------------------------
    # NAME & DISPLAY
    # -------------------------------------------------------------------------
    def name_get(self):
        """
        Tambahkan suffix branch untuk memudahkan identifikasi lintas cabang.
        """
        res = []
        for rec in self:
            name = super(StockWarehouse, rec).name_get()[0][1] if type(super()) != object else (rec.display_name or rec.name or str(rec.id))
            suffix = ''
            try:
                if rec.branch_id:
                    suffix = " [%s]" % (rec.branch_id.display_name,)
            except Exception:
                pass
            res.append((rec.id, "%s%s" % (name, suffix)))
        return res

    # -------------------------------------------------------------------------
    # ACTIONS / SMART BUTTONS
    # -------------------------------------------------------------------------
    def action_view_branches_using_this(self):
        """
        Tampilkan daftar branch yang memakai warehouse ini sebagai default_warehouse_id.
        """
        self.ensure_one()
        return {
            'name': _('Branches using this Warehouse'),
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.branch',
            'view_mode': 'tree,form,kanban,search',
            'domain': [('default_warehouse_id', '=', self.id)],
            'context': {'search_default_company_id': self.company_id.id},
            'target': 'current',
        }

    def action_view_branch_locations(self):
        """
        Tampilkan daftar clinic.branch.location yang memetakan warehouse ini.
        """
        self.ensure_one()
        return {
            'name': _('Branch Locations'),
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.branch.location',
            'view_mode': 'tree,form,kanban,search',
            'domain': [('warehouse_id', '=', self.id)],
            'context': {'default_warehouse_id': self.id},
            'target': 'current',
        }

    def action_open_branch(self):
        """
        Buka form branch yang terkait (jika diisi).
        """
        self.ensure_one()
        if not self.branch_id:
            raise UserError(_("This warehouse has no branch assigned."))
        return {
            'name': _('Branch'),
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.branch',
            'view_mode': 'form',
            'res_id': self.branch_id.id,
            'target': 'current',
        }

    # -------------------------------------------------------------------------
    # UTILITIES (INTEGRASI SOFT-COUPLED)
    # -------------------------------------------------------------------------
    def integration_values(self):
        """
        Kembalikan mapping nilai yang umum dipakai modul lain (tanpa coupling).
        """
        self.ensure_one()
        # Cari picking types umum bila tersedia pada warehouse (bawaan Odoo)
        in_pt = getattr(self, 'in_type_id', False) or False
        out_pt = getattr(self, 'out_type_id', False) or False
        int_pt = getattr(self, 'int_type_id', False) or False
        return {
            'warehouse_id': self.id,
            'company_id': self.company_id.id,
            'branch_id': self.branch_id.id if self.branch_id else False,
            'picking_type_in_id': in_pt.id if in_pt else False,
            'picking_type_out_id': out_pt.id if out_pt else False,
            'picking_type_internal_id': int_pt.id if int_pt else False,
        }

    def with_branch(self, branch):
        """
        Helper untuk menerapkan context branch pada operasi lanjutan.
        """
        branch = branch if isinstance(branch, models.BaseModel) else self.env['clinic.branch'].browse(branch)
        return self.with_context(branch_id=branch.id if branch else False)

    # -------------------------------------------------------------------------
    # HELPERS — ALLOWED BRANCHES (tanpa dependensi keras)
    # -------------------------------------------------------------------------
    def _user_allowed_branches(self, user=None, company=None):
        """
        Recordset branch yang diizinkan untuk user saat ini.
        Jika user punya allowed_branch_ids → gunakan; jika tidak, fallback ke seluruh branch di company aktif.
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

