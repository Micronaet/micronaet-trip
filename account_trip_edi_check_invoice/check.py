# -*- coding: utf-8 -*-
###############################################################################
#
#    Copyright (C) 2001-2014 Micronaet SRL (<http://www.micronaet.it>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
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
from openerp import SUPERUSER_ID, api
from openerp import tools
from openerp.tools.translate import _
from openerp.tools.float_utils import float_round as round
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, 
    DATETIME_FORMATS_MAP, 
    float_compare)


_logger = logging.getLogger(__name__)


class EdiInvoiceLine(orm.Model):
    """ Model name: Edi Invoice Line
    """
    
    _name = 'edi.invoice.line'
    _description = 'EDI invoice line'
    _rec_name = 'name'
    _order = 'invoice_name,name'
    
    def import_invoice_line_from_account(self, cr, uid, context=None):
        ''' Import procedure for get all invoice line for check
            Export with sprix: spx780
        '''
        filename = '~/etl/edi/elior/controllo/fatture.txt'
        
        # Delete all previous records:
        line_ids = self.search(cr, uid, [], context=context)
        self.unlink(cr, uid, line_ids, context=context)
        
        for row in open(filename, 'r'):
            data = {
                'invoice_number': row[:6],
                'invoice_date': '%s-%s-%s' % (
                    row[6:10],
                    row[10:12],
                    row[12:14],
                    ),
                'order_sequence': row[14:18],
                'name': row[18:34],
                'article': row[34:45],
                'qty': row[45:60],
                'price': row[60:75],
                'uom': row[75:90],
                'description': row[90:125],
                'ddt_number': row[125:131],
                'ddt_date': row[131:141],
                'order_number': row[141:157],
                'order_date': row[157:167],
                }
        
        
        return True
        
    _columns = {
        'invoice_number': fields.char('Invoice #', size=20, 
            required=True, readonly=True),
        'invoice_date': fields.date('Invoice date', 
            required=True, readonly=True),
        'order_sequence': fields.char('Order position', 
            size=10, readonly=True),
        'name': fields.char('Company code', size=16, 
            required=True, readonly=True),
        'article': fields.char('Customer code', size=16,    
            required=True, readonly=True),
        'qty': fields.float('Q.ty', digits=(16, 3), 
            required=True, readonly=True),
        'price': fields.float('Price', digits=(16, 3), 
            required=True, readonly=True),
        'uom': fields.char('UOM', size=5, 
            required=True, readonly=True),
        'description': fields.char('Description', size=16, 
            required=True, readonly=True),
        'ddt_number': fields.char('DDT #', size=20, 
            required=True, readonly=True),
        'ddt_date': fields.date('Invoice date', 
            required=True, readonly=True),
        'order_number': fields.char('Company order #', size=25, 
            required=True, readonly=True),
        'order_date': fields.date('Invoice date', 
            required=True, readonly=True),
        }

class EdiOrder(orm.Model):
    """ Model name: Edi Order
    """
    
    _name = 'edi.order'
    _description = 'EDI order'
    _rec_name = 'name'

    _columns = {
        'name': fields.char('Company order #', size=25, 
            required=True, readonly=True),
        'order_sequence': fields.char('Order position', 
            size=10, readonly=True),
        'name': fields.char('Company code', size=16, 
            required=True, readonly=True),
        'article': fields.char('Customer code', size=16,    
            required=True, readonly=True),
        'qty': fields.float('Q.ty', digits=(16, 3), 
            required=True, readonly=True),
        'price': fields.float('Price', digits=(16, 3), 
            required=True, readonly=True),
        'uom': fields.char('UOM', size=5, 
            required=True, readonly=True),
        'description': fields.char('Description', size=16, 
            required=True, readonly=True),
        }
        
class EdiOrderLine(orm.Model):
    """ Model name: Edi Invoice Line
    """
    
    _name = 'edi.order.line'
    _description = 'EDI line'
    _rec_name = 'name'

    _columns = {
        'order_id': fields.many2one(
            'openerp.model', 'Label', 
            required=False),
        'order_sequence': fields.char('Order position', 
            size=10, readonly=True),
        'name': fields.char('Company code', size=16, 
            required=True, readonly=True),
        'article': fields.char('Customer code', size=16,    
            required=True, readonly=True),
        'qty': fields.float('Q.ty', digits=(16, 3), 
            required=True, readonly=True),
        'price': fields.float('Price', digits=(16, 3), 
            required=True, readonly=True),
        'uom': fields.char('UOM', size=5, 
            required=True, readonly=True),
        'description': fields.char('Description', size=16, 
            required=True, readonly=True),
        }


    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
