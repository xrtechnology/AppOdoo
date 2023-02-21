from odoo import _, api, fields, models
from datetime import datetime, date
from odoo.exceptions import ValidationError
import pytz
import logging

_logger = logging.getLogger(__name__)


class AccountPaymentReport(models.Model):
    _name = 'account.payment.report'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Informe de pagos masivos'
    _order = 'create_date desc'
    
    name = fields.Char('Nombre', required=True,  readonly=True, index='trigram', copy=False, default='Borrador')
    approval_requested_by = fields.Many2one('res.users', string='Solicitó aprobación', readonly=True)
    request_date = fields.Datetime('Fecha de solicitud', readonly=True)
    # Usuarios aprobadores
    approved_first_by = fields.Many2one('res.users', string='Primer aprobador', readonly=True)
    approved_second_by = fields.Many2one('res.users', string='Segundo aprobador', readonly=True)
    approved_third_by = fields.Many2one('res.users', string='Tercer aprobador', readonly=True)
    approved_fourth_by = fields.Many2one('res.users', string='Cuarto aprobador', readonly=True)
    # Fechas de aprobación
    approved_date_first = fields.Datetime('Fecha aprobación 1', readonly=True)
    approved_date_second = fields.Datetime('Fecha aprobación 2', readonly=True)
    approved_date_third = fields.Datetime('Fecha aprobación 3', readonly=True)
    approved_date_fourth = fields.Datetime('Fecha aprobación 4', readonly=True)
    # Firmas de usuarios aprobadores
    approver_one_sign = fields.Binary(related='approved_first_by.sign_signature', string="Firma aprobador 1")
    approver_two_sign = fields.Binary(related='approved_second_by.sign_signature', string="Firma aprobador 2")
    approver_three_sign = fields.Binary(related='approved_third_by.sign_signature', string="Firma aprobador 3")
    approver_four_sign = fields.Binary(related='approved_fourth_by.sign_signature', string="Firma aprobador 4")
    # Datos del pago
    paid_by = fields.Many2one('res.users', string='Pago realizado por', readonly=True)
    payment_date = fields.Datetime('Fecha de pago', readonly=True)
    paying_user_sign = fields.Binary(related='paid_by.sign_signature', string="Firma de generador de pagos")

    journal_id = fields.Many2one('account.journal', string='Diario de pago', required=True, domain="[('type','=','bank')]", check_company=True)
    company_id = fields.Many2one(comodel_name='res.company',string='Empresa', compute='_compute_company_id', store=True, precompute=True, index=True)
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('pending', 'En espera de aprobación'),
        ('approved', 'Aprobado'),
        ('accounted', 'Pago contabilizado'),
        ('canceled', 'Cancelado'),
    ], string='Estado', default='draft', readonly=False, required=True, tracking=True)
    user_id = fields.Many2one('res.users', string='Creado por', index=True, tracking=True,
        default=lambda self: self.env.user, check_company=False, readonly=True)
    date_report = fields.Date('Fecha de creación', compute="_compute_date_report")
    transaction_line_ids = fields.One2many('account.payment.transaction.line', 'account_payment_report_id', string='Transacciones', 
        required=True, ondelete='cascade')
    payment_method_line_id = fields.Many2one('account.payment.method.line', string='Método de pago', required=True,
        domain="[('id', 'in', available_payment_method_line_ids)]")
    available_payment_method_line_ids = fields.Many2many('account.payment.method.line',
        compute='_compute_payment_method_line_fields')
    l10n_mx_edi_payment_method_id = fields.Many2one(comodel_name='l10n_mx_edi.payment.method', string="Forma de pago",
        help="Indica la forma em que se pagó / se pagará la factura, donde las opciones podrían ser: "
        "Efectivo, Choque nominal, Tarjeta de crédito, etc. Deje en blanco si no lo conoce y el XML mostrará 'No identificado'.")
    note = fields.Char('Comentarios')
    # Campos booleanos que indican si un usuario puede aprobar en relación al grupo y a las empresas permitidas 
    first_approval_in_this_company = fields.Boolean('Permitir primera aprobación en esta empresa', compute="_compute_approval_in_this_company")
    second_approval_in_this_company = fields.Boolean('Permitir segunda aprobación en esta empresa', compute="_compute_approval_in_this_company")
    third_approval_in_this_company = fields.Boolean('Permitir tercera aprobación en esta empresa', compute="_compute_approval_in_this_company")
    fourth_approval_in_this_company = fields.Boolean('Permitir cuarta aprobación en esta empresa', compute="_compute_approval_in_this_company")
    # Campos boolanos que indican si todas las líneas de transacción han sido validadas por los groupos de aprobación 1, 2, 3 y 4.
    lines_approved_group_approver_1 = fields.Boolean('Transacciones aprobadas (grupo aprobador 1)', compute='_compute_lines_approved', default=False)
    lines_approved_group_approver_2 = fields.Boolean('Transacciones aprobadas (grupo aprobador 2)', compute='_compute_lines_approved', default=False)
    lines_approved_group_approver_3 = fields.Boolean('Transacciones aprobadas (grupo aprobador 3)', compute='_compute_lines_approved', default=False)
    lines_approved_group_approver_4 = fields.Boolean('Transacciones aprobadas (grupo aprobador 4)', compute='_compute_lines_approved', default=False)
    # Campos booleanos que indican si hay líneas de transacción pendientes por cada grupo. Esto indica que faltan transacciones por aprobar o rechazar
    lines_pending_group_1 = fields.Boolean('Transacciones pendientes (grupo aprobador 1)', compute="_compute_lines_pending")
    lines_pending_group_2 = fields.Boolean('Transacciones pendientes (grupo aprobador 2)', compute="_compute_lines_pending")
    lines_pending_group_3 = fields.Boolean('Transacciones pendientes (grupo aprobador 3)', compute="_compute_lines_pending")
    lines_pending_group_4 = fields.Boolean('Transacciones pendientes (grupo aprobador 4)', compute="_compute_lines_pending")
    # Estado de nivel de aprobación
    level_approval = fields.Selection([
        ('0', 'No aprobado'),
        ('1', 'Primera aprobación'),
        ('2', 'Segunda aprobación'),
        ('3', 'Tercera aprobación'),
        ('4', 'Cuarta aprobación'),
        ('5', 'Aprobdo por todos'),
        ('6', 'Cancelado'),
    ], default='0', string='Nivel de aprobación', required=True, readonly=True)

    # Computar Empresa
    @api.depends('journal_id')
    def _compute_company_id(self):
        for rec in self:
            company_id = rec.journal_id.company_id or self.env.company
            if company_id != rec.company_id:
                rec.company_id = company_id

    # Tomar solo la fecha del campo crate_date para no mostrar la hora de creación
    @api.depends('create_date')
    def _compute_date_report(self):
        for rec in self:
            rec.date_report = rec.create_date.date()
            
    # Establecer como Borrador
    def set_as_draft(self):
        return self.get_action_note_wizard(note_required=False, state_value='draft', 
        state_string='Establecido como borrador', title_wizard='Esteblecer como borrador', group=False)
    
    # Establecer como En espera de aprobación
    def set_as_pending(self):
        # Se envía el xmlid del grupo 'Aprovador 1' para crear actividades a usuarios de ese grupo
        return self.get_action_note_wizard(note_required=False, state_value='pending', state_string='En espera de aprobación', 
        title_wizard='Solicitar aprobación', group='toh_mass_payment_report.group_mass_payment_approver_1')
        
    # Establecer como Aprobado
    def set_as_approved(self):
        # Se envía el xmlid del grupo 'Generador de pagos' para crear actividades a usuarios de ese grupo
        return self.get_action_note_wizard(note_required=False, state_value='approved', 
        state_string='Aprobado', title_wizard='Aprobar', group='toh_mass_payment_report.group_mass_payment_generator')

    # Establecer como Cancelado
    def set_as_canceled(self):
        return self.get_action_note_wizard(note_required=True, state_value='canceled', 
        state_string='Cancelado', title_wizard='Cancelar', group=False)

    # Método para botón de primera aprobación.
    def action_first_approval(self):
        # Marcar como aprobado una vez
        self.write({
            'level_approval': '2',
            'approved_first_by': self.env.user,
            'approved_date_first': datetime.now()
            })
        # Marcar actividad de primera aprobación como hecho
        activity_id = self.env['mail.activity'].search([
            ('res_id', '=', self.id), 
            ('user_id' ,'=', self.env.user.id), 
            ('activity_type_id' ,'=', self.env.ref('toh_mass_payment_report.mail_act_mass_payment_approval').id)])
        activity_id.action_feedback()
        # Eliminar las otras (en caso de haber)
        other_activity_ids = self.env['mail.activity'].search([
            ('res_id', '=' ,self.id),
            ('activity_type_id' ,'=', self.env.ref('toh_mass_payment_report.mail_act_mass_payment_approval').id)])
        other_activity_ids.unlink()
        # Generar actividad al grupo de usuarios 'Aprobador 2'
        users = self.env.ref('toh_mass_payment_report.group_mass_payment_approver_2').users
        for user in users:
            self.activity_schedule('toh_mass_payment_report.mail_act_mass_payment_approval_2', user_id = user.id)

    # Método para segunda aprobación
    def action_second_approval(self):
        self.write({
            'level_approval': '3',
            'approved_second_by': self.env.user,
            'approved_date_second': datetime.now()
        })
        # Marcar actividad de segunda aprobación como hecha
        activity_id = self.env['mail.activity'].search([
            ('res_id', '=', self.id), 
            ('user_id' ,'=', self.env.user.id), 
            ('activity_type_id' ,'=', self.env.ref('toh_mass_payment_report.mail_act_mass_payment_approval_2').id)])
        activity_id.action_feedback()
        # Eliminar las otras (en caso de haber)
        other_activity_ids = self.env['mail.activity'].search([
            ('res_id', '=' ,self.id),
            ('activity_type_id' ,'=', self.env.ref('toh_mass_payment_report.mail_act_mass_payment_approval_2').id)])
        other_activity_ids.unlink()
        # Crear actividades de tercera aprobación al grupo Aprobador 3
        users = self.env.ref('toh_mass_payment_report.group_mass_payment_approver_3').users
        for user in users:
            self.activity_schedule('toh_mass_payment_report.mail_act_mass_payment_approval_3', user_id = user.id)

    # Método para tercera aprobación
    def action_third_approval(self):
        self.write({
            'level_approval': '4',
            'approved_third_by': self.env.user,
            'approved_date_third': datetime.now()
        })
        # Marcar actividad de tercera aprobación de usuario como hecha
        activity_id = self.env['mail.activity'].search([
            ('res_id', '=', self.id), 
            ('user_id' ,'=', self.env.user.id), 
            ('activity_type_id' ,'=', self.env.ref('toh_mass_payment_report.mail_act_mass_payment_approval_3').id)])
        activity_id.action_feedback()
        # Eliminar las otras (en caso de haber)
        other_activity_ids = self.env['mail.activity'].search([
            ('res_id', '=' ,self.id),
            ('activity_type_id' ,'=', self.env.ref('toh_mass_payment_report.mail_act_mass_payment_approval_3').id)])
        other_activity_ids.unlink()
        # Crear actividades de cuarta aprobación al grupo 'Aprobador 4'
        users = self.env.ref('toh_mass_payment_report.group_mass_payment_approver_4').users
        for user in users:
            self.activity_schedule('toh_mass_payment_report.mail_act_mass_payment_approval_4', user_id = user.id)

    # Método copiado de account.payment para el funcionamiento del Domain 
    # en el campo 'available_payment_method_line_ids'
    @api.depends('journal_id')
    def _compute_payment_method_line_fields(self):
        for pay in self:
            pay.available_payment_method_line_ids = pay.journal_id._get_available_payment_method_lines('outbound')
            to_exclude = pay._get_payment_method_codes_to_exclude()
            if to_exclude:
                pay.available_payment_method_line_ids = pay.available_payment_method_line_ids.filtered(lambda x: x.code not in to_exclude)

    # Método copiado de account.payment para funcionamiento de _compute_payment_method_line_fields
    def _get_payment_method_codes_to_exclude(self):
        # can be overriden to exclude payment methods based on the payment characteristics
        self.ensure_one()
        return []

    # Computar si el usuario actual puede aprobar según la empresa y el grupo de aprobación
    def _compute_approval_in_this_company(self):
        for rec in self:
            user = self.env.user
            company = self.env.company
            first_approval_group = self.env.user.has_group('toh_mass_payment_report.group_mass_payment_approver_1') == True
            second_approval_group = self.env.user.has_group('toh_mass_payment_report.group_mass_payment_approver_2') == True
            third_approval_group = self.env.user.has_group('toh_mass_payment_report.group_mass_payment_approver_3') == True
            fourth_approval_group = self.env.user.has_group('toh_mass_payment_report.group_mass_payment_approver_4') == True
            # ------------------------------
            # Comprobación primero aprobador:
            # ------------------------------
            # Si no tiene permisos, será False
            if not first_approval_group:
                rec.first_approval_in_this_company = False
            # Si el campo de empresas está vacío, permitir; True
            elif not user.approver_one_company_ids:
                rec.first_approval_in_this_company = True
            # Si tiene valores; comprobar si la empresa actual está seleccionado:
            elif user.approver_one_company_ids:
                # Si está: permitir: True, sino; negar; False
                rec.first_approval_in_this_company = True if company.id in user.approver_one_company_ids.ids else False
            # ------------------------------
            # Comprobación segundo aprobador:
            # ------------------------------
            # Si no tiene permisos, será False
            if not second_approval_group:
                rec.second_approval_in_this_company = False
            # Si el campo de empresas está vacío, permitir; True
            elif not user.approver_two_company_ids:
                rec.second_approval_in_this_company = True
            # Si tiene valores; comprobar si la empresa actual está seleccionado:
            elif user.approver_two_company_ids:
                # Si está: permitir: True, sino; negar; False
                rec.second_approval_in_this_company = True if company.id in user.approver_two_company_ids.ids else False
            # ------------------------------
            # Comprobación tercer aprobador:
            # ------------------------------
            # Si no tiene permisos, será False
            if not third_approval_group:
                rec.third_approval_in_this_company = False
            # Si el campo de empresas está vacío, permitir; True
            elif not user.approver_three_company_ids:
                rec.third_approval_in_this_company = True
            # Si tiene valores; comprobar si la empresa actual está seleccionado:
            elif user.approver_three_company_ids:
                # Si está: permitir: True, sino; negar; False
                rec.third_approval_in_this_company = True if company.id in user.approver_three_company_ids.ids else False
            # ------------------------------
            # Comprobación cuarto aprobador:
            # ------------------------------
            # Si no tiene permisos, será False
            if not fourth_approval_group:
                rec.fourth_approval_in_this_company = False
            # Si el campo de empresas está vacío, permitir; True
            elif not user.approver_four_company_ids:
                rec.fourth_approval_in_this_company = True
            # Si tiene valores; comprobar si la empresa actual está seleccionado:
            elif user.approver_four_company_ids:
                # Si está: permitir: True, sino; negar; False
                rec.fourth_approval_in_this_company = True if company.id in user.approver_four_company_ids.ids else False

    # Este método asigna True si todas las líneas de transacción han sido aprobadas, de lo contrario; asigna False
    @api.depends('transaction_line_ids')
    def _compute_lines_approved(self):
        for rec in self:
            approver_status = self.get_approver_status_array()

            rec.lines_approved_group_approver_1 = False if any(item in ['pending', 'denied'] for item in approver_status[0]) else True
            rec.lines_approved_group_approver_2 = False if any(item in ['pending', 'denied'] for item in approver_status[1]) else True
            rec.lines_approved_group_approver_3 = False if any(item in ['pending', 'denied'] for item in approver_status[2]) else True
            rec.lines_approved_group_approver_4 = False if any(item in ['pending', 'denied'] for item in approver_status[3]) else True

    # Este método asigna True si hay transacciones pendientes (aún sin aprobar o rechazar), de lo contrario; asigna False
    def _compute_lines_pending(self):
        for rec in self:
            approver_status = self.get_approver_status_array()

            rec.lines_pending_group_1 = True if any(item in ['pending'] for item in approver_status[0]) else False
            rec.lines_pending_group_2 = True if any(item in ['pending'] for item in approver_status[1]) else False
            rec.lines_pending_group_3 = True if any(item in ['pending'] for item in approver_status[2]) else False
            rec.lines_pending_group_4 = True if any(item in ['pending'] for item in approver_status[3]) else False
    
    # Método que devuelve un array de arrays de estatus de linea de transacción por cada grupo
    def get_approver_status_array(self):
        state_app1_list = list(map(lambda tx: tx.approver_one_state, self.transaction_line_ids))
        state_app2_list = list(map(lambda tx: tx.approver_two_state, self.transaction_line_ids))
        state_app3_list = list(map(lambda tx: tx.approver_three_state, self.transaction_line_ids))
        state_app4_list = list(map(lambda tx: tx.approver_four_state, self.transaction_line_ids))

        return [state_app1_list, state_app2_list, state_app3_list, state_app4_list]

    # Sobreescritura del método create()
    @api.model
    def create(self, vals):
        # Genera folio consecutivo para el campo 'name' al crear un registro
        if vals.get('name', _('Borrador')) == _('Borrador'):
            vals['name'] = self.env['ir.sequence'].next_by_code('account.payment.report') or _('Borrador')

        # Validar que se seleccione por lo menos una transacción
        if not vals.get('transaction_line_ids'):
            raise ValidationError('Debe seleccionar por lo menos una transacción a pagar.')

        result = super(AccountPaymentReport, self).create(vals)
        return result

    def write(self, vals):
        # Asignar fecha a 'request_date' al cambiar estado a 'pending'
        if 'state' in vals:
            # Al cambiar a en espera de aprobación
            if vals.get('state') == 'pending':
                self.write({
                    'request_date': datetime.now(),
                    'approval_requested_by': self.env.user
                })
            # Al aprobar
            elif vals.get('state') == 'approved':
                self.write({
                    'approved_date_fourth': datetime.now(),
                    'approved_fourth_by': self.env.user,
                    'level_approval': '5'
                })
                # Al aprobar, marcar estado de cada línea de transacción como Aprobado
                for tx in self.transaction_line_ids:
                    tx.state_approval = 'approved'
            # Al cancelar:
            elif vals.get('state') == 'draft':
                # Reestablecer valores de creador de reportes, aprobadores y creador de pagos.
                self.write({
                    'approval_requested_by': False,
                    'approved_first_by': False,
                    'approved_second_by': False,
                    'approved_third_by': False,
                    'approved_fourth_by': False,
                    'approved_date_first': False,
                    'approved_date_second': False,
                    'approved_date_third': False,
                    'approved_date_fourth': False,
                    'level_approval': '0',
                    'paid_by': False,
                    'payment_date': False,
                })
            elif vals.get('state') == 'accounted':
                self.write({
                    'paid_by': self.env.user,
                    'payment_date': datetime.now()
                })
                # Al pagar, marcar estado de cada línea de transacción como Pagado
                for tx in self.transaction_line_ids:
                    tx.state_approval = 'paid'
        return super().write(vals)
    
    # Método para obtener action para abrir el wizard
    def get_action_note_wizard(self, note_required, state_value, state_string, title_wizard, group):
        return {
            'type': 'ir.actions.act_window',
            'name': title_wizard,
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'note.history.wizard',
            'target': 'new',
            'context': {
                'note_required': note_required,
                'state_value': state_value,
                'state_string': state_string,
                'group': group,
                } 
        }

    # Crear pagos
    def create_payments(self):
        for line in self.transaction_line_ids:
            if line.type == 'expense':
                continue

            payment_vals = {
                'date': date.today(),
                'amount': line.amount,
                'payment_type': 'outbound',
                'partner_type': 'supplier',
                'ref': line.record_reference,
                'journal_id': self.journal_id.id,
                'currency_id': line.currency_id.id,
                'partner_id': line.partner_id.id,
                'payment_method_line_id': self.payment_method_line_id.id,
                'l10n_mx_edi_payment_method_id': self.l10n_mx_edi_payment_method_id.id,
            }
            new_payment = line.payment_id.create(payment_vals)
            line.payment_id = new_payment.id
            line.payment_id.state = 'posted'

            if line.type == 'invoice':
                move_lines = new_payment.line_ids.filtered(lambda record: record.account_type == 'liability_payable' and not record.reconciled)
                for move in move_lines:
                    line.invoice_id.js_assign_outstanding_line(move.id)
            
        date_note = datetime.now().astimezone(pytz.timezone(self.env.context.get('tz')))
        message = f'''Informe de pagos masivos <strong>Contabilizado</strong><br>
            <strong>Fecha:</strong> {date_note.strftime("%d/%m/%Y")}<br>
            <strong>Hora:</strong> {date_note.strftime("%H:%M:%S")}<br>
            '''
        self.message_post(body=_(message), message_type='sms')
        self.write({'state': 'accounted'})

        # Marcar como hecha la actividad de 'Generar pagos' y elimianr las otras
        activity_id = self.env['mail.activity'].search([
            ('res_id', '=', self.id), 
            ('user_id' ,'=', self.env.user.id), 
            ('activity_type_id' ,'=', self.env.ref('toh_mass_payment_report.mail_act_mass_payment_generator').id)])
        activity_id.action_feedback()

        # Eliminar las otras (en caso de haber)
        other_activity_ids = self.env['mail.activity'].search([
            ('res_id', '=' ,self.id),
            ('activity_type_id' ,'=', self.env.ref('toh_mass_payment_report.mail_act_mass_payment_generator').id)])
        other_activity_ids.unlink()
        
    # Método que obtiene total por divisa
    def get_totals(self):
        for rec in self:
            # Obtener divisas
            currencies = list(set(map(lambda line: line.currency_id, rec.transaction_line_ids)))
            
            # Sumatoria de totales por divisa
            totals = []
            for curr in currencies:
                filtered_by_currency = list(filter(lambda line: line.currency_id == curr, rec.transaction_line_ids ))

                # Importe adeudado
                amount_total_list = list(map(lambda line: abs(line.amount_total), filtered_by_currency))
                sum_amount_total = sum(list(amount_total_list))
                # Importe a pagar
                amount_list = list(map(lambda line: abs(line.amount), filtered_by_currency))
                sum_amount = sum(list(amount_list))
                # Importe residual
                amount_residual_list = list(map(lambda line: abs(line.amount_residual), filtered_by_currency))
                sum_amount_residual = sum(list(amount_residual_list))
                
                totals.append({
                    'currency_id': curr, 
                    'amount_total': sum_amount_total,
                    'total': sum_amount,
                    'total_residual': sum_amount_residual,
                })
            
            return totals
            

