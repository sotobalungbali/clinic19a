# Source model contract — v51

Every model below is preflighted for read/create/write before source generation. Prerequisite records, company scope and consumer contracts are checked separately by the existing owner preflights.

| Model | Required fields | Workflow methods |
|---|---|---|
| clinic.insurance.policy | name company_id branch_id patient_id plan_id insurer_partner_id policy_number start_date end_date state | — |
| clinic.insurance.authorization | name company_id branch_id patient_id policy_id request_date service_date source_type submission_channel line_ids state | action_prepare |
| clinic.insurance.authorization.line | authorization_id description quantity unit_price coverage_percent copay_percent requested_amount | — |
| membership.contract | name company_id currency_id partner_id patient_id plan_id start_date end_date state contract_value | — |
| product.category | name | — |
| product.template | name company_id type uom_id categ_id | — |
| product.product | product_tmpl_id name default_code company_id type is_storable tracking uom_id categ_id standard_price | — |
| stock.location | name usage company_id location_id | — |
| stock.move | origin company_id product_id product_uom product_uom_qty location_id location_dest_id move_line_ids state date clinic_usage_id picked quantity | _action_confirm, _action_done |
| stock.move.line | move_id product_id product_uom_id quantity location_id location_dest_id date | — |
| clinic.treatment.product.usage | name company_id warehouse_id patient_id src_location_id dest_location_id date_usage line_ids state move_ids | action_consume |
| clinic.treatment.product.usage.line | usage_id product_id product_uom product_uom_qty | — |
| account.account | name code account_type company_ids active | — |
| account.journal | name code type company_id default_account_id | — |
| account.move | name ref date company_id journal_id state line_ids | — |
| account.move.line | name account_id debit credit partner_id | — |
| clinic.wallet | name partner_id patient_id company_id currency_id issue_date expiry_policy state balance | action_open |
| clinic.wallet.transaction | name wallet_id transaction_type amount date journal_id state move_id | action_post |
| clinic.execution.log | name session_id company_id event_type date_event | — |
| clinic.procedure.session | name company_id encounter_id procedure_id product_id uom_id quantity planned_start planned_end date_start date_end state | action_start, action_done |










