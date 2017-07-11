# -*- coding: utf-8 -*-
###############################################################################
#
# ODOO (ex OpenERP) 
# Open Source Management Solution
# Copyright (C) 2001-2015 Micronaet S.r.l. (<http://www.micronaet.it>)
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


class EdiLoadInvoiceLineWizard(orm.TransientModel):
    ''' Wizard for load invoice line
    '''
    _name = 'edi.load.invoice.line.wizard'

    # --------------------
    # Wizard button event:
    # --------------------

    def action_done(self, cr, uid, ids, context=None):
        ''' Event for button done
        '''
        if context is None: 
            context = {}        

        line_pool = self.pool.get('edi.invoice.line')        
        line_pool.import_invoice_line_from_account(cr, uid, context=context)        
        return True

    def action_export(self, cr, uid, ids, context=None):
        ''' Event for button extract
        '''
        if context is None: 
            context = {}
        
        # Pool used:
        order_pool = self.pool.get('edi.order')
        #line_pool = self.pool.get('edi.invoice.line')        
        
        # 0. Load history files:
        # XXX Not here just use scheduled operation!!!
        
        # 1. Import invoice:
        #line_pool.import_invoice_line_from_account(cr, uid, context=context)
        
        # 2. Get selected order:
        order_ids = order_pool.search(cr, uid, [
            ('invoiced', '=', True)], context=context)
        
        # 3. Load data in all selected order:
        order_pool.load_order_line_details(cr, uid, order_ids, context=context)
        
        # 4. Generate check database:
        order_pool.generate_check_database(cr, uid, order_ids, context=context)
            
        # 5. Extract in Excel:
        return order_pool.extract_check_data_xlsx(cr, uid, order_ids, context=context)

    def action_only_export(self, cr, uid, ids, context=None):
        ''' Event for button extract
        '''
        if context is None: 
            context = {}
        
        # Pool used:
        order_pool = self.pool.get('edi.order')
        
        order_ids = order_pool.search(cr, uid, [
            ('invoiced', '=', True)], context=context)
        return order_pool.extract_check_data_xlsx(cr, uid, order_ids, context=context)

    _columns = {
        'note': fields.text('Procedure', readonly=True),
        }
        
    _defaults = {
        'note': lambda *x: _('''
            <b>Invoice line load procedure:</b><br/>
            <p>
            Launch sprix from Mexal Service menu:
            # 780 (Check invoice)
            </p>
            <p>
            When the exprot is finished press <b>DONE</b>
            </p>
            '''),
        }    

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:


