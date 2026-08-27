# Odoo 19 Marketing API Audit

Addon 32 delegates Email delivery to Odoo 19 `mass_mailing`.

Native contracts used:
- `mailing.mailing`
- `mailing.mailing.action_put_in_queue()`
- `mailing.mailing.action_cancel()`
- `mailing.trace`
- `mailing.trace.trace_status`
- `utm.campaign` (`name` + user-facing `title` are set explicitly)
- `mass_mailing.group_mass_mailing_user`
- `mass_mailing.group_mass_mailing_campaign`

ClinicOne extends `mailing.mailing` only with
`clinic_marketing_campaign_id` provenance.

Trace statuses handled:
- outgoing
- process
- pending
- sent
- open
- reply
- bounce
- error
- cancel

ClinicOne does not implement its own SMTP queue, bounce tracker, open tracker,
click tracker, or email blacklist.

