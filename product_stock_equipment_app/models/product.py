# -*- coding: utf-8 -*-

from odoo import models, fields, exceptions, api, _
import io
import logging
from odoo.tools.float_utils import float_compare, float_is_zero, float_round
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class Product(models.Model):
    _inherit = 'product.template'

    default_categ_id = fields.Many2one('product.category', string="Default Category")
    maintenance_team_id = fields.Many2one('maintenance.team', string='Maintenance Team')
    is_equipment = fields.Boolean("Is Equipment?")
    technician_id = fields.Many2one('res.users')
    equipment_assign_to = fields.Selection([('department', 'Department'), ('employee', 'Employee'), ('other', 'Other')],string='Used By',required=True,default='employee')
    shiping_count = fields.Integer(compute='_compute_shiping_count')

    def _compute_shiping_count(self):
        moves = self.env['stock.move'].search([('product_id.product_tmpl_id','=',self.id),('picking_id','!=',False)])
        for rec in self:
            rec.shiping_count = len(moves.ids)
            return rec.shiping_count

    def action_open_move(self):
        # maintenance.hr_equipment_action
        moves = self.env['stock.move'].search([('product_id.product_tmpl_id','=',self.id),('picking_id','!=',False)])
        action = self.env.ref('stock.stock_move_action').read()[0]
        if moves:
            action['domain'] = [('id', 'in', moves.ids)]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    @api.onchange('is_equipment')
    def set_serial_number(self):
        if self.is_equipment:
            self.tracking = 'serial'
