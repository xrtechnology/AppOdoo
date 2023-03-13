from odoo import models, fields, exceptions, api, _
import logging
from odoo.tools.float_utils import float_compare, float_is_zero, float_round

_logger = logging.getLogger(__name__)


class MaintenanceEquipment(models.Model):
    _inherit = 'maintenance.equipment'


    product_id = fields.Many2one('product.product', "Linked Product")
    stock_location_id = fields.Many2one('stock.location', "Stock Location")
    move_count = fields.Integer(compute='_compute_move_count')

    def _compute_move_count(self):
        moves = self.env['stock.move'].search([('product_id','=',self.product_id.id)])
        for rec in self:
            rec.move_count = len(moves.ids)
            return rec.move_count

    def action_move_history(self):
        moves = self.env['stock.move'].search([('product_id','=',self.product_id.id)])
        action = self.env.ref('stock.stock_move_action').read()[0]
        if moves:
            action['domain'] = [('id', 'in', moves.ids)]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action
