
# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, AccessError, ValidationError
from odoo.tools import OrderedSet

"""
ClinicOne — clinic_branch
File: models/mixin_branch.py

Tujuan
------
- Memberi field branch_id & company_id dengan guardrail multi-company
- Default pintar (context -> user working branch -> company default -> fallback)
- Domain cabang berdasarkan allowed branches user
- Helper utilitas untuk propagasi context & validasi lintas-modul
- Soft-coupling dengan 38 addon lain melalui pengecekan dinamis field di res.users/res.company

Cara Pakai
---------
class SomeModel(models.Model):
    _name = 'clinic.something'
    _inherit = ['clinic.branch.mixin', 'mail.thread']  # contoh

Catatan
-------
- Tidak memaksa dependensi modul lain. Jika field seperti `working_branch_id`,
  `allowed_branch_ids`, `default_branch_id` belum ada, mixin menggunakan fallback aman.
- Gunakan group `clinic_branch.group_branch_manager` untuk otorisasi perubahan branch
  pada record yang sudah "locked" (lihat _branch_lock_states).
"""


class ClinicBranchMixin(models.AbstractModel):
    _name = 'clinic.branch.mixin'
    _description = 'Clinic Branch Mixin'
    _check_company_auto = True     # aktifkan pemeriksaan otomatis Odoo untuk cross-company
    _branch_required = True        # ubah di subclass bila branch optional
    _branch_lock_states = ('posted', 'done')  # state yang melarang penggantian branch (jika field state ada)

    # ---------- Helpers untuk context key ----------
    _CTX_BRANCH_ID = 'branch_id'
    _CTX_ALLOWED_BRANCH_IDS = 'allowed_branch_ids'

    # ---------- Field bantuan untuk domain dinamis ----------
    # Field ini TIDAK disimpan; hanya untuk dipakai domain di Many2one branch_id
    allowed_branch_ids = fields.Many2many(
        'clinic.branch',
        string='Allowed Branches (Virtual)',
        compute='_compute_allowed_branches',
        help='Daftar cabang yang boleh diakses user saat ini; digunakan untuk domain branch_id.',
    )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        index=True,
        default=lambda self: self._default_company_id(),
        help='Company dari record ini; harus konsisten dengan company pada branch.'
    )

    branch_id = fields.Many2one(
        'clinic.branch',
        string='Branch',
        required=False,  # akan dipaksa required via constrains jika _branch_required=True
        index=True,
        domain='[("id", "in", allowed_branch_ids)]',
        check_company=True,
        help='Cabang pemilik record; domain otomatis mengikuti hak akses user.'
    )

    # (Opsional) Informasi turunan—berguna untuk laporan/UX umum
    branch_tz = fields.Char(
        string='Branch Timezone',
        compute='_compute_branch_meta',
        help='Timezone cabang untuk scheduling/SLA.'
    )
    branch_company_id = fields.Many2one(
        'res.company',
        string='Branch Company',
        compute='_compute_branch_meta',
        help='Company pemilik cabang (redundansi untuk kemudahan filter/laporan).'
    )

    # -------------------------------------------------------------------------
    # DEFAULTS & DOMAIN
    # -------------------------------------------------------------------------

    @api.model
    def _default_company_id(self):
        """
        Urutan default company:
        1) context company (via with_company)
        2) env.company (Odoo 14+)
        3) user.company_id
        """
        # Odoo sudah meng-set env.company sesuai with_company; ini cukup aman.
        return self.env.company.id

    @api.model
    def _default_branch_id(self, company=None):
        """
        Urutan default branch:
        1) context['branch_id'] jika valid & diizinkan
        2) user.working_branch_id (jika field tersedia)
        3) company.default_branch_id (jika field tersedia)
        4) allowed_branch_ids pertama dalam company aktif
        """
        Branch = self.env['clinic.branch']
        user = self.env.user
        company = company or self.env.company

        # 1) context
        ctx_branch_id = self.env.context.get(self._CTX_BRANCH_ID)
        if ctx_branch_id:
            try:
                b = Branch.browse(int(ctx_branch_id)).exists()
            except Exception:
                b = Branch.browse()  # kosong
            if b and self._is_branch_allowed_for_user(b):
                return b.id

        # 2) user.working_branch_id (soft check)
        if 'working_branch_id' in user._fields:
            wb = user.sudo().working_branch_id
            if wb and self._is_branch_allowed_for_user(wb) and wb.company_id == company:
                return wb.id

        # 3) company.default_branch_id (soft check)
        comp = company or user.company_id
        if comp and 'default_branch_id' in comp._fields:
            db = comp.sudo().default_branch_id
            if db and self._is_branch_allowed_for_user(db) and db.company_id == company:
                return db.id

        # 4) fallback: allowed branches by company
        allowed = self._user_allowed_branches(company=company)
        return allowed[:1].id if allowed else False

    @api.depends_context('uid', 'company')
    def _compute_allowed_branches(self):
        for rec in self:
            rec.allowed_branch_ids = self._user_allowed_branches(company=rec.company_id or self.env.company)

    def _user_allowed_branches(self, company=None):
        """
        Ambil daftar branch yang boleh diakses user.
        Soft-coupling: bila user tidak punya field allowed_branch_ids,
        fallback ke semua branch di company aktif user.
        """
        Branch = self.env['clinic.branch']
        user = self.env.user
        company = company or self.env.company

        # Jika user punya field allowed_branch_ids → gunakan itu
        if 'allowed_branch_ids' in user._fields:
            allowed = user.sudo().allowed_branch_ids
            if company:
                allowed = allowed.filtered(lambda b: b.company_id == company)
            if allowed:
                return allowed

        # Fallback: semua branch di company user (aman untuk single-company)
        dom = []
        if company:
            dom.append(('company_id', '=', company.id))
        return Branch.sudo().search(dom)

    def _is_branch_allowed_for_user(self, branch):
        """ True bila branch ada dalam allowed_branch_ids user (dengan fallback aman). """
        if not branch:
            return False
        allowed = self._user_allowed_branches(company=branch.company_id)
        return branch.id in allowed.ids

    # -------------------------------------------------------------------------
    # COMPUTE / ONCHANGE
    # -------------------------------------------------------------------------

    @api.depends('branch_id', 'branch_id.tz', 'branch_id.company_id')
    def _compute_branch_meta(self):
        for rec in self:
            rec.branch_tz = rec.branch_id.tz if rec.branch_id else False
            rec.branch_company_id = rec.branch_id.company_id if rec.branch_id else False

    @api.onchange('company_id')
    def _onchange_company_id_set_branch(self):
        """
        Jika company berubah, sesuaikan branch agar konsisten.
        """
        for rec in self:
            if rec.company_id and rec.branch_id and rec.branch_id.company_id != rec.company_id:
                rec.branch_id = False  # paksa pilih ulang
            if not rec.branch_id and self._branch_required:
                default_bid = rec._default_branch_id(company=rec.company_id)
                if default_bid:
                    rec.branch_id = default_bid

    @api.onchange('branch_id')
    def _onchange_branch_id_set_company(self):
        """
        Pastikan company mengikuti company cabang.
        """
        for rec in self:
            if rec.branch_id and rec.company_id != rec.branch_id.company_id:
                rec.company_id = rec.branch_id.company_id

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------

    @api.constrains('branch_id', 'company_id')
    def _check_branch_company_consistency(self):
        """
        Pastikan branch.company_id == company_id dan branch wajib ada jika _branch_required=True.
        """
        for rec in self:
            if self._branch_required and not rec.branch_id:
                raise ValidationError(_("Branch is required."))
            if rec.branch_id and rec.company_id and rec.branch_id.company_id != rec.company_id:
                raise ValidationError(_("Branch's company must match the record's company."))

    # -------------------------------------------------------------------------
    # CREATE / WRITE GUARDRAILS
    # -------------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        """
        Auto-set company_id & branch_id bila tidak diisi.
        Validasi domain branch terhadap allowed branches user.
        """
        company = self.env.company
        for vals in vals_list:
            # Company
            if not vals.get('company_id'):
                vals['company_id'] = self._default_company_id()

            # Branch
            if not vals.get('branch_id') and self._branch_required:
                default_bid = self._default_branch_id(company=self.env['res.company'].browse(vals['company_id']))
                if default_bid:
                    vals['branch_id'] = default_bid

            # Validasi konsistensi
            if vals.get('branch_id') and vals.get('company_id'):
                b = self.env['clinic.branch'].browse(vals['branch_id'])
                if b.exists() and b.company_id.id != vals['company_id']:
                    raise ValidationError(_("Selected branch belongs to a different company."))

            # Cek hak akses branch
            if vals.get('branch_id') and not self._is_branch_allowed_for_user(self.env['clinic.branch'].browse(vals['branch_id'])):
                raise AccessError(_("You are not allowed to create records in this branch."))

        recs = super().create(vals_list)
        return recs

    def write(self, vals):
        """
        Melarang perubahan branch pada record 'locked' (state ∈ _branch_lock_states) kecuali Branch Manager.
        Menjaga konsistensi company ↔ branch.
        """
        change_branch = 'branch_id' in vals and vals.get('branch_id') is not None
        change_company = 'company_id' in vals and vals.get('company_id') is not None

        if change_branch or change_company:
            # Guard: jika ada state & masuk lock states → butuh group manager
            need_manager = False
            if 'state' in self._fields:
                locked = self.filtered(lambda r: r.state in self._branch_lock_states)
                need_manager = bool(locked)

            if need_manager and not self.env.user.has_group('clinic_branch.group_branch_manager'):
                raise AccessError(_("You cannot change branch/company for locked records."))

        # Konsistensi company <-> branch
        if change_branch:
            new_branch = self.env['clinic.branch'].browse(vals['branch_id']) if vals.get('branch_id') else self.env['clinic.branch']
            if new_branch and new_branch.exists():
                if change_company:
                    # Jika company juga berubah, validasi konsistensi
                    new_company = self.env['res.company'].browse(vals['company_id'])
                    if new_branch.company_id != new_company:
                        raise ValidationError(_("Branch company and record company must be the same."))
                else:
                    # Sinkronkan company agar sama dengan branch.company
                    vals.setdefault('company_id', new_branch.company_id.id)

                # Cek hak akses
                if not self._is_branch_allowed_for_user(new_branch):
                    raise AccessError(_("You are not allowed to move records to this branch."))

        elif change_company and vals.get('company_id'):
            # Jika hanya company berubah, pastikan branch (jika ada) tetap konsisten
            new_company = self.env['res.company'].browse(vals['company_id'])
            conflict = self.filtered(lambda r: r.branch_id and r.branch_id.company_id != new_company)
            if conflict:
                # Kosongkan branch agar dipilih ulang sesuai company baru
                # atau paksa pilih default branch yang sesuai
                if self._branch_required:
                    default_bid = self._default_branch_id(company=new_company)
                    if not default_bid:
                        raise ValidationError(_("No default branch available for the selected company."))
                    vals['branch_id'] = default_bid
                else:
                    vals['branch_id'] = False

        return super().write(vals)

    # -------------------------------------------------------------------------
    # PUBLIC UTILITIES
    # -------------------------------------------------------------------------

    @api.model
    def with_branch(self, branch):
        """
        Convenience: set context branch untuk operasi turunan (create/relational).
        """
        branch = branch if isinstance(branch, models.BaseModel) else self.env['clinic.branch'].browse(branch)
        return self.with_context({
            self._CTX_BRANCH_ID: branch.id if branch else False,
            self._CTX_ALLOWED_BRANCH_IDS: self._user_allowed_branches(company=branch.company_id if branch else self.env.company).ids,
        })

    def ensure_same_branch(self, other, message=None):
        """
        Pastikan self & other berada di branch yang sama (untuk transaksi lintas dokumen).
        """
        self.ensure_one()
        if not other:
            return True
        if hasattr(other, 'branch_id'):
            if self.branch_id and other.branch_id and self.branch_id != other.branch_id:
                raise ValidationError(message or _("Branches must be the same to proceed."))
        return True

    @api.model
    def branch_domain(self, company=None):
        """
        Domain shortcut untuk pencarian berbasis allowed branches + company.
        """
        dom = [('id', 'in', self._user_allowed_branches(company=company or self.env.company).ids)]
        return dom

    # -------------------------------------------------------------------------
    # INTEGRATION HOOKS (untuk 38 addon lain — optional)
    # -------------------------------------------------------------------------

    def _integration_guard_company(self, vals, field_names):
        """
        Sinkronisasi konsistensi company untuk field-field relasi (opsional).
        Misal pada dokumen akunting/inventory, pastikan journal/warehouse se-company
        dengan company record saat ini.
        """
        if not vals or not field_names:
            return
        company_id = vals.get('company_id') or (self[:1].company_id.id if self else self.env.company.id)
        if not company_id:
            return
        company = self.env['res.company'].browse(company_id)

        # Contoh peta field umum (hanya valid bila modul terkait aktif):
        field_company_map = {
            'journal_id': 'account.journal',
            'warehouse_id': 'stock.warehouse',
            'picking_type_id': 'stock.picking.type',
            'location_id': 'stock.location',
            'location_dest_id': 'stock.location',
            'analytic_account_id': 'account.analytic.account',
        }
        for f_name, model_name in field_company_map.items():
            if f_name in field_names and vals.get(f_name):
                rec = self.env[model_name].browse(vals[f_name]).sudo()
                # Banyak model di atas punya company_id; cek secara soft
                if 'company_id' in rec._fields and rec.company_id and rec.company_id != company:
                    raise ValidationError(_("%s must belong to the same company.") % (self._fields[f_name].string or f_name))

    # -------------------------------------------------------------------------
    # NAME DISPLAY (opsional, bantu debugging)
    # -------------------------------------------------------------------------

    def name_get(self):
        res = []
        for rec in self:
            name = super(ClinicBranchMixin, rec).name_get()[0][1] if type(super()) != object else (rec.display_name or str(rec.id))
            suffix = ''
            if rec.branch_id:
                suffix = " [%s]" % (rec.branch_id.display_name,)
            res.append((rec.id, "%s%s" % (name, suffix)))
        return res

