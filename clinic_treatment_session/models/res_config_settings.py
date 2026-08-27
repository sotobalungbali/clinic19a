# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class ResConfigSettings(models.TransientModel):
    """
    Global configuration for Clinic Treatment Session.

    Semua pengaturan di sini disimpan di ir.config_parameter dengan prefix:
        clinic_treatment_session.*

    Integrasi dengan modul lain di ClinicOne:

    - Reminder & Auto No-show:
        * clinic_treatment_session.reminder_offset_hours
        * clinic_treatment_session.auto_no_show_enabled
        * clinic_treatment_session.auto_no_show_hours
      Dipakai oleh cron di model clinic.treatment.session
      (cron_send_session_reminders dan cron auto-no-show jika kita buat nanti).

    - Inventory / Stock Consumption:
        * clinic_treatment_session.location_src_id
        * clinic_treatment_session.location_dest_id
      Dipakai oleh clinic.treatment.session.line._get_default_consumption_locations()
      untuk menentukan lokasi sumber & tujuan stock.move konsumsi.

    - Billing Mode:
        * clinic_treatment_session.auto_create_billing
        * clinic_treatment_session.billing_mode
      Bisa dibaca oleh addon:
        - clinic_billing        (billing klinik)
        - clinic_wallet         (wallet & voucher)
        - clinic_package        (paket tindakan)
        - clinic_membership     (membership & benefit)
      untuk menentukan bagaimana sebuah sesi di-bill setelah DONE.

    - Coverage (Package, Membership, Wallet):
        * clinic_treatment_session.package_auto_deduct
        * clinic_treatment_session.membership_auto_apply
        * clinic_treatment_session.wallet_auto_consume

      Flag ini memberi panduan global ke addon terkait:
        - apakah komponen paket harus otomatis dikurangi
        - apakah benefit membership di-apply otomatis
        - apakah saldo wallet / voucher harus dikonsumsi otomatis
    """

    _inherit = "res.config.settings"

    # -------------------------------------------------------------------------
    # REMINDER & NO-SHOW SETTINGS
    # -------------------------------------------------------------------------
    session_reminder_offset_hours = fields.Integer(
        string="Session Reminder Offset (Hours)",
        help=(
            "Number of hours before the session start time when reminder "
            "emails/notifications should be sent.\n"
            "Used by clinic.treatment.session cron job.\n"
            "Stored in system parameter: "
            "'clinic_treatment_session.reminder_offset_hours'."
        ),
        default=2,
    )

    session_auto_no_show_enabled = fields.Boolean(
        string="Enable Auto No-show",
        help=(
            "If enabled, sessions that remain in 'Draft' or 'Confirmed' state "
            "for too long after their planned start time can be automatically "
            "marked as 'No-show' by a cron job.\n"
            "Stored in system parameter: "
            "'clinic_treatment_session.auto_no_show_enabled'."
        ),
        default=False,
    )

    session_auto_no_show_hours = fields.Integer(
        string="Auto No-show Threshold (Hours)",
        help=(
            "Number of hours after the planned start time after which a session "
            "may be automatically considered a No-show.\n"
            "This value is only used if 'Enable Auto No-show' is active.\n"
            "Stored in system parameter: "
            "'clinic_treatment_session.auto_no_show_hours'."
        ),
        default=2,
    )

    # -------------------------------------------------------------------------
    # INVENTORY / STOCK CONSUMPTION SETTINGS
    # -------------------------------------------------------------------------
    session_location_src_id = fields.Many2one(
        "stock.location",
        string="Default Source Location",
        domain="[('usage', 'in', ('internal', 'transit', 'view'))]",
        help=(
            "Default source location for stock consumption when session lines "
            "with products (type 'product' or 'consu') are marked as consumed.\n\n"
            "Used by Clinic Treatment Session lines if no specific location is "
            "set on the line.\n"
            "Stored in system parameter: "
            "'clinic_treatment_session.location_src_id'."
        ),
    )

    session_location_dest_id = fields.Many2one(
        "stock.location",
        string="Default Destination Location",
        domain="[('usage', 'in', ('customer', 'inventory', 'production', 'transit', 'view', 'supplier'))]",
        help=(
            "Default destination location for stock consumption when session "
            "lines are marked as consumed.\n\n"
            "Typically configured as a 'Consumption', 'Scrap', or dedicated "
            "clinic consumption location.\n"
            "Stored in system parameter: "
            "'clinic_treatment_session.location_dest_id'."
        ),
    )

    # -------------------------------------------------------------------------
    # BILLING MODE & INTEGRATION FLAGS
    # -------------------------------------------------------------------------
    session_auto_create_billing = fields.Boolean(
        string="Auto Create Billing on Done",
        help=(
            "If enabled, ClinicOne billing modules may automatically create "
            "billing documents (clinic.billing.invoice or customer invoice) "
            "when a treatment session is marked as Done.\n\n"
            "This is only a global flag; the actual behavior is implemented "
            "in billing-related addons (e.g., clinic_billing).\n"
            "Stored in system parameter: "
            "'clinic_treatment_session.auto_create_billing'."
        ),
        default=False,
    )

    session_billing_mode = fields.Selection(
        [
            ("clinic_billing", "Clinic Billing (clinic.billing.invoice)"),
            ("account_invoice", "Standard Customer Invoice (account.move)"),
            ("none", "No Automatic Billing"),
        ],
        string="Default Billing Mode",
        default="clinic_billing",
        help=(
            "Preferred billing workflow for treatment sessions:\n"
            "- 'Clinic Billing': use ClinicOne clinic billing module.\n"
            "- 'Standard Customer Invoice': create standard account.move invoices.\n"
            "- 'No Automatic Billing': do not auto-create any billing document.\n\n"
            "Actual behavior is implemented by billing-related addons, which "
            "should read this configuration.\n"
            "Stored in system parameter: "
            "'clinic_treatment_session.billing_mode'."
        ),
    )

    # -------------------------------------------------------------------------
    # COVERAGE / PACKAGE / MEMBERSHIP / WALLET
    # -------------------------------------------------------------------------
    session_package_auto_deduct = fields.Boolean(
        string="Auto Deduct Package Balance",
        help=(
            "If enabled, when a session line is linked to a package component "
            "(clinic.package.line), ClinicOne package addons may automatically "
            "deduct the package balance when the session is completed.\n"
            "Stored in system parameter: "
            "'clinic_treatment_session.package_auto_deduct'."
        ),
        default=True,
    )

    session_membership_auto_apply = fields.Boolean(
        string="Auto Apply Membership Benefits",
        help=(
            "If enabled, membership benefits (clinic.membership.benefit) may be "
            "applied automatically to eligible session lines when preparing "
            "billing/invoices.\n"
            "Stored in system parameter: "
            "'clinic_treatment_session.membership_auto_apply'."
        ),
        default=True,
    )

    session_wallet_auto_consume = fields.Boolean(
        string="Auto Consume Wallet / Vouchers",
        help=(
            "If enabled, ClinicOne wallet/voucher addons (clinic_wallet) may "
            "automatically consume wallet balances or vouchers when billing "
            "is generated for a session.\n"
            "Stored in system parameter: "
            "'clinic_treatment_session.wallet_auto_consume'."
        ),
        default=True,
    )

    # -------------------------------------------------------------------------
    # INTERNAL HELPERS: READ/WRITE ir.config_parameter
    # -------------------------------------------------------------------------
    @api.model
    def _get_int_param(self, key, default=0):
        """
        Helper untuk membaca system parameter integer.
        """
        Param = self.env["ir.config_parameter"].sudo()
        value = Param.get_param(key, default=str(default))
        try:
            return int(value)
        except Exception:
            return default

    @api.model
    def _get_bool_param(self, key, default=False):
        """
        Helper untuk membaca system parameter boolean.
        Menerima representasi '1', '0', 'True', 'False', dll.
        """
        Param = self.env["ir.config_parameter"].sudo()
        value = Param.get_param(key, "1" if default else "0")
        return str(value).lower() in ("1", "true", "t", "yes", "y")

    @api.model
    def _get_m2o_param(self, key):
        """
        Helper untuk membaca system parameter Many2one
        (disimpan sebagai ID integer).
        """
        Param = self.env["ir.config_parameter"].sudo()
        value = Param.get_param(key, default="0")
        try:
            record_id = int(value)
        except Exception:
            record_id = 0
        return record_id or False

    @api.model
    def _get_str_param(self, key, default=""):
        """
        Helper untuk membaca system parameter string.
        """
        Param = self.env["ir.config_parameter"].sudo()
        return Param.get_param(key, default)

    # -------------------------------------------------------------------------
    # OVERRIDE: get_values / set_values
    # -------------------------------------------------------------------------
    @api.model
    def get_values(self):
        """
        Baca semua nilai dari ir.config_parameter dan populate ke field wizard.
        """
        res = super(ResConfigSettings, self).get_values()
        Param = self.env["ir.config_parameter"].sudo()

        # Reminder & No-show
        reminder_offset = self._get_int_param(
            "clinic_treatment_session.reminder_offset_hours", default=2
        )
        auto_no_show = self._get_bool_param(
            "clinic_treatment_session.auto_no_show_enabled", default=False
        )
        auto_no_show_hours = self._get_int_param(
            "clinic_treatment_session.auto_no_show_hours", default=2
        )

        # Locations
        src_loc_id = self._get_m2o_param(
            "clinic_treatment_session.location_src_id"
        )
        dest_loc_id = self._get_m2o_param(
            "clinic_treatment_session.location_dest_id"
        )

        # Billing
        auto_billing = self._get_bool_param(
            "clinic_treatment_session.auto_create_billing", default=False
        )
        billing_mode = self._get_str_param(
            "clinic_treatment_session.billing_mode", default="clinic_billing"
        )

        # Coverage flags
        package_auto_deduct = self._get_bool_param(
            "clinic_treatment_session.package_auto_deduct", default=True
        )
        membership_auto_apply = self._get_bool_param(
            "clinic_treatment_session.membership_auto_apply", default=True
        )
        wallet_auto_consume = self._get_bool_param(
            "clinic_treatment_session.wallet_auto_consume", default=True
        )

        res.update(
            {
                # Reminder & No-show
                "session_reminder_offset_hours": reminder_offset,
                "session_auto_no_show_enabled": auto_no_show,
                "session_auto_no_show_hours": auto_no_show_hours,
                # Locations
                "session_location_src_id": src_loc_id,
                "session_location_dest_id": dest_loc_id,
                # Billing
                "session_auto_create_billing": auto_billing,
                "session_billing_mode": billing_mode,
                # Coverage
                "session_package_auto_deduct": package_auto_deduct,
                "session_membership_auto_apply": membership_auto_apply,
                "session_wallet_auto_consume": wallet_auto_consume,
            }
        )
        return res

    def set_values(self):
        """
        Simpan semua nilai dari wizard ke ir.config_parameter.
        """
        super(ResConfigSettings, self).set_values()
        Param = self.env["ir.config_parameter"].sudo()

        for record in self:
            # Reminder & No-show
            Param.set_param(
                "clinic_treatment_session.reminder_offset_hours",
                str(record.session_reminder_offset_hours or 0),
            )
            Param.set_param(
                "clinic_treatment_session.auto_no_show_enabled",
                "1" if record.session_auto_no_show_enabled else "0",
            )
            Param.set_param(
                "clinic_treatment_session.auto_no_show_hours",
                str(record.session_auto_no_show_hours or 0),
            )

            # Locations
            Param.set_param(
                "clinic_treatment_session.location_src_id",
                str(record.session_location_src_id.id or 0),
            )
            Param.set_param(
                "clinic_treatment_session.location_dest_id",
                str(record.session_location_dest_id.id or 0),
            )

            # Billing
            Param.set_param(
                "clinic_treatment_session.auto_create_billing",
                "1" if record.session_auto_create_billing else "0",
            )
            Param.set_param(
                "clinic_treatment_session.billing_mode",
                record.session_billing_mode or "clinic_billing",
            )

            # Coverage
            Param.set_param(
                "clinic_treatment_session.package_auto_deduct",
                "1" if record.session_package_auto_deduct else "0",
            )
            Param.set_param(
                "clinic_treatment_session.membership_auto_apply",
                "1" if record.session_membership_auto_apply else "0",
            )
            Param.set_param(
                "clinic_treatment_session.wallet_auto_consume",
                "1" if record.session_wallet_auto_consume else "0",
            )
