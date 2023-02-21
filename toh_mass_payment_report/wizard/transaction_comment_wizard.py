from odoo import _, fields, models


class TransactionCommentWizard(models.TransientModel):
    _name = 'transaction.comment.wizard'
    _description = 'Comentario de línea de transacción'
    
    comment = fields.Char('Comentario', required=True)

    def save_comment(self):
        transaction_line_id = self.env['account.payment.transaction.line'].browse(self.env.context.get("active_id"))
        group_approver = self.env.context.get("group_approver")

        transaction_line_id.comment = self.comment
        if group_approver == 1:
            transaction_line_id.write({ 'state_approval': 'denied', 'approver_one_state': 'denied' })
        elif group_approver == 2:
            transaction_line_id.write({ 'state_approval': 'denied', 'approver_two_state': 'denied', 'approver_one_state': 'denied' })
        elif group_approver == 3:
            transaction_line_id.write({ 'state_approval': 'denied', 'approver_three_state': 'denied', 'approver_two_state': 'denied', 'approver_one_state': 'denied' })
        elif group_approver == 4:
            transaction_line_id.write({ 'state_approval': 'denied', 'approver_four_state': 'denied', 'approver_three_state': 'denied', 'approver_two_state': 'denied', 'approver_one_state': 'denied' })
