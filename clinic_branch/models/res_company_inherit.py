
# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError, AccessError


class ResCompany(models.Model):
    _inherit = 'res.company'

    # disini juga error
    # is_doctor = fields.Boolean(
    #     string="Is a Doctor",
    #     help="Enable this to indicate that this contact is a doctor."
    # )

    # -------------------------------------------------------------------------
    # DEFAULT BRANCH
    # -------------------------------------------------------------------------
    default_branch_id = fields.Many2one(
        'clinic.branch',
        string='Default Branch',
        domain='[("company_id", "=", id)]',
        check_company=True,
        help='Default branch for this company. Used as a fallback when a record needs a branch.'
    )

    branch_count = fields.Integer(
        string='Branches',
        compute='_compute_branch_count',
        help='Number of clinic branches under this company.'
    )

    # -------------------------------------------------------------------------
    # POLICY FLAGS (Soft-coupled toggles for 38+ ClinicOne addons)
    # Letakkan di company agar multi-company dapat kebijakan berbeda.
    # Semua default True agar scope branch diaktifkan out-of-the-box.
    # -------------------------------------------------------------------------
    policy_branch_scope_patient = fields.Boolean('Scope Patient by Branch', default=True)
    policy_branch_scope_doctor = fields.Boolean('Scope Doctor by Branch', default=True)
    policy_branch_scope_booking = fields.Boolean('Scope Booking by Branch', default=True)
    policy_branch_scope_encounter = fields.Boolean('Scope Encounter/Procedure by Branch', default=True)
    policy_branch_scope_treatment = fields.Boolean('Scope Treatment/Catalog by Branch', default=True)
    policy_branch_scope_inventory = fields.Boolean('Scope Inventory by Branch', default=True)
    policy_branch_scope_room_device = fields.Boolean('Scope Room/Device by Branch', default=True)
    policy_branch_scope_billing = fields.Boolean('Scope Billing/AR/AP by Branch', default=True)
    policy_branch_scope_accounting = fields.Boolean('Scope Accounting by Branch', default=True)
    policy_branch_scope_wallet = fields.Boolean('Scope Wallet by Branch', default=True)
    policy_branch_scope_package = fields.Boolean('Scope Package by Branch', default=True)
    policy_branch_scope_membership = fields.Boolean('Scope Membership by Branch', default=True)
    policy_branch_scope_portal = fields.Boolean('Scope Portal by Branch', default=True)
    policy_branch_scope_reports = fields.Boolean('Scope Reports by Branch', default=True)
    policy_branch_scope_dashboard = fields.Boolean('Scope Dashboard by Branch', default=True)
    policy_branch_scope_ecommerce = fields.Boolean('Scope eCommerce by Branch', default=True)
    policy_branch_scope_marketing = fields.Boolean('Scope Marketing by Branch', default=True)
    policy_branch_scope_emar = fields.Boolean('Scope EMAR by Branch', default=True)
    policy_branch_scope_care_plan = fields.Boolean('Scope Care Plan by Branch', default=True)
    policy_branch_scope_incident_event = fields.Boolean('Scope Incident Event by Branch', default=True)
    policy_branch_scope_post_care = fields.Boolean('Scope Post-care Followup by Branch', default=True)
    policy_branch_scope_telemedicine = fields.Boolean('Scope Telemedicine by Branch', default=True)
    policy_branch_scope_audit = fields.Boolean('Scope Audit by Branch', default=True)
    policy_branch_scope_l10n = fields.Boolean('Scope Localization (L10n) by Branch', default=True)

    # Propagasi default branch ke user baru/eksisting (opsional, soft)
    branch_auto_assign_users = fields.Boolean(
        string='Auto-assign Default Branch to Users',
        default=True,
        help='If enabled, new users in this company get default working/allowed branch '
             '(only if corresponding fields exist on res.users).'
    )

    # Footer/header umum level company (fallback untuk QWeb jika cabang tidak mengisi)
    branch_report_header = fields.Char(
        string='Default Branch Report Header',
        help='Company-level default header for reports when branch-specific header is absent.'
    )
    branch_report_footer = fields.Text(
        string='Default Branch Report Footer',
        help='Company-level default footer for reports when branch-specific footer is absent.'
    )

    # -------------------------------------------------------------------------
    # COMPUTE
    # -------------------------------------------------------------------------
    # @api.depends('id')
    # def _compute_branch_count(self):
    #     Branch = self.env['clinic.branch'].sudo()
    #     for company in self:
    #         company.branch_count = Branch.search_count([('company_id', '=', company.id)])
    @api.model
    def _compute_branch_count(self):
        """Hitung jumlah branch per company.
        Tidak perlu depends; field tidak disimpan (store=False) sehingga dihitung saat dibaca."""
        Branch = self.env['clinic.branch'].sudo()
        for company in self:
            company.branch_count = Branch.search_count([('company_id', '=', company.id)])

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains('default_branch_id')
    def _check_default_branch_company(self):
        for comp in self:
            if comp.default_branch_id and comp.default_branch_id.company_id != comp:
                raise ValidationError(_("Default branch must belong to the same company."))

    # -------------------------------------------------------------------------
    # ONCHANGE
    # -------------------------------------------------------------------------
    @api.onchange('default_branch_id')
    def _onchange_default_branch_id(self):
        """
        Jaga konsistensi company ↔ branch saat memilih default branch.
        """
        if self.default_branch_id and self.default_branch_id.company_id != self:
            self.default_branch_id = False
            return {
                'warning': {
                    'title': _('Branch/company mismatch'),
                    'message': _('Selected branch does not belong to this company.'),
                }
            }

    # -------------------------------------------------------------------------
    # CREATE/WRITE OVERRIDES
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        """
        Setelah company dibuat, bila ada tepat 1 branch milik company tsb, tetapkan sebagai default.
        """
        companies = super().create(vals_list)
        Branch = self.env['clinic.branch'].sudo()
        for comp in companies:
            try:
                if not comp.default_branch_id:
                    branches = Branch.search([('company_id', '=', comp.id)], order='sequence, id')
                    if len(branches) == 1:
                        comp.default_branch_id = branches.id
            except Exception:
                # silent soft-fail
                pass
        return companies

    def write(self, vals):
        """
        - Jika default_branch_id berubah dan auto-assign aktif → propagasi ke user (soft, bila field tersedia).
        - Tidak memaksakan modul user-branch; hanya update bila field ada.
        """
        default_branch_changed = 'default_branch_id' in vals
        res = super().write(vals)

        if default_branch_changed:
            self._propagate_default_branch_to_users()
        return res

    # -------------------------------------------------------------------------
    # ACTIONS (UI)
    # -------------------------------------------------------------------------
    def action_view_branches(self):
        """
        Membuka daftar branch milik company ini.
        """
        self.ensure_one()
        action = {
            'name': _('Branches'),
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.branch',
            'view_mode': 'tree,form,kanban,search',
            'domain': [('company_id', '=', self.id)],
            'context': {'default_company_id': self.id},
            'target': 'current',
        }
        # Jika ada action spesifik, gunakan
        try:
            act_ref = self.env.ref('clinic_branch.action_clinic_branch')
            if act_ref:
                action = act_ref.read()[0]
                action['domain'] = [('company_id', '=', self.id)]
                action['context'] = dict(action.get('context', {}), default_company_id=self.id)
        except Exception:
            pass
        return action

    # -------------------------------------------------------------------------
    # UTILITIES
    # -------------------------------------------------------------------------
    def _suggest_default_branch(self):
        """
        Mengusulkan default branch berdasarkan urutan (sequence, id).
        """
        Branch = self.env['clinic.branch'].sudo()
        self.ensure_one()
        branches = Branch.search([('company_id', '=', self.id)], order='sequence, id', limit=1)
        return branches[:1]

    def ensure_default_branch(self):
        """
        Pastikan company memiliki default_branch. Jika belum ada, coba set otomatis.
        """
        for comp in self:
            if not comp.default_branch_id:
                suggestion = comp._suggest_default_branch()
                if suggestion:
                    comp.default_branch_id = suggestion.id

    def with_branch(self, branch=None):
        """
        Helper untuk memberi context branch (dipakai modul lain).
        """
        self.ensure_one()
        if branch is None:
            branch = self.default_branch_id
        bid = branch.id if getattr(branch, 'id', False) else False
        return self.with_context(branch_id=bid)  # dipakai oleh clinic.branch.mixin

    def branch_scope_enabled(self, area):
        """
        area: string kode area (e.g., 'booking', 'inventory', 'accounting', 'portal', 'reports', ...)
        Mengembalikan True/False berdasarkan policy_* di company ini.
        """
        self.ensure_one()
        mapping = {
            'patient': self.policy_branch_scope_patient,
            'doctor': self.policy_branch_scope_doctor,
            'booking': self.policy_branch_scope_booking,
            'encounter': self.policy_branch_scope_encounter,
            'treatment': self.policy_branch_scope_treatment,
            'inventory': self.policy_branch_scope_inventory,
            'room_device': self.policy_branch_scope_room_device,
            'billing': self.policy_branch_scope_billing,
            'accounting': self.policy_branch_scope_accounting,
            'wallet': self.policy_branch_scope_wallet,
            'package': self.policy_branch_scope_package,
            'membership': self.policy_branch_scope_membership,
            'portal': self.policy_branch_scope_portal,
            'reports': self.policy_branch_scope_reports,
            'dashboard': self.policy_branch_scope_dashboard,
            'ecommerce': self.policy_branch_scope_ecommerce,
            'marketing': self.policy_branch_scope_marketing,
            'emar': self.policy_branch_scope_emar,
            'care_plan': self.policy_branch_scope_care_plan,
            'incident_event': self.policy_branch_scope_incident_event,
            'post_care': self.policy_branch_scope_post_care,
            'telemedicine': self.policy_branch_scope_telemedicine,
            'audit': self.policy_branch_scope_audit,
            'l10n': self.policy_branch_scope_l10n,
        }
        return bool(mapping.get(area, True))

    def get_company_branches(self):
        """
        Kembalikan recordset clinic.branch di company ini.
        """
        Branch = self.env['clinic.branch'].sudo()
        res = Branch.search([('company_id', '=', self.id)])
        return res

    def get_default_branch_values(self):
        """
        Ambil mapping default dari default_branch untuk dipakai modul lain (tanpa coupling).
        """
        self.ensure_one()
        branch = self.default_branch_id
        if not branch:
            branch = self._suggest_default_branch()
        if not branch:
            return {}
        return branch.integration_values()

    # -------------------------------------------------------------------------
    # INTERNAL: PROPAGASI KE USER (SOFT-COUPLED)
    # -------------------------------------------------------------------------
    def _propagate_default_branch_to_users(self):
        """
        Jika default_branch_id berubah dan branch_auto_assign_users==True:
        - Untuk user dalam company ini yang TIDAK punya working_branch_id/allowed_branch_ids:
          set working_branch_id & allowed_branch_ids ke default.
        - Untuk user yang allowed_branch_ids==[old_default] & working=old_default: perbarui ke new_default.
        Hanya berjalan bila field-field tersebut tersedia pada res.users.
        """
        Users = self.env['res.users'].sudo()
        for comp in self:
            if not comp.branch_auto_assign_users:
                continue
            if not comp.default_branch_id:
                continue

            # Cek ketersediaan field
            if not all(f in Users._fields for f in ('company_id',)):
                continue
            has_working = 'working_branch_id' in Users._fields
            has_allowed = 'allowed_branch_ids' in Users._fields

            # Jika tidak ada field pendukung, tidak perlu apa-apa
            if not (has_working or has_allowed):
                continue

            # Ambil users di company ini (aktif saja)
            domain = [('company_id', '=', comp.id)]
            users = Users.search(domain)

            for user in users:
                # Skip superuser secara aman
                if user._is_admin() or user.id == self.env.ref('base.user_admin').id:
                    continue

                updates = {}
                # Kasus 1: user belum punya working/allowed -> auto set ke default
                if has_working and not user.working_branch_id:
                    updates['working_branch_id'] = comp.default_branch_id.id
                if has_allowed and not user.allowed_branch_ids:
                    updates['allowed_branch_ids'] = [(4, comp.default_branch_id.id)]

                # Kasus 2: user hanya memiliki branch lama tunggal yang sama dengan default lama
                # → update ke default baru. (Hanya saat write() mengganti default).
                # Catatan: Tidak menyimpan default lama di sini; untuk kesederhanaan, hanya menambahkan default baru.
                if has_allowed and comp.default_branch_id.id not in user.allowed_branch_ids.ids:
                    # Tambahkan default baru tanpa menghapus yang lama
                    updates.setdefault('allowed_branch_ids', [])
                    updates['allowed_branch_ids'].append((4, comp.default_branch_id.id))

                if updates:
                    try:
                        user.write(updates)
                    except Exception:
                        # Jangan gagalkan perubahan company bila user-write gagal.
                        pass

    # -------------------------------------------------------------------------
    # SECURITY HELPERS
    # -------------------------------------------------------------------------
    def _ensure_branch_admin(self):
        """
        Helper: hanya user dengan group manager branch yang boleh melakukan aksi tertentu.
        """
        if not self.env.user.has_group('clinic_branch.group_branch_manager'):
            raise AccessError(_("You need Branch Manager rights to perform this action."))

