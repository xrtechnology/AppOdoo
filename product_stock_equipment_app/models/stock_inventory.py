# -*- coding: utf-8 -*-

from odoo import models, fields, exceptions, api, _
import io
import logging
from odoo.tools.float_utils import float_compare, float_is_zero, float_round
from odoo.exceptions import UserError
from datetime import datetime

_logger = logging.getLogger(__name__)


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    create_equipment = fields.Boolean("Create Equipment?")


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    create_equipment = fields.Boolean()

    def action_apply_inventory(self):  
        if self.env.user.has_group('product_stock_equipment_app.group_equipment_product'):
            serial_number = self.lot_id.name
            equipment = self.env['maintenance.equipment'].create({'name':self.product_id.name ,'serial_no': serial_number, 'product_id':self.product_id.id,'maintenance_team_id':self.product_id.maintenance_team_id.id, 'technician_user_id':self.product_id.technician_id.id,'stock_location_id':self.location_id.id})
            serial = self.env['stock.lot'].search([('name','=',self.lot_id.name)])
            serial.write({'equipment_id':equipment.id})

            products_tracked_without_lot = []
            for quant in self:
                rounding = quant.product_uom_id.rounding
                if fields.Float.is_zero(quant.inventory_diff_quantity, precision_rounding=rounding)\
                        and fields.Float.is_zero(quant.inventory_quantity, precision_rounding=rounding)\
                        and fields.Float.is_zero(quant.quantity, precision_rounding=rounding):
                    continue
                if quant.product_id.tracking in ['lot', 'serial'] and\
                        not quant.lot_id and quant.inventory_quantity != quant.quantity:
                    products_tracked_without_lot.append(quant.product_id.id)
            # for some reason if multi-record, env.context doesn't pass to wizards...
            ctx = dict(self.env.context or {})
            ctx['default_quant_ids'] = self.ids
            quants_outdated = self.filtered(lambda quant: quant.is_outdated)
            if quants_outdated:
                ctx['default_quant_to_fix_ids'] = quants_outdated.ids
                return {
                    'name': _('Conflict in Inventory Adjustment'),
                    'type': 'ir.actions.act_window',
                    'view_mode': 'form',
                    'views': [(False, 'form')],
                    'res_model': 'stock.inventory.conflict',
                    'target': 'new',
                    'context': ctx,
                }
            if products_tracked_without_lot:
                ctx['default_product_ids'] = products_tracked_without_lot
                return {
                    'name': _('Tracked Products in Inventory Adjustment'),
                    'type': 'ir.actions.act_window',
                    'view_mode': 'form',
                    'views': [(False, 'form')],
                    'res_model': 'stock.track.confirmation',
                    'target': 'new',
                    'context': ctx,
                }
            self._apply_inventory()
            self.inventory_quantity_set = False
        else:
            res = super(StockQuant, self).action_apply_inventory()
            return res


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def button_validate(self):
        # Clean-up the context key at validation to avoid forcing the creation of immediate
        # transfers.
        ctx = dict(self.env.context)
        ctx.pop('default_immediate_transfer', None)
        self = self.with_context(ctx)

        # Sanity checks.
        pickings_without_moves = self.browse()
        pickings_without_quantities = self.browse()
        pickings_without_lots = self.browse()
        products_without_lots = self.env['product.product']
        for picking in self:
            if not picking.move_ids and not picking.move_line_ids:
                pickings_without_moves |= picking

            picking.message_subscribe([self.env.user.partner_id.id])
            picking_type = picking.picking_type_id
            precision_digits = self.env['decimal.precision'].precision_get('Product Unit of Measure')
            no_quantities_done = all(float_is_zero(move_line.qty_done, precision_digits=precision_digits) for move_line in picking.move_line_ids.filtered(lambda m: m.state not in ('done', 'cancel')))
            no_reserved_quantities = all(float_is_zero(move_line.reserved_qty, precision_rounding=move_line.product_uom_id.rounding) for move_line in picking.move_line_ids)
            if no_reserved_quantities and no_quantities_done:
                pickings_without_quantities |= picking

            if picking_type.use_create_lots or picking_type.use_existing_lots:
                lines_to_check = picking.move_line_ids
                if not no_quantities_done:
                    lines_to_check = lines_to_check.filtered(lambda line: float_compare(line.qty_done, 0, precision_rounding=line.product_uom_id.rounding))
                for line in lines_to_check:
                    product = line.product_id
                    if product and product.tracking != 'none':
                        if not line.lot_name and not line.lot_id:
                            pickings_without_lots |= picking
                            products_without_lots |= product

        if not self._should_show_transfers():
            if pickings_without_moves:
                raise UserError(_('Please add some items to move.'))
            if pickings_without_quantities:
                raise UserError(self._get_without_quantities_error_message())
            if pickings_without_lots:
                raise UserError(_('You need to supply a Lot/Serial number for products %s.') % ', '.join(products_without_lots.mapped('display_name')))
        else:
            message = ""
            if pickings_without_moves:
                message += _('Transfers %s: Please add some items to move.') % ', '.join(pickings_without_moves.mapped('name'))
            if pickings_without_quantities:
                message += _('\n\nTransfers %s: You cannot validate these transfers if no quantities are reserved nor done. To force these transfers, switch in edit more and encode the done quantities.') % ', '.join(pickings_without_quantities.mapped('name'))
            if pickings_without_lots:
                message += _('\n\nTransfers %s: You need to supply a Lot/Serial number for products %s.') % (', '.join(pickings_without_lots.mapped('name')), ', '.join(products_without_lots.mapped('display_name')))
            if message:
                raise UserError(message.lstrip())

        # Run the pre-validation wizards. Processing a pre-validation wizard should work on the
        # moves and/or the context and never call `_action_done`.
        if not self.env.context.get('button_validate_picking_ids'):
            self = self.with_context(button_validate_picking_ids=self.ids)
        res = self._pre_action_done_hook()
        if res is not True:
            return res

        # Call `_action_done`.
        if self.env.context.get('picking_ids_not_to_backorder'):
            pickings_not_to_backorder = self.browse(self.env.context['picking_ids_not_to_backorder'])
            pickings_to_backorder = self - pickings_not_to_backorder
        else:
            pickings_not_to_backorder = self.env['stock.picking']
            pickings_to_backorder = self
        pickings_not_to_backorder.with_context(cancel_backorder=True)._action_done()
        pickings_to_backorder.with_context(cancel_backorder=False)._action_done()
        if self.move_ids:
            for move in self.move_ids:
                for move_line in self.move_line_ids:
                    if move_line.create_equipment:
                        serial_number = move_line.lot_name or move_line.lot_id.name
                        equipment = self.env['maintenance.equipment'].create({'name':move_line.product_id.name ,'serial_no': serial_number, 'product_id':move_line.product_id.id,'maintenance_team_id':move_line.product_id.maintenance_team_id.id, 'technician_user_id':move_line.product_id.technician_id.id,'stock_location_id':move_line.location_dest_id.id,'partner_id':self.partner_id.id})
                        serial = self.env['stock.lot'].search([('name','=',move_line.lot_name)])
                        serial.write({'equipment_id':equipment.id})

        if self.user_has_groups('stock.group_reception_report') \
                and self.user_has_groups('stock.group_auto_reception_report') \
                and self.filtered(lambda p: p.picking_type_id.code != 'outgoing'):
            lines = self.move_ids.filtered(lambda m: m.product_id.type == 'product' and m.state != 'cancel' and m.quantity_done and not m.move_dest_ids)
            if lines:
                # don't show reception report if all already assigned/nothing to assign
                wh_location_ids = self.env['stock.location']._search([('id', 'child_of', self.picking_type_id.warehouse_id.view_location_id.id), ('usage', '!=', 'supplier')])
                if self.env['stock.move'].search([
                        ('state', 'in', ['confirmed', 'partially_available', 'waiting', 'assigned']),
                        ('product_qty', '>', 0),
                        ('location_id', 'in', wh_location_ids),
                        ('move_orig_ids', '=', False),
                        ('picking_id', 'not in', self.ids),
                        ('product_id', 'in', lines.product_id.ids)], limit=1):
                    action = self.action_view_reception_report()
                    action['context'] = {'default_picking_ids': self.ids}
                    return action
        return True



class StockProductionLot(models.Model):
    _inherit = 'stock.lot'

    equipment_id = fields.Many2one('maintenance.equipment', "Linked Equipment")
