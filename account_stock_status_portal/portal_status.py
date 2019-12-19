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
import openerp.netsvc as netsvc
import openerp.addons.decimal_precision as dp
from openerp.osv import fields, osv, expression, orm
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from openerp import SUPERUSER_ID
from openerp import tools
from openerp.tools.translate import _
from openerp.tools.float_utils import float_round as round
from openerp.tools import (
    DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, 
    DATETIME_FORMATS_MAP, 
    float_compare)


_logger = logging.getLogger(__name__)


class EdiPportalStockStatusEvent(orm.Model):
    ''' Wizard for status event
    '''
    _name = 'edi.portal.stock.status.event'
    _order = 'create_date desc'
    _rec_name = 'edi_portal_status'
    
    _columns = {
        'create_date': fields.date('Create date', readonly=True),
        'edi_portal_status': fields.text('Portal status', readonly=True,
            required=True),
        }

class EdiPortalStockStatus(orm.Model):
    """ Model name: EdiPortalStockStatus
    """
    
    _name = 'edi.portal.stock.status'
    _description = 'EDI Stock status'
    _rec_name = 'name'
    _order = 'name'

    # -------------------------------------------------------------------------
    # Scheduled update:
    # -------------------------------------------------------------------------
    def update_stock_status(self, cr, uid, username, filename, context=None):
        ''' Update stock status from external file
        '''
        def clean_text(value):
            ''' Clean text
            '''
            return (value or '').strip()

        def clean_float(value):
            ''' Clean float value
            '''
            value = (value or '').strip()
            if not value: 
                return 0.0

            value = value.replace(',', '.')
            try:
                return float(value)
            except:
                _logger.error('Error converting float: %s' % value)
                return 0.0

        def clean_date(value):
            ''' Clean date value
            '''
            value = (value or '').strip()
            value_split = value.split('/')
            
            if len(value_split) != 3:
                _logger.error('Error converting date: %s' % value)
                return False
                
            return '%s%s-%s-%s' % (
                '20' if len(value_split[2]) == 2 else '',
                value_split[2],
                value_split[1],
                value_split[0],
                )
            
        separator = ';'
        filename = os.path.expanduser(filename)
        f_csv = open(filename, 'r')
        
        # ---------------------------------------------------------------------
        # Clean al previous record:
        # ---------------------------------------------------------------------
        user_pool = self.pool.get('res.users')
        user_ids = user_pool.search(cr, uid, [
            ('login', '=', username),
            ], context=context)
        if not user_ids:
            _logger.error('User login %s not found!' % username)
            return False
        user_id = user_ids[0]
        
        line_ids = self.search(cr, uid, [
            ('user_id', '=', user_id),
            ], context=context)
        self.unlink(cr, uid, line_ids, context=context)
        
        # ---------------------------------------------------------------------
        # Start import new status:
        # ---------------------------------------------------------------------
        status = False
        header = False
        columns = False
        
        for line in f_csv:
            if not status:
                status = line
                continue
                
            if not header:
                header = line
                continue
            
            row = line.split(separator)
            if not columns:
                columns = len(row)
                
            if columns != len(row):
                _logger.error('Line with different columns: %s' % (line, ))   
            
            # Extract info:
            name = clean_text(row[0])
            parent = clean_text(name[:11])
            description = clean_text(row[1])
            uom = clean_text(row[2])
            stock_qty = clean_float(row[3])
            locked_qty = clean_float(row[4])
            available_qty = clean_float(row[5])
            provision_qty = clean_float(row[6])
            deadline = clean_date(row[7])
            
            data = {
                'user_id': user_id,
                'name': name, 
                'parent': parent,
                'description': description,
                'uom': uom,
                'stock_qty': stock_qty,
                'locked_qty': locked_qty,
                'available_qty': available_qty,
                'provision_qty': provision_qty,
                'deadline': deadline,
                }
            self.create(cr, uid, data, context=context)
            
        # Update portal status: 
        event_pool = self.pool.get('edi.portal.stock.status.event')
        event_ids = event_pool.search(cr, uid, [], context=context)
        event_pool.unlink(cr, uid, event_ids, context=context)
        event_pool.create(cr, uid, {
            'edi_portal_status': status,
            }, context=context)
            
        return True
        
    _columns = {
        'user_id': fields.many2one('res.users', 'Partner'),
        'name': fields.char('Product code', size=20, required=True),
        'parent': fields.char('Parent code', size=11, required=True),
        'description': fields.char('Product description', size=80),
        'uom': fields.char('Product code', size=64, required=True),
        'stock_qty': fields.float('Stock Q.', digits=(16, 2)),
        'locked_qty': fields.float('Locked Q.', digits=(16, 2)),
        'available_qty': fields.float('Available Q.', digits=(16, 2)),
        'provision_qty': fields.float('Provision Q.', digits=(16, 2)),
        'deadline': fields.date('Lot deadline'),
        }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
