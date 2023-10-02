# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#
#    For Module Support : devintelle@gmail.com  or Skype : devintelle 
#
##############################################################################

from odoo import models, fields, api, _


class hr_payslip(models.Model):
    _inherit = 'hr.payslip'
    
    installment_ids = fields.Many2many('installment.line',string='Installment Lines')
    installment_amount = fields.Float('Installment Amount',compute='get_installment_amount')
    installment_int = fields.Float('Installment Amount',compute='get_installment_amount')
    
    def compute_sheet(self):
        for payeslip in self:
            installment_ids = self.env['installment.line'].search(
                    [('employee_id', '=', payeslip.employee_id.id), ('loan_id.state', '=', 'done'),
                     ('is_paid', '=', False),('date','<=',payeslip.date_to)])
            if installment_ids:
                payeslip.installment_ids = [(6, 0, installment_ids.ids)]
        return super(hr_payslip,self).compute_sheet()
        

    @api.depends('installment_ids')
    def get_installment_amount(self):
        for payslip in self:
            amount = 0
            int_amount = 0
            if payslip.installment_ids:
                for installment in payslip.installment_ids:
                    if not installment.is_skip:
                        amount += installment.installment_amt
                    int_amount += installment.ins_interest
                    
            payslip.installment_amount = amount
            payslip.installment_int = int_amount

    @api.onchange('employee_id')
    def onchange_employee(self):
        if self.employee_id:
            installment_ids = self.env['installment.line'].search(
                [('employee_id', '=', self.employee_id.id), ('loan_id.state', '=', 'done'),
                 ('is_paid', '=', False),('date','<=',self.date_to)])
            if installment_ids:
                self.installment_ids = [(6, 0, installment_ids.ids)]

    @api.onchange('installment_ids')
    def onchange_installment_ids(self):
        if self.employee_id:
            installment_ids = self.env['installment.line'].search(
                [('employee_id', '=', self.employee_id.id), ('loan_id.state', '=', 'done'),
                 ('is_paid', '=', False), ('date', '<=', self.date_to)])
            if installment_ids:
                self.installment_ids = [(6, 0, installment_ids.ids)]

    def action_payslip_done(self):
        res = super(hr_payslip, self).action_payslip_done()
        print ("self======",self)
        for payslip in self:
            if payslip.installment_ids:
                for installment in payslip.installment_ids:
                    if not installment.is_skip:
                        installment.is_paid = True
                    installment.payslip_id = payslip.id

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
