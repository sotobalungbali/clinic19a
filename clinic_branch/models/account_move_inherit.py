
# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, AccessError, UserError
from collections import defaultdict


"""
ClinicOne — clinic_branch
File: models/account_move_inherit.py

Fitur utama
-----------
- Field `branch_id` pada account.move + domain dinamis berbasis hak akses user.
- Default cerdas: context['branch_id'] → user.working_branch → company.default_branch → allowed pertama.
- Propagasi otomatis `branch_id` ke account.move.line (field related, tersimpan & terindeks).
- Guard multi-company: branch.company = move.company; larangan ganti branch pada move posted (kecuali Manager).
- Onchange konsistensi, validasi saat post; helper utilitas untuk modul downstream (reports, billing).
- Soft-coupled: tidak mengubah sequence jurnal, tidak memaksa modul lain.

Konvensi
--------
- Kebijakan wajib branch: `company.policy_branch_scope_accounting` (lihat res_company_inherit.py).
"""


# ============================================================================
# 1) ACCOUNT MOVE (Header)
# ============================================================================

class AccountMove(models.Model):
    _inherit = 'account.move'

    # ------------------------------
    # Allowed branches (virtual)
    # ------------------------------
    move_allowed_branch_ids = fields.Many2many(
        'clinic.branch',
        string='Allowed Branches (Virtual)',
        compute='_compute_move_allowed_branches',
        help='Daftar cabang yang boleh dipilih sesuai hak akses user pada company aktif.'
    )

    # ------------------------------
    # Branch field on header
    # ------------------------------
    branch_id = fields.Many2one(
        'clinic.branch',
        string='Branch',
        index=True,
        required=False,                      # diwajibkan via policy & constraints
        domain='[("id", "in", move_allowed_branch_ids), ("company_id", "=", company_id)]',
        check_company=True,
        help='Cabang pemilik transaksi akunting ini.'
    )

    # UX helpers (turunan; bermanfaat untuk filter/laporan)
    branch_company_id = fields.Many2one(
        'res.company',
        string='Branch Company',
        compute='_compute_branch_meta',
        store=True
    )
    branch_tz = fields.Char(
        string='Branch Timezone',
        compute='_compute_branch_meta',
        store=False
    )

    # ------------------------------
    # COMPUTE
    # ------------------------------
    @api.depends_context('uid', 'company')
    def _compute_move_allowed_branches(self):
        Branch = self.env['clinic.branch'].sudo()
        user = self.env.user
        for rec in self:
            # Pakai allowed_branch_ids user jika ada; fallback semua branch di company aktif
            allowed = False
            if 'allowed_branch_ids' in user._fields and user.allowed_branch_ids:
                allowed = user.sudo().allowed_branch_ids
                if rec.company_id:
                    allowed = allowed.filtered(lambda b: b.company_id == rec.company_id)
            if not allowed:
                dom = [('company_id', '=', (rec.company_id or self.env.company).id)]
                allowed = Branch.search(dom)
            rec.move_allowed_branch_ids = allowed

    @api.depends('branch_id', 'branch_id.company_id', 'branch_id.tz')
    def _compute_branch_meta(self):
        for rec in self:
            rec.branch_company_id = rec.branch_id.company_id if rec.branch_id else False
            rec.branch_tz = rec.branch_id.tz if rec.branch_id else False

    # ------------------------------
    # DEFAULTS
    # ------------------------------
    @api.model
    def _default_branch_for_move(self, vals=None, company=None):
        """
        Urutan default:
        1) context['branch_id'] (jika valid & diizinkan)
        2) user.working_branch_id (jika ada & diizinkan)
        3) company.default_branch_id (jika ada & diizinkan)
        4) allowed branches pertama pada company
        """
        Branch = self.env['clinic.branch']
        user = self.env.user
        comp = company or self.env.company

        # 1) context
        ctx_bid = self.env.context.get('branch_id')
        if ctx_bid:
            b = Branch.browse(int(ctx_bid)).exists()
            if b and self._is_branch_allowed_for_user(b):
                return b.id

        # 2) working branch (soft)
        if 'working_branch_id' in user._fields:
            wb = user.sudo().working_branch_id
            if wb and wb.company_id == comp and self._is_branch_allowed_for_user(wb):
                return wb.id

        # 3) company default (soft)
        if 'default_branch_id' in comp._fields:
            db = comp.sudo().default_branch_id
            if db and self._is_branch_allowed_for_user(db):
                return db.id

        # 4) fallback
        allowed = self._user_allowed_branches(company=comp)
        return allowed[:1].id if allowed else False

    # ------------------------------
    # ONCHANGE
    # ------------------------------
    @api.onchange('company_id')
    def _onchange_company_branch_guard(self):
        for rec in self:
            if rec.company_id:
                # reset branch bila beda company
                if rec.branch_id and rec.branch_id.company_id != rec.company_id:
                    rec.branch_id = False
                # defaultkan branch bila kosong
                if not rec.branch_id:
                    default_bid = rec._default_branch_for_move(company=rec.company_id)
                    if default_bid:
                        rec.branch_id = default_bid

    @api.onchange('branch_id')
    def _onchange_branch_sync_company(self):
        for rec in self:
            if rec.branch_id and rec.company_id and rec.branch_id.company_id != rec.company_id:
                rec.branch_id = False
                return {
                    'warning': {
                        'title': _('Branch/company mismatch'),
                        'message': _('Selected branch belongs to another company.')
                    }
                }

    # ------------------------------
    # CONSTRAINTS
    # ------------------------------
    @api.constrains('branch_id', 'company_id', 'state', 'move_type')
    def _check_branch_policy_and_company(self):
        """
        - Konsistensi company pada branch vs move.
        - Wajib branch jika policy accounting aktif di company.
        - Larangan ganti branch pada move posted (kecuali Branch Manager).
        """
        for rec in self:
            # Konsistensi company
            if rec.branch_id and rec.company_id and rec.branch_id.company_id != rec.company_id:
                raise ValidationError(_("Move's branch company must match the move's company."))

            # Wajib branch bila kebijakan aktif
            if rec.company_id and hasattr(rec.company_id, 'policy_branch_scope_accounting'):
                if rec.company_id.policy_branch_scope_accounting and not rec.branch_id:
                    raise ValidationError(_("Branch is required for accounting moves (company policy)."))

            # Larangan edit branch pada posted
            if rec.state == 'posted' and rec.branch_id:
                # Perubahan branch saat posted ditangani di write() dengan diff check.
                # Di sini cukup memastikan keberadaan branch sesuai policy.

                # (No-op here)
                pass

    # ------------------------------
    # CREATE / WRITE
    # ------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        """
        - Set default branch bila kosong
        - Guard hak akses memilih branch
        - Propagasi branch ke line_ids yang dibuat bersamaan
        """
        Branch = self.env['clinic.branch'].sudo()

        for vals in vals_list:
            # company untuk defaulting
            comp = None
            if vals.get('company_id'):
                comp = self.env['res.company'].browse(vals['company_id']).exists()
            comp = comp or self.env.company

            # default branch
            if not vals.get('branch_id'):
                default_bid = self._default_branch_for_move(vals=vals, company=comp)
                if default_bid:
                    vals['branch_id'] = default_bid

            # guard hak akses
            if vals.get('branch_id'):
                b = Branch.browse(vals['branch_id'])
                if not self._is_branch_allowed_for_user(b):
                    raise AccessError(_("You are not allowed to create an accounting move in this branch."))

            # konsistensi branch-company
            if vals.get('branch_id') and vals.get('company_id'):
                b = Branch.browse(vals['branch_id'])
                if b and b.company_id.id != vals['company_id']:
                    raise ValidationError(_("Selected branch belongs to a different company."))

            # Propagasi ke line_ids create commands
            if vals.get('line_ids'):
                vals['line_ids'] = self._propagate_branch_to_line_commands(vals['line_ids'], vals.get('branch_id'))

        moves = super().create(vals_list)
        return moves

    def write(self, vals):
        """
        - Blokir perubahan branch pada move posted kecuali Branch Manager.
        - Konsistensi branch-company & hak akses.
        - Propagasi branch ke line_ids pada update commands.
        """
        changing_branch = 'branch_id' in vals
        changing_company = 'company_id' in vals
        new_branch = self.env['clinic.branch'].browse(vals.get('branch_id')) if changing_branch and vals.get('branch_id') else False

        # Larangan ubah branch pada posted
        if changing_branch:
            posted = self.filtered(lambda m: m.state == 'posted')
            if posted and not self.env.user.has_group('clinic_branch.group_branch_manager'):
                raise AccessError(_("You cannot change branch on posted moves."))

        # Hak akses & konsistensi (branch ↔ company)
        if changing_branch and new_branch:
            if not self._is_branch_allowed_for_user(new_branch):
                raise AccessError(_("You are not allowed to move this accounting document to the selected branch."))
            if changing_company and vals.get('company_id'):
                new_company = self.env['res.company'].browse(vals['company_id'])
                if new_branch.company_id != new_company:
                    raise ValidationError(_("Branch company and move company must match."))
            else:
                # Sinkronisasi ringan bila perlu (jika move belum punya company — kasus langka)
                for rec in self:
                    if rec.company_id and rec.company_id != new_branch.company_id:
                        raise ValidationError(_("Move already belongs to a different company than the selected branch."))

        if changing_company and vals.get('company_id') and not changing_branch:
            new_company = self.env['res.company'].browse(vals['company_id'])
            conflict = self.filtered(lambda r: r.branch_id and r.branch_id.company_id != new_company)
            if conflict:
                # kosongkan branch agar dipilih ulang sesuai company baru
                vals['branch_id'] = False

        # Propagasi branch ke command line_ids saat write
        if 'line_ids' in vals and vals['line_ids']:
            target_branch_id = vals.get('branch_id') or False
            # Jika tidak ada branch di vals, gunakan branch per-record saat iterasi setelah super()
            if target_branch_id:
                vals['line_ids'] = self._propagate_branch_to_line_commands(vals['line_ids'], target_branch_id)

        res = super().write(vals)

        # Jika branch berubah tapi line.related belum ter-update (karena related store), Odoo akan sync sendiri.
        # Namun jika line_ids diupdate tanpa branch pada vals dan branch header sudah ada,
        # pastikan line baru ikut: lakukan pasca-tulis bila diperlukan.
        if 'line_ids' in vals and not vals.get('branch_id'):
            for move in self:
                for cmd, lid, lvals in (vals.get('line_ids') or []):
                    if cmd == 0 and isinstance(lvals, dict) and not lvals.get('branch_id'):
                        # force sync (related akan menyimpan otomatis, tapi jaga-jaga)
                        pass  # no-op; related field akan mengisi dari move.branch_id

        return res

    # ------------------------------
    # POSTING GUARDS
    # ------------------------------
    def _check_branch_required_before_post(self):
        """
        Pastikan branch ada bila company mewajibkan scope accounting by branch.
        """
        for rec in self:
            if rec.company_id and hasattr(rec.company_id, 'policy_branch_scope_accounting'):
                if rec.company_id.policy_branch_scope_accounting and not rec.branch_id:
                    raise ValidationError(_("Branch is required before posting (company policy)."))

    def _post(self, soft=True):
        """
        Guard sebelum posting:
        - Validasi kewajiban branch (policy)
        - Tidak mengubah urusan sequence jurnal bawaan Odoo
        """
        self._check_branch_required_before_post()
        # Propagasi branch ke baris yang mungkin dibuat otomatis (mis. rounding lines)
        for move in self:
            missing = move.line_ids.filtered(lambda l: not l.branch_id and l.display_type not in ('line_section', 'line_note'))
            if missing and move.branch_id:
                # related akan mengisi otomatis; jika related readonly, tidak perlu write
                # Namun untuk berjaga (mis. customizations), coba tulis diam-diam bila field writable.
                try:
                    writable = missing.filtered(lambda l: not l._fields['branch_id'].readonly)
                    if writable:
                        writable.write({'branch_id': move.branch_id.id})
                except Exception:
                    pass
        return super()._post(soft=soft)

    # ------------------------------
    # UTILITIES
    # ------------------------------
    def _user_allowed_branches(self, user=None, company=None):
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

    def _propagate_branch_to_line_commands(self, commands, branch_id):
        """
        Tambahkan branch_id pada command create (0) & update (1) line jika belum ada.
        commands: list of (cmd, id, vals)
        """
        fixed = []
        for cmd in commands:
            if not isinstance(cmd, (list, tuple)) or len(cmd) < 1:
                fixed.append(cmd)
                continue
            op = cmd[0]
            if op == 0 and isinstance(cmd[2], dict):
                vals = dict(cmd[2])
                vals.setdefault('branch_id', branch_id)
                fixed.append((0, 0, vals))
            elif op == 1 and isinstance(cmd[2], dict):
                vals = dict(cmd[2])
                vals.setdefault('branch_id', branch_id)
                fixed.append((1, cmd[1], vals))
            else:
                fixed.append(cmd)
        return fixed

    # ------------------------------
    # NAME DISPLAY (opsional)
    # ------------------------------
    def name_get(self):
        res = []
        for rec in self:
            name = super(AccountMove, rec).name_get()[0][1] if type(super()) != object else (rec.name or rec.ref or str(rec.id))
            suffix = ''
            try:
                if rec.branch_id:
                    suffix = " [%s]" % (rec.branch_id.display_name,)
            except Exception:
                pass
            res.append((rec.id, "%s%s" % (name, suffix)))
        return res

    # ------------------------------
    # ACTIONS (opsional)
    # ------------------------------
    def action_open_branch(self):
        self.ensure_one()
        if not self.branch_id:
            raise UserError(_("This document has no branch assigned."))
        return {
            'name': _('Branch'),
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.branch',
            'view_mode': 'form',
            'res_id': self.branch_id.id,
            'target': 'current',
        }


# ============================================================================
# 2) ACCOUNT MOVE LINE (Detail)
# ============================================================================

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    # Baris selalu mengikuti branch header (related, disimpan & terindeks)
    branch_id = fields.Many2one(
        'clinic.branch',
        string='Branch',
        related='move_id.branch_id',
        store=True,
        index=True,
        check_company=True,
        readonly=True,
    )

    # Guard tambahan (opsional): konsistensi company id pada entity relasi umum.
    @api.constrains('account_id', 'journal_id', 'company_id')
    def _check_company_consistency_soft(self):
        """
        Banyak entitas (analytic, account, journal) sudah dijaga Odoo.
        Di sini cukup jaga kehati-hatian ringan bila ada kustom.
        """
        # (Kosongkan atau tambahkan validasi tambahan sesuai kebutuhan proyek)
        return True


# ============================================================================
# 3) PAYMENT REGISTER WIZARD (optional soft-coupled propagation)
# ============================================================================
# Catatan: Pada Odoo modern, pembayaran dibuat dari wizard account.payment.register.
# Berikut ini menambahkan field branch_id pada wizard dan mencoba menyuntikkan nilai
# ke pembayaran yang dibuat. Metode internal dapat berubah lintas versi, maka dibuat
# sangat konservatif.

class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    branch_id = fields.Many2one(
        'clinic.branch',
        string='Branch',
        help='Branch of the resulting payment move. Defaults from the invoice or context.',
        default=lambda self: self._default_branch_for_payment_register()
    )

    @api.model
    def _default_branch_for_payment_register(self):
        # Ambil dari context atau dari invoice aktif
        Branch = self.env['clinic.branch']
        ctx_bid = self.env.context.get('branch_id')
        if ctx_bid:
            b = Branch.browse(int(ctx_bid)).exists()
            if b:
                return b.id
        # Dari invoice aktif
        active_model = self.env.context.get('active_model')
        active_ids = self.env.context.get('active_ids') or []
        if active_model == 'account.move' and active_ids:
            inv = self.env['account.move'].browse(active_ids[0]).exists()
            if inv and inv.branch_id:
                return inv.branch_id.id
        # Fallback working branch / company default
        user = self.env.user
        comp = self.env.company
        if 'working_branch_id' in user._fields and user.working_branch_id:
            return user.working_branch_id.id
        if 'default_branch_id' in comp._fields and comp.default_branch_id:
            return comp.default_branch_id.id
        return False

    # Coba injeksi branch ke vals pembayaran yang akan dibuat; metode dapat berubah antar versi.
    def _create_payments(self):
        """
        Override konservatif untuk menyuntikkan branch pada payment moves yang dibuat.
        Memanggil super() lalu menyetel branch pada move hasil, bila memungkinkan.
        """
        action = super()._create_payments()
        try:
            # Cari move yang baru dibuat dari domain action (bila ada)
            if isinstance(action, dict):
                model = action.get('res_model')
                domain = action.get('domain') or []
                if model == 'account.move' and domain:
                    moves = self.env[model].search(domain)
                    for mv in moves:
                        if not mv.branch_id and self.branch_id:
                            # Guard kebijakan company
                            if mv.company_id == self.branch_id.company_id:
                                mv.write({'branch_id': self.branch_id.id})
        except Exception:
            # Jangan patahkan alur pembayaran
            pass
        return action

