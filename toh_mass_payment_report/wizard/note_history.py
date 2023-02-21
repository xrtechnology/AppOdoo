from odoo import _, fields, models
from datetime import datetime
import logging
import pytz

_logger = logging.getLogger(__name__)


class NoteHistoryWizard(models.TransientModel):
    _name = 'note.history.wizard'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Historial de notas'
    
    note = fields.Char('Nota')
    note_required = fields.Boolean('Requerido', default=lambda self: self._context.get("note_required"))

    def post_note(self):
        payment_report = self.env['account.payment.report'].browse(self.env.context.get("active_id"))
        state_string = self.env.context.get('state_string')
        date_note = datetime.now().astimezone(pytz.timezone(self.env.context.get('tz')))

        # ---------------------------------------------------------------
        # Formar estructura html para el mensaje a publicar en el chatter
        # ---------------------------------------------------------------
        comment = f'<strong>Nota:</strong>\n{self.note}' if self.note else ''
        message = f'''Informe de pagos masivos <strong>{state_string}</strong><br>
            <strong>Fecha:</strong> {date_note.strftime("%d/%m/%Y")}<br>
            <strong>Hora:</strong> {date_note.strftime("%H:%M:%S")}<br>
            {comment}
            '''
        # ---------------------------------------------------------------------------
        # Publicar un mensaje en el chatter y cambiar reporte a etapa correspondiente
        # ---------------------------------------------------------------------------
        payment_report.message_post(body=_(message), message_type='sms')

        # Crear actividad a grupos de usuarios si se cambia a pending
        if self.env.context.get("state_value") == 'pending':
            # Borrar actividades de revisión (si las hay)
            other_activity_ids = self.env['mail.activity'].search([('res_id', '=', payment_report.id),
                ('activity_type_id' ,'in', [self.env.ref('toh_mass_payment_report.mail_act_mass_payment_feedback').id])
            ])
            other_activity_ids.unlink()
            # Generar actividades al grupo de aprobación 1
            users = self.env.ref( self.env.context.get('group') ).users
            for user in users:
                payment_report.activity_schedule('toh_mass_payment_report.mail_act_mass_payment_approval', user_id = user.id),

            # Restablecer estado de línea de transacción:
            for tx in payment_report.transaction_line_ids:
                if tx.approver_one_state == 'denied':
                    tx.approver_one_state = 'pending'
                if tx.approver_two_state == 'denied':
                    tx.approver_two_state = 'pending'
                if tx.approver_three_state == 'denied':
                    tx.approver_three_state = 'pending'
                if tx.approver_four_state == 'denied':
                    tx.approver_four_state = 'pending'
                tx.comment = ''
            # Establecer reporte como nivel de primera aprobación
            payment_report.level_approval = '1'
            
        # Si se aprueba, marcar actividad de Cuarta aprobación como Hecha
        elif self.env.context.get("state_value") == 'approved':
            activity_id = self.env['mail.activity'].search([
                ('res_id', '=', payment_report.id), 
                ('user_id' ,'=', self.env.user.id), 
                ('activity_type_id' ,'=', self.env.ref('toh_mass_payment_report.mail_act_mass_payment_approval_4').id)])
            activity_id.action_feedback()

            # Eliminar las otras (en caso de haber)
            other_activity_ids = self.env['mail.activity'].search([
                ('res_id', '=', payment_report.id),
                ('activity_type_id' ,'=', self.env.ref('toh_mass_payment_report.mail_act_mass_payment_approval_4').id)])
            other_activity_ids.unlink()

            # Generar actividad al grupo de usuarios 'Generador de pagos'
            users = self.env.ref('toh_mass_payment_report.group_mass_payment_generator').users
            for user in users:
                payment_report.activity_schedule('toh_mass_payment_report.mail_act_mass_payment_generator', user_id = user.id)

        # Si se cancela o restablece a borrador; eliminar actividades (aprobación 1, 2, 3, 4, de revisón y generador de pagos) si las hay
        elif self.env.context.get("state_value") == 'canceled':
            other_activity_ids = self.env['mail.activity'].search([
                ('res_id', '=', payment_report.id),
                ('activity_type_id' ,'in', [
                    self.env.ref('toh_mass_payment_report.mail_act_mass_payment_approval').id,
                    self.env.ref('toh_mass_payment_report.mail_act_mass_payment_approval_2').id,
                    self.env.ref('toh_mass_payment_report.mail_act_mass_payment_approval_3').id,
                    self.env.ref('toh_mass_payment_report.mail_act_mass_payment_approval_4').id,
                    self.env.ref('toh_mass_payment_report.mail_act_mass_payment_feedback').id,
                    self.env.ref('toh_mass_payment_report.mail_act_mass_payment_generator').id
                ])
            ])
            other_activity_ids.unlink()
            # Marcar nivel de aprobación como cancelado
            payment_report.level_approval = '6'
            # Restablecer estado de línea de transacción como pendiente:
            for tx in payment_report.transaction_line_ids:
                tx.approver_one_state = 'pending'
                tx.approver_two_state = 'pending'
                tx.approver_three_state = 'pending'
                tx.approver_four_state = 'pending'
                tx.comment = ''
                
        elif self.env.context.get("state_value") == 'draft':
            # Borrar todas las actividades de aprobación y de generador de pagos
            other_activity_ids = self.env['mail.activity'].search([
                ('res_id', '=', payment_report.id),
                ('activity_type_id' ,'in', [
                    self.env.ref('toh_mass_payment_report.mail_act_mass_payment_approval').id,
                    self.env.ref('toh_mass_payment_report.mail_act_mass_payment_approval_2').id,
                    self.env.ref('toh_mass_payment_report.mail_act_mass_payment_approval_3').id,
                    self.env.ref('toh_mass_payment_report.mail_act_mass_payment_approval_4').id,
                    self.env.ref('toh_mass_payment_report.mail_act_mass_payment_generator').id
                ])
            ])
            other_activity_ids.unlink()
            # Verificar en qué nivel de aprobación para notificar a grupos de niveles más bajos
            groups_to_notify = []
            if payment_report.level_approval in ['1','6']: # Cuando sea Aprobador 1 o Cancelado
                groups_to_notify.append('toh_mass_payment_report.group_mass_payment_user')
            elif payment_report.level_approval == '2': # Cuando sea Aprrobador 2
                groups_to_notify.append('toh_mass_payment_report.group_mass_payment_user')
                groups_to_notify.append('toh_mass_payment_report.group_mass_payment_approver_1')
            elif payment_report.level_approval == '3': # Cuando sea Aprrobador 3
                groups_to_notify.append('toh_mass_payment_report.group_mass_payment_user')
                groups_to_notify.append('toh_mass_payment_report.group_mass_payment_approver_1')
                groups_to_notify.append('toh_mass_payment_report.group_mass_payment_approver_2')
            elif payment_report.level_approval == '4': # Cuando sea Aprrobador 2
                groups_to_notify.append('toh_mass_payment_report.group_mass_payment_user')
                groups_to_notify.append('toh_mass_payment_report.group_mass_payment_approver_1')
                groups_to_notify.append('toh_mass_payment_report.group_mass_payment_approver_2')
                groups_to_notify.append('toh_mass_payment_report.group_mass_payment_approver_3')

            # Obtener los ids de los usuarios a generar actividad
            user_ids = []
            for group in groups_to_notify:
                users = self.env.ref(group).users
                for user in users:
                    user_ids.append(user)

            # Generar actividad de retroalimentación a usuarios
            for user in list(set(user_ids)):
                payment_report.activity_schedule('toh_mass_payment_report.mail_act_mass_payment_feedback', user_id = user.id)

        # Cambiar de etapa
        payment_report.write({'state': self.env.context.get("state_value")})
