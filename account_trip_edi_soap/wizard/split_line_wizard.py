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

# Wizard is not a really wizard but a line extension used for duplication
class EdiLogisticLineSplitWizard(orm.TransientModel):
    ''' Wizard for for split line
    '''
    _inherit = 'edi.soap.logistic.line'

    def open_edi_logistic_line_split_wizard(self, cr, uid, ids, context=None):
        '''
        '''
        model_pool = self.pool.get('ir.model.data')
        view_id = model_pool.get_object_reference(
            cr, uid, 
            'account_trip_edi_soap', 
            'edi_soap_logistic_line_split_wizard_view')[1]

        return {
            'type': 'ir.actions.act_window',
            'name': _('Split line'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': ids[0],
            'res_model': 'edi.soap.logistic.line',
            'view_id': view_id, 
            'views': [(view_id, 'form')],
            'domain': [],
            'context': context,
            'target': 'new',
            'nodestroy': False,
            }

    # -------------------------------------------------------------------------
    # Onchange:
    # -------------------------------------------------------------------------
    def onchange_quantity(self, cr, uid, ids, new_quantity, 
            context=None):
        ''' Check quantity
        '''   
        res = {}
        line = self.browse(cr, uid, ids, context=context)[0]
        if new_quantity >= line.net_qty:
            return {'warning': {
                'title': _('Quantity error'), 
                'message': _('New q. %s >= total q.: %s') % (
                    new_quantity,
                    line.net_qty,
                    ),
                }}
        return res   
        
    # -------------------------------------------------------------------------
    # Wizard button event:
    # -------------------------------------------------------------------------
    def action_split(self, cr, uid, ids, context=None):
        ''' Event for button done
        '''
        if context is None: 
            context = {}        

        # ---------------------------------------------------------------------
        # New data:
        # ---------------------------------------------------------------------
        line = self.browse(cr, uid, ids, context=context)[0]        
        new_pallet = line.new_pallet
        new_pallet_id = line.new_pallet_id.id
        new_parcel = float(line.new_quantity)

        if not new_parcel:
            raise osv.except_osv(
                _('Error'), 
                _('Cannot split, no parcel selected!'),
                )

        # ---------------------------------------------------------------------
        # Old data:        
        # ---------------------------------------------------------------------
        old_confirmed_qty = line.confirmed_qty
        old_net_qty = line.net_qty
        old_lord_qty = line.lord_qty
        old_parcel = line.parcel

        if new_pallet_id == pallet_id:
            raise osv.except_osv(
                _('Error'), 
                _('Cannot split, same pallet!'),
                )
        
        # ---------------------------------------------------------------------
        # Calculated new data:
        # ---------------------------------------------------------------------
        if not old_parcel:
            raise osv.except_osv(
                _('Error'), 
                _('Cannot split, no parcel in original line!'),
                )

        # New calculated (depend on parcel rate):
        new_rate = new_parcel / old_parcel
        new_confirmed_qty = old_confirmed_qty * new_rate
        new_net_qty = old_net_qty * new_rate
        new_lord_qty = old_lord_qty * new_rate

        # ---------------------------------------------------------------------
        # Update previous line:
        # ---------------------------------------------------------------------
        line_pool.write(cr, uid, [line.id], {
            'net_qty': old_net_qty - new_net_qty,
            'confirmed_qty': old_confirmed_qty - new_confirmed_qty,
            'lord_qty': old_lord_qty - new_lord_qty,
            'parcel': old_parcel - new_parcel,
            }, context=context)

        # ---------------------------------------------------------------------
        # Split line:
        # ---------------------------------------------------------------------
        line_pool.create(cr, uid, {
            'splitted_from_id': line.id,

            'logistic_id': line.logistic_id.id,
            'pallet': new_pallet,
            'pallet_id': new_pallet_id,
            'product_id': line.product_id.id,
            'sequence': line.sequence,
            'name': line.name,
            'customer_code': line.customer_code,
            'variable_weight': line.variable_weight,
            'lot': line.lot,
            'confirmed_qty': new_confirmed_qty,
            'net_qty': new_net_qty,
            'lord_qty': new_lord_qty,
            'parcel': new_parcel,
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
            }, context=context)

        # ---------------------------------------------------------------------
        # Return view updated:
        # ---------------------------------------------------------------------
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
            return logistic_pool.open_logistic_lines(
                cr, uid, [line.logistic_id.id], context=context)

    _columns = {
        'new_quantity': fields.integer('New parcel', digits=(16, 2)),
            
        'new_pallet': fields.integer('New pallet'),    
        'new_pallet_id': fields.many2one('edi.soap.logistic.pallet', 
            'New pallet'),       
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
