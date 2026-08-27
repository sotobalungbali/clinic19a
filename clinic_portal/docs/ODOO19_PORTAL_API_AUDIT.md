# Odoo 19 Portal API Audit

Addon 31 follows the native Odoo 19 portal architecture.

Verified native contracts:
- `odoo.addons.portal.controllers.portal.CustomerPortal`;
- `portal.controllers.portal.pager`;
- `portal.portal_layout`;
- `portal.portal_searchbar`;
- `portal.portal_table`;
- `portal.portal_docs_entry`;
- `portal.wizard.action_open_wizard()`;
- `portal.wizard.user.action_grant_access()`;
- native Sale Portal `/my/orders`;
- native Account Portal `/my/invoices`;
- `account.move.get_portal_url()` for the official invoice page.

The addon does not clone authentication, signup tokens, invoice payment,
invoice PDF, Sale Order portal, or portal access invitation logic.
