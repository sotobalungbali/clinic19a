# UI/UX Matrix

| Model | Search | Enterprise List | Professional Form | Statusbar | Smart Buttons | Body Actions | One2many Buttons | Analysis |
|---|---|---|---|---|---|---|---|---|
| `clinic.wallet` | Yes | Yes | Yes | Yes | Transactions, Rules, Customer | Top-Up, Refund, Adjust In/Out | Open Transaction, Journal Entry, Open Rule | Statement via PDF |
| `clinic.wallet.transaction` | Yes | Yes | Yes | Yes | Wallet, Journal Entry | Header Post/Reserve/Cancel/Reverse | N/A | Pivot + Graph |
| `clinic.wallet.rule` | Yes | Yes | Yes | Yes | N/A | Activate/Deactivate | N/A | Search/grouping |
| `clinic.wallet.portal.mgr.approver` | Yes | Yes | Yes | N/A | N/A | N/A | N/A | Search/grouping |
| `clinic.wallet.portal.request` | Yes | Yes | Yes | Yes | Wallet, Transaction, Journal | Submit/Approve/Reject/Done/Cancel | N/A | Search/grouping |

Shared-model UI includes a patient smart button/page, Clinic Billing wallet-settlement page and action buttons, account.move wallet transaction smart button, and a dedicated Settings app.




