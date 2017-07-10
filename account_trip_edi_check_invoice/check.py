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
from openerp import SUPERUSER_ID
from openerp import tools
from openerp.tools.translate import _
from openerp.tools.float_utils import float_round as round
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, 
    DATETIME_FORMATS_MAP, 
    float_compare)


_logger = logging.getLogger(__name__)


class EdiInvoice(orm.Model):
    """ Model name: Edi Invoice
    """
    
    _name = 'edi.invoice'
    _description = 'EDI invoice'
    _rec_name = 'name'
    _order = 'name'
    
    _columns = {
        'name': fields.char('Number', size=20, required=True),
        'date': fields.date('Invoice date', required=True),
        }

class EdiInvoiceLine(orm.Model):
    """ Model name: Edi Invoice Line
    """
    
    _name = 'edi.invoice.line'
    _description = 'EDI invoice line'
    _rec_name = 'name'
    _order = 'invoice_id,name'
    
    def import_invoice_line_from_account(self, cr, uid, context=None):
        ''' Import procedure for get all invoice line for check
            Export with sprix: spx780
        '''
        # Pool used:
        invoice_pool = self.pool.get('edi.invoice')
        
        filename = '~/etl/edi/elior/controllo/fatture.txt'
        
        # ---------------------------------------------------------------------
        # Clean previous elements:
        # ---------------------------------------------------------------------
        # Details:
        line_ids = self.search(cr, uid, [], context=context)
        self.unlink(cr, uid, line_ids, context=context)
        
        # Invoice:
        invoice_ids = invoice_pool.search(cr, uid, [], context=context)
        invoice_pool.unlink(cr, uid, invoice_ids, context=context)
        
        invoice_db = {}
        for row in open(filename, 'r'):
            # -----------------------------------------------------------------
            # Header data:
            # -----------------------------------------------------------------
            invoice_number = row[:6]
            invoice_date = '%s-%s-%s' % (
                row[6:10],
                row[10:12],
                row[12:14],
                )
            invoice_number = 'FT-%s-%s' % (
                invoice_number, row[6:10], )
                
            if invoice_number not in invoice_db:
                invoice_db['invoice_number'] = invoice_pool.create(cr, uid, {
                    'name': invoice_number,
                    'date': invoice_date,
                    }, context=context)
                    
            # -----------------------------------------------------------------
            # Detail data:
            # -----------------------------------------------------------------
            data = {
                'invoice_id': invoice_db.get(invoice_number, False),                
                'order_sequence': int(row[16:20]),
                'name': row[20:36],
                'article': row[36:47],
                'qty': row[47:62],
                'price': row[62:77],
                'uom': row[77:92],
                'description': row[92:127],
                'ddt_number': row[127:133],
                'ddt_date': '%s-%s-%s' % (
                    row[133:137],
                    row[137:139],
                    row[139:141],
                    ),
                'order_number': row[143:159],
                'order_date': '%s-%s-%s' % (
                    row[159:163],
                    row[163:165],
                    row[165:167],
                    ), 
                }
                
            self.create(cr, uid, data, context=context)
        return True
        
    _columns = {
        'invoice_id': fields.many2one('edi.invoice', 'Invoice'),
        'order_sequence': fields.integer('Order position', 
            readonly=True),
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
        'order_date': fields.date('Order date', 
            required=True, readonly=True),
        }

class EdiInvoice(orm.Model):
    """ Model name: Edi Invoice
    """
    
    _inherit = 'edi.invoice'

    _columns = {
        'line_ids': fields.one2many('edi.invoice.line', 'invoice_id', 'Lines'),
        }
        
class EdiOrder(orm.Model):
    """ Model name: Edi Order
    """
    
    _name = 'edi.order'
    _description = 'EDI order'
    _rec_name = 'name'

    # -------------------------------------------------------------------------
    # Button event:
    # -------------------------------------------------------------------------
    def load_order_line_details(self, cr, uid, ids, context=None):
        ''' Load current order details (also used for N orders)
        '''
        # Delete all order line for all order passed
        
        # Search last file:
        
        # Load order detail from file
        
                    
                    # Create order line:
                    #for row in open(filename, 'r'):
                    #    data = {
                    #        #'order_id':,
                    #        'order_sequence': row[20:30], # XXX errato
                    #        'name': row[320:355], 
                    #        'article': row[355:390],
                    #        'qty': row[595:605], 
                    #        'price': row[841:871], 
                    #        'uom': row[605:608],
                    #        'description': row[495:595],
                    #        'total': row[871:901],
                    #        }
        
        return True
        
        
    _columns = {
        'name': fields.char('Number', size=25, required=True),
        'date': fields.datetime('Date', readonly=True),
        }

class EdiOrder(orm.Model):
    """ Model name: Edi Order
    """
    
    _name = 'edi.order.folder'
    _description = 'EDI order folder'
    _rec_name = 'name'

    def load_file_in_folder(self, cr, uid, ids, context=None):
        """ Load file in this folder (used also for scheduled)
        """
        # Parameters:
        extension = 'ASC'
        
        # Pool used:
        order_pool = self.pool.get('edi.order')
        file_pool = self.pool.get('edi.order.file')
        
        for folder in self.browse(cr, uid, ids, context=context):
            # Delete all previouse file in folder:
            file_ids = file_pool.search(cr, uid, [
                ('folder_id', '=', folder.id),
                ], context=context)
            file_pool.unlink(cr, uid, file_ids, context=context)
            
            # TODO order_loaded for speed up search order operations?
            for root, dirs, files in os.walk(folder.path):
                for f in files:                    
                    if not f.endswith(estension):
                        _logger.warning('Jump file: %s' % f)
                        continue
                        
                    # ---------------------------------------------------------
                    # Read file data (name and content):
                    # ---------------------------------------------------------                    
                    # Open file for get order number:                    
                    filename = os.path.join(folder.path, f)
                    f_asc = open(filename, 'r')
                    row = f_asc.readline() # XXX only one row
                    f_asc.close()
                    
                    # Parse name:
                    mode = f[:6].upper()
                    
                    date = f[6:22]
                    
                    date = '%s-%s-%s %s:%s:%s' % (
                        # Date:
                        date[:4],
                        date[4:6],
                        date[6:8],
                        
                        # Time:
                        date[8:10],
                        date[10:12],
                        date[12:14],
                        )
                    
                    if mode == 'ELIORD':
                        mode = 'create'
                    if mode == 'ELIURG':
                        mode = 'urgent'
                    if mode == 'ELICHG':
                        mode = 'delete'
                        
                    # ---------------------------------------------------------
                    # Order info:
                    # ---------------------------------------------------------
                    # Create order record:
                    order = row[20:30]

                    order_date = row[30:38]
                    order_date = '%s-%s-%s' % (
                        order_date[:4],
                        order_date[4:6],
                        order_date[6:8],
                        )
                    
                    order_ids = order_pool.search(cr, uid, [
                        ('name', '=', order),
                        # XXX no date
                        ], context=context)                    
                    
                    if order_ids: # Nothing:
                        order_id = order_ids[0]
                        # TODO check if more order!
                    else: # Create
                        order_id = order_pool.create(cr, uid, {
                            'name': order,
                            'date': order_date,
                            }, context=context)        

                    # ---------------------------------------------------------
                    # Create file item (not write because deleted all):
                    # ---------------------------------------------------------
                    file_pool.create(cr, uid, {
                        'order_id': order_id,
                        'folder_id': folder.id,
                        'name': f,
                        'last': False,
                        'datetime': date,
                        'mode': mode,
                        }, context=context)
        return True                    

    def load_scheduled_folder_selected(self, cr, uid, ids, context=None):
        ''' Load all selected folder
        '''
        folder_ids = self.search(cr, uid, [
            ('autoload', '=', True),
            ], context=context)
            
        return self.load_file_in_folder(cr, uid, folder_ids, context=context)
        
    _columns = {
        'autoload': fields.boolean('Auto load', 
            help='Schedule for auto load operation'),
        'name': fields.char('Name', size=25, required=True),
        'path': fields.char('Path', size=180, required=False),
        'note': fields.text('Note'),
        }

class EdiOrderFile(orm.Model):
    """ Model name: Edi Order File
    """
    
    _name = 'edi.order.file'
    _description = 'EDI order file'
    _rec_name = 'name'

    def _get_fullname_file_name(
            self, cr, uid, ids, fields, args, context=None):
        ''' Fields function for calculate 
        '''
        res = {}
        for item in self.browse(cr, uid, ids, context=context):
            res[item.id] = os.path.join(item.folder_id.path, item.name)
        return res    

    _columns = {
        'order_id': fields.many2one('edi.order', 'Order'),
        'folder_id': fields.many2one('edi.order.folder', 'History folder'),        
        'name': fields.char('Name', size=40, required=True, readonly=True),
        'fullname': fields.function(
            _get_fullname_file_name, method=True, 
            type='char', string='Fullname', size=200, store=False),                         
        'last': fields.boolean('Last'),
        'datetime': fields.date('Datetime', required=False, readonly=True,
            help='Datetime form customer EDI program (not file datetime)'),
        'mode': fields.selection([
            ('create', 'Create (ELIORD)'),
            ('urgent', 'Urgent (ELIURG)'),
            ('delete', 'Delete (ELICHG)'),
            ], 'Mode', readonly=False),
        }
    
    _defaults = {
        'mode': lambda *x: 'create',
        }    

class EdiOrderLine(orm.Model):
    """ Model name: Edi Invoice Line
    """
    
    _name = 'edi.order.line'
    _description = 'EDI line'
    _rec_name = 'name'

    _columns = {
        'order_id': fields.many2one('edi.order', 'Order'),
        'sequence': fields.char('Seq.', 
            size=10, readonly=True),
        'name': fields.char('Company code', size=16, 
            required=True, readonly=True),
        'article': fields.char('Customer code', size=16,    
            required=True, readonly=True),
        'uom': fields.char('UOM', size=5, 
            required=True, readonly=True),
        'qty': fields.float('Q.ty', digits=(16, 3), 
            required=True, readonly=True),
        'price': fields.float('Price', digits=(16, 3), 
            required=True, readonly=True),
        'description': fields.char('Description', size=16, 
            required=True, readonly=True),
        'total': fields.float('Subtotal', digits=(16, 3), 
            required=True, readonly=True),
        }

class EdiOrder(orm.Model):
    """ Model name: Edi Order
    """
    
    _inherit = 'edi.order'
    
    _columns = {
        'file_ids': fields.one2many('edi.order.file', 'order_id',  'Files'),
        'line_ids': fields.one2many('edi.order.line', 'order_id',  'Line'),
        }
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
