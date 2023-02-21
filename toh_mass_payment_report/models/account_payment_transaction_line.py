from odoo import _, api, fields, models
import logging

_logger = logging.getLogger(__name__)


class AccountPaymentTransactionLine(models.Model):
    _name = 'account.payment.transaction.line'
    _description = 'Línea de transacción de pago'
    
    type = fields.Selection([
        ('invoice', 'Factura de proveedor'),
        ('purchase', 'Órden de compra'),
        ('expense', 'Reporte de gasto'),
        ('tax', 'Impuesto'),
    ], string='Tipo de transacción', required=True)
    approver_one_state = fields.Selection([
        ('pending', 'Pendiente'),
        ('approved', 'Aprobado'),
        ('denied', 'Rechazado'),
    ], string='Estado primera aprobación', default='pending', readonly=True)
    approver_two_state = fields.Selection([
        ('pending', 'Pendiente'),
        ('approved', 'Aprobado'),
        ('denied', 'Rechazado'),
    ], string='Estado segunda aprobación', default='pending', readonly=True)
    approver_three_state = fields.Selection([
        ('pending', 'Pendiente'),
        ('approved', 'Aprobado'),
        ('denied', 'Rechazado'),
    ], string='Estado tercera aprobación', default='pending', readonly=True)
    approver_four_state = fields.Selection([
        ('pending', 'Pendiente'),
        ('approved', 'Aprobado'),
        ('denied', 'Rechazado'),
    ], string='Estado cuarta aprobación', default='pending', readonly=True)
    state_approval = fields.Selection([
        ('pending', 'Pendiente'),
        ('approved', 'Aprobado'),
        ('denied', 'Rechazado'),
        ('paid', 'Pagado'),
        ('canceled', 'Cancelado'),
    ], string='Estado de aprobación', default='pending', compute="compute_state_approval")
    
    invoice_id = fields.Many2one('account.move', string='Factura de proveedor',)
    purchase_order_id = fields.Many2one('purchase.order', string='Órden de compra',)
    expense_sheet_id = fields.Many2one('hr.expense.sheet', string='Reporte de gasto',
        domain="[('state','=','post'),('payment_state','in',['not_paid','partial'])]"
    )
    tax = fields.Char('Impuesto')
    partner_id = fields.Many2one('res.partner', string='Proveedor')
    employee_id = fields.Many2one('hr.employee', string='Empleado', compute="_compute_employee_id")
    pay_to = fields.Char('Pagar a', compute='_compute_pay_to', required=False, store=False)
    currency_id = fields.Many2one('res.currency', string='Divisa', compute="_compute_currency_id", readonly=False, required=True, store=True)
    currency = fields.Char(related='currency_id.name', string='Moneda')
    amount_total = fields.Monetary('Importe adeudado', compute="_compute_amount_total", readonly=False, store=True)
    amount = fields.Monetary('Importe a pagar', required=True)
    amount_residual = fields.Monetary('Importe residual', compute="_compute_amount_residual")    
    record_reference = fields.Char(string='Registro', compute='_compute_record_reference')
    payment_id = fields.Many2one('account.payment', string='Pago relacionado')
    sequence = fields.Integer(default=1)
    account_payment_report_id = fields.Many2one('account.payment.report', string='Informe de pago masivo')
    state_report = fields.Selection(related='account_payment_report_id.state')
    level_approval = fields.Selection(related='account_payment_report_id.level_approval')

    first_approval_in_this_company = fields.Boolean(related='account_payment_report_id.first_approval_in_this_company')
    second_approval_in_this_company = fields.Boolean(related='account_payment_report_id.second_approval_in_this_company')
    third_approval_in_this_company = fields.Boolean(related='account_payment_report_id.third_approval_in_this_company')
    fourth_approval_in_this_company = fields.Boolean(related='account_payment_report_id.fourth_approval_in_this_company')
    comment = fields.Char('Nota', readonly=True)

    # Limpiar el registro seleccionado (invoice_id, purchase_order_id, expense_sheet_id)
    # Esto para limpiar los campos relacionados a este, como el proveedor/empleado e importe adeudado
    @api.onchange('type')
    def _onchange_type(self):
        if self.type == 'invoice':
            self.purchase_order_id = False
            self.expense_sheet_id = False
        elif self.type == 'purhcase':
            self.expense_sheet_id = False
            self.invoice_id = False
        elif self.type == 'expense':
            self.invoice_id = False
            self.purchase_order_id = False
        else:
            self.purchase_order_id = False
            self.invoice_id = False
            self.expense_sheet_id = False

    # Obtener el partner_id cuando sea Factura u Orden
    @api.depends('expense_sheet_id')
    def _compute_employee_id(self):
        for rec in self:
            if rec.type == 'expense':
                rec.employee_id = rec.expense_sheet_id.employee_id
            else:
                rec.employee_id = False

    # Compute estado de aprobación general
    @api.depends('approver_one_state', 'approver_two_state', 'approver_three_state', 'approver_four_state', 'level_approval')
    def compute_state_approval(self):
        for rec in self:
            if rec.state_report == 'approved':
                rec.state_approval = 'approved'
            elif rec.state_report == 'accounted':
                rec.state_approval = 'paid'
            elif rec.state_report == 'canceled':
                rec.state_approval = 'canceled'
            # Si se regresa a borrador, tomar el estado del primer aprobador para saber si es rechazado o aprobado
            elif rec.state_report == 'draft':
                rec.state_approval = rec.approver_one_state 
            elif rec.level_approval == '1':
                rec.state_approval = rec.approver_one_state
            elif rec.level_approval == '2':
                rec.state_approval = rec.approver_two_state
            elif rec.level_approval == '3':
                rec.state_approval = rec.approver_three_state
            elif rec.level_approval == '4':
                rec.state_approval = rec.approver_four_state
            else:
                rec.state_approval = 'pending'
        

    # Obtener el nombre de a quién se le hará el pago
    @api.depends('type', 'partner_id', 'employee_id')
    def _compute_pay_to(self):
        for rec in self:
            if rec.partner_id:
                rec.pay_to = rec.partner_id.name
            elif rec.employee_id:
                rec.pay_to = rec.employee_id.name
            else:
                rec.pay_to = ''

    # Obtener el currency_id
    @api.depends('invoice_id', 'purchase_order_id', 'expense_sheet_id')
    def _compute_currency_id(self):
        for rec in self:
            if rec.invoice_id:
                rec.currency_id = rec.invoice_id.currency_id
            elif rec.purchase_order_id:
                rec.currency_id = rec.purchase_order_id.currency_id
            elif rec.expense_sheet_id:
                rec.currency_id = rec.expense_sheet_id.currency_id
            else:
                rec.currency_id = False

    # Obtener el total del adeudo
    @api.depends('invoice_id', 'purchase_order_id', 'expense_sheet_id')
    def _compute_amount_total(self):
        for rec in self:
            if rec.invoice_id:
                rec.amount_total = rec.invoice_id.amount_residual_signed
            elif rec.purchase_order_id:
                rec.amount_total = rec.purchase_order_id.amount_total
            elif rec.expense_sheet_id:
                rec.amount_total = rec.expense_sheet_id.total_amount
            else:
                rec.amount_total = 0
    
    @api.onchange('amount_total')
    def _onchange_amount_total(self):
        self.amount = abs(self.amount_total)
            
    # Calcular el total restante a pagar
    @api.depends('amount_total', 'amount')
    def _compute_amount_residual(self):
        for rec in self:
            rec.amount_residual = abs(rec.amount_total) - rec.amount

    # Crear el link al registro en cuestión
    @api.depends('type', 'invoice_id', 'purchase_order_id', 'expense_sheet_id', 'tax')
    def _compute_record_reference(self):
        for rec in self:
            if rec.type == 'invoice':
                rec.record_reference = rec.invoice_id.name
            elif rec.type == 'purchase':
                rec.record_reference = rec.purchase_order_id.name
            elif rec.type == 'expense':
                rec.record_reference = rec.expense_sheet_id.name
            else:
                rec.record_reference = rec.tax

    # Retorna el dominio para Facturas y Compras
    # Filtra para no mostrar registros ya seleccionados en el One2Many
    @api.onchange('partner_id')
    def _onchange_purchase_order_id(self):
        for rec in self:
            po_ids = []
            invoice_ids = []
            for txt in rec.account_payment_report_id.transaction_line_ids:
                if txt.purchase_order_id.id:
                    po_ids.append(txt.purchase_order_id.id)
                if txt.invoice_id.id:
                    invoice_ids.append(txt.invoice_id.id)
            return {
                'domain': {
                    'purchase_order_id': [
                        ('id', 'not in', po_ids),
                        ('partner_id','=',rec.partner_id.id),
                        ('state','=','purchase'),
                        ('invoice_count','=',0)
                    ],
                    'invoice_id': [
                        ('id', 'not in', invoice_ids),
                        ('partner_id','=',rec.partner_id.id),
                        ('move_type','in',['in_invoice','in_receipt']),
                        ('payment_state','in',['not_paid','partial']),
                        ('state','=','posted')
                    ]
                }
            }
    
    # Función para aprobar línea de transacción
    def action_approve_transaction_line(self):
        group_approver = self.env.context.get("group_approver")
        if group_approver == 1:
            self.write({'approver_one_state': 'approved', 'state_approval': 'approved'})
        elif group_approver == 2:
            self.write({'approver_two_state': 'approved', 'state_approval': 'approved'})
        elif group_approver == 3:
            self.write({'approver_three_state': 'approved', 'state_approval': 'approved'})
        elif group_approver == 4:
            self.write({'approver_four_state': 'approved', 'state_approval': 'approved'})
    
    # Método para rechazar línea de transacción. 
    # Abre un wizard para solicitar una nota obligatoria del motivo del rechazo
    def action_deny_transaction_line(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Rechazar transacción',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'transaction.comment.wizard',
            'target': 'new',
            'context': {
                'group_approver': self.env.context.get("group_approver")
            }
        }

    # Action para abrir PopUp del registro en cuestión
    def action_open_record(self):
        self.ensure_one()
        res_model = 'account.move'
        res_id = self.invoice_id.id
        if self.type == 'invoice':
            res_model = 'account.move'
            res_id = self.invoice_id.id
            name = f'Factura de proveedor - {self.record_reference}'
        elif self.type == 'purchase':
            res_model = 'purchase.order'
            res_id = self.purchase_order_id.id
            name = f'Orden de compra - {self.record_reference}'
        elif self.type == 'expense':
            res_model = 'hr.expense.sheet'
            res_id = self.expense_sheet_id.id
            name = f'Reporte de gasto - {self.record_reference}'
        else:
            return
        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': res_model,
            'res_id': res_id,
            'target': 'new'
        }
        
    # Action para abrir PopUp del pago relacionado
    def action_open_payment(self):
        return {
            'name': 'Pago',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'account.payment',
            'res_id': self.payment_id.id,
            'target': 'new'
        }
    