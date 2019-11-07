#!/usr/bin/python
# -*- coding: utf-8 -*-
###############################################################################
#
# ODOO (ex OpenERP) 
# Open Source Management Solution
# Copyright (C) 2001-2015 Micronaet S.r.l. (<https://micronaet.com>)
# Developer: Nicola Riolini @thebrush (<https://it.linkedin.com/in/thebrush>)
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. 
# See the GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################


import os
import sys
import logging
import openerp
import openerp.addons.decimal_precision as dp
from openerp.osv import fields, osv, expression, orm
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from openerp import SUPERUSER_ID
from openerp import tools
from openerp.tools.translate import _
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, 
    DATETIME_FORMATS_MAP, 
    float_compare)

_logger = logging.getLogger(__name__)

class EdiLogisticLineSplitWizard(orm.TransientModel):
    ''' Wizard for for split line
    '''
    _name = 'edi.logistic.line.split.wizard'

    # -------------------------------------------------------------------------
    # Onchange:
    # -------------------------------------------------------------------------
    def onchange_quantity(self, cr, uid, ids, line_id, new_quantity, 
            context=None):
        ''' Check quantity
        '''   
        res = {}
        line_pool = self.pool.get('edi.soap.logistic.line')
        line = line_pool.browse(cr, uid, line_id, context=context)
        if new_quantity >= line.net_qty:
            return {
                'warning': {
                    'title': _('Quantity error'), 
                    'message': _('New q. %s >= total q.: %s') % (
                        new_quantity,
                        line.net_qty,
                        ),
                    }}
        return res   
        
    def onchange_pallet_code(self, cr, uid, ids, line_id, new_pallet, 
            context=None):
        ''' Save correct element
        '''
        line_pool = self.pool.get('edi.soap.logistic.line')
        line = line_pool.browse(cr, uid, line_id, context=context)
        pallet_id = False
        for pallet in line.logistic_id.pallet_ids:
            if new_pallet == pallet.name:
                pallet_id = pallet.id
                break
        if not pallet_id:
            raise osv.except_osv(
                _('Pallet error'), 
                _('Pallet not found use code present in the list'),
                )        
        return {'value': {
            'new_pallet_id': pallet_id,
            }}        

    # -------------------------------------------------------------------------
    # Wizard button event:
    # -------------------------------------------------------------------------
    def action_split(self, cr, uid, ids, context=None):
        ''' Event for button done
        '''
        logistic_pool = self.pool.get('edi.soap.logistic')
        line_pool = self.pool.get('edi.soap.logistic.line')
        if context is None: 
            context = {}        

        # Get wizard data:
        wiz_browse = self.browse(cr, uid, ids, context=context)[0]        
        
        line = wiz_browse.line_id
        new_pallet = wiz_browse.new_pallet
        new_pallet_id = wiz_browse.new_pallet_id.id
        new_net_qty = wiz_browse.new_quantity

        # Get old data:        
        old_net_qty = line.net_qty
        old_lord_qty = line.lord_qty
        old_parcel = line.parcel
        
        # New data:
        # TODO: 
        confirmed_qty = 0
        lord_qty = 0
        parcel = 0

        # Update previous line:
        line_pool.write(cr, uid, [line.id], {
            # TODO
            'net_qty': old_net_qty - new_net_qty,
            #'confirmed_qty': confirmed_qty,
            #'lord_qty': lord_qty,
            #'parcel': parcel,
            }, context=context)

        # ---------------------------------------------------------------------
        # Split line:
        # ---------------------------------------------------------------------
        line_pool.create(cr, uid, {
            'logistic_id': line.logistic_id.id,
            'pallet': new_pallet,
            'pallet_id': new_pallet_id,
            'product_id': line.product_id.id,
            'sequence': line.sequence,
            'name': line.name,
            'variable_weight': line.variable_weight,
            'lot': line.lot,
            'confirmed_qty': confirmed_qty,
            'net_qty': new_net_qty,
            'lord_qty': lord_qty,
            'parcel': parcel,
            'piece': line.piece,
            'deadline': line.deadline,
            'origin_country': line.origin_country,
            'provenance_country': line.provenance_country,
            'dvce': line.dvce,
            'dvce_date': line.dvce_date,
            'animo': line.animo,
            'sif': line.sif,
            'duty': line.duty,
            'invoice': line.invoice,
            'invoice_date': line.invoice_date,
            'mrn': line.mrn,
            # Related (not used):
            #'order_id': 
            #'duty_code': 
            #'chunk': 
            'splitted': True,
            }, context=context)

        # ---------------------------------------------------------------------
        # Return view updated:
        # ---------------------------------------------------------------------
        print context
        if context.get('return_logistic'):
            return { # for speed instead of reload
                'type': 'ir.actions.act_window',
                'name': _('Order splitted'),
                'view_type': 'form',
                'view_mode': 'form,tree',
                'res_id': line.logistic_id.id,
                'res_model': 'edi.soap.logistic',
                'view_id': False, #view_id, 
                'views': [(False, 'form'), (False, 'tree')],
                'domain': [],
                'context': context,
                'target': 'current', # 'new'
                'nodestroy': False,
                }
        else:
            res = logistic_pool.open_logistic_lines(
                cr, uid, [line.logistic_id.id], context=context)
            print res    
            return res    

    # -------------------------------------------------------------------------
    # Default function:            
    # -------------------------------------------------------------------------
    def get_default_line_id(self, cr, uid, context=None):
        ''' Get active_ids extract current
        '''
        if context is None:
            raise osv.except_osv(
                _('Error'), 
                _('Cannot select origin line'),
                )
        return context.get('active_id')

    _columns = {
        'line_id': fields.many2one(
            'edi.soap.logistic.line', 'Line', help='Line selected'),
        'new_quantity': fields.float('New quantity', digits=(16, 2), 
            required=True),
        'new_pallet': fields.integer('New pallet', required=True),    
        'new_pallet_id': fields.many2one('edi.soap.logistic.pallet', 
            'New pallet'),
        }
    
    _defaults = {
        'line_id': lambda s, cr, uid, ctx: s.get_default_line_id(cr, uid, ctx),
        }    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:


