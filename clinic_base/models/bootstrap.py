
# -*- coding: utf-8 -*-
from odoo import api, models, SUPERUSER_ID

class ClinicBaseBootstrap(models.AbstractModel):
    _name = "clinic.base.bootstrap"
    _description = "ClinicOne Bootstrap (registry-time checks)"

    def _register_hook(self):
        # Dipanggil setiap registry build (start server / update module)
        env = api.Environment(self.env.cr, SUPERUSER_ID, {})
        self._ensure_stock_warehouse0(env)
        return super()._register_hook()

    @staticmethod
    def _ensure_stock_warehouse0(env):
        """Pastikan XML ID stock.warehouse0 menunjuk ke warehouse WH milik main_company.
        Tidak membuat warehouse baru. No-op jika sudah benar."""
        try:
            # Jika modul stock belum terpasang, tidak ada yang perlu dicek
            if 'stock.warehouse' not in env:
                return

            imd = env['ir.model.data'].sudo()
            company = env.ref('base.main_company')
            # Cari warehouse ber-kode 'WH' milik perusahaan utama
            wh = env['stock.warehouse'].sudo().search([
                ('code', '=', 'WH'),
                ('company_id', '=', company.id),
            ], limit=1)

            if not wh:
                # Tidak ada WH? Jangan bikin—biarkan stock mengelola sendiri.
                return

            xid = imd.search([('module', '=', 'stock'), ('name', '=', 'warehouse0')], limit=1)
            if not xid:
                imd.create({
                    'module': 'stock',
                    'name': 'warehouse0',
                    'model': 'stock.warehouse',
                    'res_id': wh.id,
                    'noupdate': True,
                })
            elif xid.model != 'stock.warehouse' or xid.res_id != wh.id:
                xid.write({'model': 'stock.warehouse', 'res_id': wh.id, 'noupdate': True})
        except Exception:
            # Jangan pernah menggagalkan registry build karena check ini
            pass

