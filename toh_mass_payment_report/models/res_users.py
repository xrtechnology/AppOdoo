from odoo import _, fields, models
import logging


_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = 'res.users'
    
    is_approver_one = fields.Boolean('Es aprobador 1', compute="_compute_is_approver")
    is_approver_two = fields.Boolean('Es aprobador 2', compute="_compute_is_approver")
    is_approver_three = fields.Boolean('Es aprobador 3', compute="_compute_is_approver")
    is_approver_four = fields.Boolean('Es aprobador 4', compute="_compute_is_approver")
    approver_one_company_ids = fields.Many2many(comodel_name='res.company', relation='approver_company_one_rel', column1='user_id', column2='company_id', string='Empresas aprobador 1')
    approver_two_company_ids = fields.Many2many(comodel_name='res.company', relation='approver_company_two_rel', column1='user_id', column2='company_id', string='Empresas aprobador 2')
    approver_three_company_ids = fields.Many2many(comodel_name='res.company', relation='approver_company_three_rel', column1='user_id', column2='company_id', string='Empresas aprobador 3')
    approver_four_company_ids = fields.Many2many(comodel_name='res.company', relation='approver_company_four_rel', column1='user_id', column2='company_id', string='Empresas aprobador 4')

    def _compute_is_approver(self):
        for rec in self:
            is_approver_one_group = rec.has_group('toh_mass_payment_report.group_mass_payment_approver_1') == True
            is_approver_two_group = rec.has_group('toh_mass_payment_report.group_mass_payment_approver_2') == True
            is_approver_three_group = rec.has_group('toh_mass_payment_report.group_mass_payment_approver_3') == True
            is_approver_four_group = rec.has_group('toh_mass_payment_report.group_mass_payment_approver_4') == True

            rec.is_approver_one = True if is_approver_one_group else False
            rec.is_approver_two = True if is_approver_two_group else False
            rec.is_approver_three = True if is_approver_three_group else False
            rec.is_approver_four = True if is_approver_four_group else False
    