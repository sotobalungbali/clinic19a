




"""Runtime-safe routing for the ClinicOne Demo Dataset menu.

Some upgraded ClinicOne databases can legitimately lag the latest source XML-ID
layout. The Demo Dataset menu must therefore load without a hard external parent
reference, then attach itself to the best available ClinicOne menu at runtime.
"""

import logging

_logger = logging.getLogger(__name__)


class DemoMenuBridgeService:
    """Resolve a safe ClinicOne parent without making module upgrade depend on it."""

    def __init__(self, env):
        self.env = env

    def _menu_from_xmlid(self, xmlid):
        menu = self.env.ref(xmlid, raise_if_not_found=False)
        if menu and menu._name == "ir.ui.menu":
            return menu.exists()
        return self.env["ir.ui.menu"]

    def _menu_from_imd(self, module, name=None, name_like=None):
        domain = [
            ("module", "=", module),
            ("model", "=", "ir.ui.menu"),
        ]
        if name:
            domain.append(("name", "=", name))
        elif name_like:
            domain.append(("name", "ilike", name_like))

        metadata = self.env["ir.model.data"].search(domain, order="id", limit=1)
        if not metadata:
            return self.env["ir.ui.menu"]

        return self.env["ir.ui.menu"].browse(metadata.res_id).exists()

    def _find_patient_root(self):
        root = self._menu_from_xmlid("clinic_patient.menu_root")
        if root:
            return root

        root = self._menu_from_imd("clinic_patient", name="menu_root")
        if root:
            return root

        # Last-resort source-drift fallback: any top-level clinic_patient menu
        # recorded in ir.model.data, preferring the one named ClinicOne.
        metadata = self.env["ir.model.data"].search([
            ("module", "=", "clinic_patient"),
            ("model", "=", "ir.ui.menu"),
        ], order="id")
        if metadata:
            menus = self.env["ir.ui.menu"].browse(metadata.mapped("res_id")).exists()
            named_root = menus.filtered(
                lambda menu: not menu.parent_id and menu.name == "ClinicOne"
            )[:1]
            if named_root:
                return named_root
            top_level = menus.filtered(lambda menu: not menu.parent_id)[:1]
            if top_level:
                return top_level

        return self.env["ir.ui.menu"]

    def _find_configuration_parent(self, root):
        configuration = self._menu_from_xmlid(
            "clinic_patient.menu_patient_configuration"
        )
        if configuration:
            return configuration

        configuration = self._menu_from_imd(
            "clinic_patient",
            name="menu_patient_configuration",
        )
        if configuration:
            return configuration

        configuration = self._menu_from_imd(
            "clinic_patient",
            name_like="configuration",
        )
        if configuration:
            return configuration

        if root:
            configuration = self.env["ir.ui.menu"].search([
                ("parent_id", "=", root.id),
                ("name", "=", "Configuration"),
            ], order="sequence, id", limit=1)
            if configuration:
                return configuration

        return self.env["ir.ui.menu"]

    def ensure_parent(self):
        """Attach Demo Dataset below Configuration, ClinicOne root, or nowhere.

        Returning True even when no parent is available is intentional: leaving
        Demo Dataset temporarily top-level is safer than aborting module upgrade.
        """
        demo_menu = self._menu_from_xmlid("clinic_demo.menu_demo_dataset")
        if not demo_menu:
            _logger.warning(
                "ClinicOne Demo Dataset menu bridge skipped: local menu XML-ID is missing."
            )
            return False

        root = self._find_patient_root()
        parent = self._find_configuration_parent(root)

        if not parent and root:
            parent = root

        if parent:
            if demo_menu.parent_id != parent:
                demo_menu.write({"parent_id": parent.id})
            _logger.info(
                "ClinicOne Demo Dataset menu attached under %s (id=%s).",
                parent.display_name,
                parent.id,
            )
        else:
            # Parentless is the compatibility-safe fallback. The menu remains
            # accessible to authorized users and can be re-bridged on next upgrade.
            if demo_menu.parent_id:
                demo_menu.write({"parent_id": False})
            _logger.warning(
                "No compatible ClinicOne parent menu was found. "
                "Demo Dataset remains top-level instead of blocking upgrade."
            )

        return True









