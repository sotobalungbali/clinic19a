# HARD GATE 4 - Full Structural Inventory

## Owned persistent models

1. `clinic.marketing.preference`
   - exact Patient Contact / Patient Card;
   - Email and WhatsApp opt-in/out;
   - global Do Not Contact;
   - consent source/evidence timestamps.

2. `clinic.marketing.segment`
   - structured Patient audience criteria;
   - demographics;
   - Patient stages/tags;
   - Membership;
   - completed-visit recency/inactivity;
   - latest NPS class;
   - required communication channel.

3. `clinic.marketing.promotion`
   - informational or owner-linked promotion wrapper;
   - Billing Voucher / Package Voucher / Treatment Pricelist / eCommerce source;
   - validity period;
   - patient-facing headline/CTA/terms.

4. `clinic.marketing.campaign`
   - Draft -> Audience Prepared -> Ready -> Running -> Completed/Cancelled;
   - Segment;
   - Promotion;
   - Branch;
   - Email/WhatsApp channel policy;
   - native `mailing.mailing`;
   - native `utm.campaign`;
   - delivery KPIs.

5. `clinic.marketing.recipient`
   - immutable audience snapshot;
   - patient/contact;
   - preference evidence;
   - Email/WhatsApp eligibility;
   - exclusion reason;
   - delivery evidence.

6. `clinic.marketing.message`
   - governed WhatsApp message;
   - destination/body snapshot;
   - queued/opened/sent/failed/cancelled evidence;
   - provider extension reference.

## Additive inherited models

- `res.company`
- `res.config.settings`
- `res.partner`
- `clinic.patient`
- `clinic.branch`
- `mailing.mailing`
- `clinic.ecommerce.catalog.item`

## Automation

- Campaign sequence
- hourly running-campaign delivery sync
- WhatsApp provider-extension queue cron
- daily Promotion expiry

## UI

Every owned persistent model has Search/List/Form.
Additional:
- Campaign Kanban
- Recipient Pivot
- Recipient Graph
- statusbars
- smart buttons
- body buttons
- One2many recipient/campaign row buttons

