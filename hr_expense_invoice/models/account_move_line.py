from odoo import _, api, fields, models
from odoo.exceptions import UserError

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.constrains('account_id', 'display_type')
    def _check_payable_receivable(self):
        for line in self:
            account_type = line.account_id.account_type
            if line.move_id.is_sale_document(include_receipts=True):
                if (line.display_type == 'payment_term') ^ (account_type == 'asset_receivable'):
                    raise UserError(_("Any journal item on a receivable account must have a due date and vice versa."))
            if line.move_id.is_purchase_document(include_receipts=True):
                if not self.expense_id.invoice_id:
                    if (line.display_type == 'payment_term') ^ (account_type == 'liability_payable'):
                        raise UserError(_("Any journal item on a payable account must have a due date and vice versa."))
    