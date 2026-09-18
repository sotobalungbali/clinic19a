# ClinicOne v52 — Stock owner API closure

## Install and resume the same run

1. Stop Odoo and replace BOTH complete addon folders from this ZIP: clinic_inventory and clinic_demo.
2. Start Odoo, Update Apps List, upgrade clinic_inventory to 19.0.1.0.4 FIRST, then clinic_demo to 19.0.1.0.52.
3. Open the SAME Demo Run; keep Demo Safe Mode enabled. Click Refresh Compatibility.
4. Once Compatible, click Complete Source Journeys. Successful source/evidence completion resumes acceptance checkpoints and runs Validate automatically.
5. Expected target: READY FOR DEMO. Do not Reset Dataset, create a new run or manually edit fingerprint/checkpoint values.

Other companions remain unchanged. The new suite fingerprint pins clinic_inventory 19.0.1.0.4, so mixing the new demo with the old stock owner is blocked before business creation. Supported migration includes stored v51 and all previously accepted lineages, with the Resources historical checkpoint mapping retained.

## Whole-path repair

The actual failure is in the clinic_inventory owner override of stock.move._action_confirm. Native Odoo 19 calls it with create_proc=False from _create_backorder. This call also occurs on an EMPTY backorder recordset, so the traceback does not prove the demo receipt quantity is short. Suppressing backorders would hide the incompatible method contract.

The full owner audit checked all 15 Stock/Product overrides against the available native Odoo 19 source and found three keyword signature discrepancies. These are corrected together:

| Owner method | Native keyword preserved |
|---|---|
| stock.move._action_confirm | create_proc=True default; explicit False forwarded unchanged |
| stock.move._action_assign | force_qty=False default; explicit quantities forwarded unchanged |
| stock.rule._get_stock_move_values | location_dest_id, including the owner preview caller |

Clinical pre-confirm, expiration, governance and post-done hooks remain. Native return values and existing default behavior are retained. No manual stock posting, production-sequence fallback, SQL or sudo business write is added.

The same audit found Stock Rule hints writing a legacy stock.move.name payload. Hints now remain in the existing description_picking field; stock.move does not receive the unsupported name key. Route policy, origin and destination logic otherwise remain unchanged.

Source Journeys preflight now inspects the actual stock.move method signatures for create_proc, force_qty and cancel_backorder before the first source business mutation. Existing field/comodel checks, actor entitlements, transaction savepoint, deterministic names/dates and source-backed report requirements remain active. Failed RPC writes are transaction-bound; the same deterministic references are resolved on retry rather than resetting completed data.

## Verification and acceptance boundary

See TEST_REPORT_52.md and validation_52 for evidence. The package includes a reusable native-signature audit in clinic_inventory/tools/check_native_stock_signatures.py. Supply the native Odoo addons directory to run it.

MOVE_FORWARD_READY: NO until native runtime acceptance. Source/static success does not establish native generation, concurrency or disposable-database reset/regeneration success. The user database must produce READY FOR DEMO before presentation readiness is established.









