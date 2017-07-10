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
        filename = '~/etl/script/elior/controllo/fatture.txt'
        
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
                'order_sequence': ,
                'name': ,
                'article': ,
                'qty': ,
                'price': ,
                'uom': ,
                'description': ,
                'ddt_number': ,
                'ddt_date': ,
                'order_number': ,
                'ddt_date': ,
                }
        
        
        return True
        
    _columns = {
        'invoice_number': fields.char('Invoice #', size=20, required=True),
        'invoice_date': fields.date('Invoice date', required=True),
        'order_sequence': fields.char('Order position', size=10),
        'name': fields.char('Company code', size=16, required=True),
        'article': fields.char('Customer code', size=16, required=True),
        'qty': fields.float('Q.ty', digits=(16, 3), required=True),
        'price': fields.float('Price', digits=(16, 3), required=True),
        'uom': fields.char('UOM', size=5, required=True),
        'description': fields.char('Description', size=16, required=True),
        'ddt_number': fields.char('DDT #', size=20, required=True),
        'ddt_date': fields.date('Invoice date', required=True),
        'order_number': fields.char('Company order #', size=25, required=True),
        'ddt_date': fields.date('Invoice date', required=True),
        }
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
