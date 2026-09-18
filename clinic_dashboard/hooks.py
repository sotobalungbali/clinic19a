# Installation seeds only company Dashboard configuration; it does not generate transactional Report Runs.
def post_init_hook(env):
    """Seed company-scoped enterprise dashboards after clinic_reports is ready; never generate transactional reports here."""
    Dashboard = env["clinic.dashboard.board"].sudo()
    for company in env["res.company"].sudo().search([]):
        Dashboard._ensure_default_boards(company)


