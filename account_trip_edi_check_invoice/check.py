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
        # Parameter:
        float_convert = 1000.0 # Every float has 3 dec. without comma
        
        # Pool used:
        invoice_pool = self.pool.get('edi.invoice')
        order_pool = self.pool.get('edi.order')
        
        filename = '~/etl/edi/elior/controllo/fatture.txt'
        filename = os.path.expanduser(filename)
        
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
        order_db = {}
        i = 0
        for row in open(filename, 'r'):
            i += 1
            if i % 1000 == 0:
                _logger.info('Import invoice line: %s' % i)
                
            # -----------------------------------------------------------------
            # Header data:
            # -----------------------------------------------------------------
            # Invoice part:
            invoice_number = row[:6].strip()
            invoice_date = '%s-%s-%s' % ( # mandatory
                row[6:10],
                row[10:12],
                row[12:14],
                )
            invoice_number = 'FT-%s-%s' % (
                row[6:10], 
                invoice_number, 
                )
                
            if invoice_number not in invoice_db:
                invoice_db[invoice_number] = invoice_pool.create(cr, uid, {
                    'name': invoice_number,
                    'date': invoice_date,
                    }, context=context)
                _logger.info('Invoice create: %s' % invoice_number)    
            
            # Order part:
            order_number = row[143:159].strip()            
            year = row[159:163].strip()
            if year:
                order_date = '%s-%s-%s' % (
                    year,
                    row[163:165],
                    row[165:167],
                    )                
            else:        
                order_date = False

            if order_number not in order_db:                
                order_ids = order_pool.search(cr, uid, [
                    ('name', '=', order_number),
                    ], context=context)    
                if order_ids:
                    order_db[order_number] = order_ids[0]
                else:    
                    order_db[order_number] = order_pool.create(cr, uid, {
                        'name': order_number,
                        'date': order_date,
                        }, context=context)    
            
            # DDT part:
            year = row[133:137].strip()
            if year:
                ddt_date = '%s-%s-%s' % (
                        year,
                        row[137:139],
                        row[139:141],
                        )
            else:
                ddt_date = False
                                
            # -----------------------------------------------------------------
            # Detail part:
            # -----------------------------------------------------------------
            data = {
                'invoice_id': invoice_db.get(invoice_number, False),

                'ddt_number': row[127:133].strip(),
                'ddt_date': ddt_date,

                'order_id': order_db.get(order_number, False),
                'order_number': order_number,
                'order_date': order_date, 
                'order_sequence': int(row[16:20]),

                'name': row[20:36].strip(),
                'article': row[36:47].strip(),
                'qty': float(row[47:62]) / float_convert,
                'price': float(row[62:77]) / float_convert,
                'subtotal': float(row[77:92]) / float_convert,
                'description': row[92:127].strip(),
                }
                
            self.create(cr, uid, data, context=context)
        return True
        
    _columns = {
        'invoice_id': fields.many2one('edi.invoice', 'Invoice'),
        'order_id': fields.many2one('edi.order', 'Order'),
        'order_sequence': fields.integer('Order position', readonly=True),
        'name': fields.char('Company code', size=16, 
            required=True, readonly=True),
        'article': fields.char('Customer code', size=16, readonly=True),
        'qty': fields.float('Q.ty', digits=(16, 3), readonly=True),
        'price': fields.float('Price', digits=(16, 3), readonly=True),
        'subtotal': fields.float('Subtotal', digits=(16, 3), readonly=True),
        'description': fields.char('Description', size=16, readonly=True),
        'ddt_number': fields.char('DDT #', size=20, readonly=True),
        'ddt_date': fields.date('DDT date', readonly=True),
        'order_number': fields.char('Company order #', size=25, readonly=True),
        'order_date': fields.date('Order date', readonly=True),
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
        # Set last to False
        file_pool = self.pool.get('edi.order.file')
        file_ids = file_pool.search(cr, uid, [
            ('order_id', 'in', ids),
            ], context=context)
        file_pool.write(cr, uid, file_ids, {
            'last': False,
            }, context=context)
            
        # Delete all order line for all order passed
        line_pool = self.pool.get('edi.order.line')
        line_ids = line_pool.search(cr, uid, [
            ('order_id', 'in', ids),
            ], context=context)
        line_pool.unlink(cr, uid, line_ids, context=context)
        
        # Read order from file:
        last_ids = [] # Save file used for load
        for order in self.browse(cr, uid, ids, context=context):
            if not order.file_ids:
                _logger.error('Order without file: %s' % order.name)
                continue
                
            last_file = order.file_ids[0]
            last_ids.append(last_file.id)
            if last_file.mode == 'delete':
                _logger.warning('Order deleted: %s' % order.name)
                continue
                
            #Create order line:
            for row in open(last_file.fullname, 'r'):
                data = {
                    'order_id': order.id,
                    'sequence': int(row[2336:2347]),
                    'name': row[2356:2391].strip(), 
                    'article': row[2391:2426].strip(),
                    'qty': row[2631:2641].strip(), 
                    'price': float(row[2877:2907]), 
                    'uom': row[2641:2644].strip(),
                    'description': row[2531:2631].strip(),
                    'total': float(row[2907:2937]),
                    }
                line_pool.create(cr, uid, data, context=context)
                
        # Set last file used:        
        return file_pool.write(cr, uid, last_ids, {
            'last': True,
            }, context=context)

    def generate_check_database(self, cr, uid, ids, context=None):
        ''' Generate mixed database invoice-order for check
        '''
        # Parameter:
        difference_gap = 0.001 # error on difference
        
        # Delete all check line:
        check_pool = self.pool.get('edi.order.line.check')
        
        check_ids = check_pool.search(cr, uid, [
            ('order_id', 'in', ids),
            ], context=context)
        check_pool.unlink(cr, uid, check_ids, context=context)
        
        for order in self.browse(cr, uid, ids, context=context):
            current_db = {}
            # -----------------------------------------------------------------
            # Start generate database from order:
            # -----------------------------------------------------------------
            for line in order.line_ids:
                article = line.article
                if article not in current_db:
                    current_db[article] = [
                        # Order:
                        line.price, 0.0, 0.0,
                        # Invoice:
                        0.0, 0.0, 0.0,
                        ]
                current_db[article][1] += line.qty # append qty
                current_db[article][2] += line.total # append subtotal
                
            
            # -----------------------------------------------------------------
            # Add database from invoice
            # -----------------------------------------------------------------
            for line in order.invoiced_ids:
                article = line.article
                if article not in current_db:
                    current_db[article] = [
                        # Order: price, qty, total
                        0.0, 0.0, 0.0,
                        # Invoice: price, qty, total
                        line.price, 0.0, 0.0,
                        ]
                current_db[article][4] += line.qty # append qty
                current_db[article][5] += line.subtotal # append subtotal
            
            # Write data:
            for article, record in current_db.iteritems():
                # Parse fields:
                (
                    order_price, order_qty, order_subtotal,
                    invoice_price, invoice_qty, invoice_subtotal,
                    ) = record
                    
                difference = order_subtotal - order_subtotal
                if abs(difference) < difference_gap: # no difference:
                    difference = 0.0
                data = {
                    'article': article,
                    'order_id': order.id,
                    'order_price': order_price, 
                    'order_qty': order_qty, 
                    'order_subtotal': order_subtotal,
                    'invoice_price': invoice_price, 
                    'invoice_qty': invoice_qty, 
                    'invoice_subtotal': invoice_subtotal,
                    'difference': difference,
                    }
                    
                # -------------------------------------------------------------
                # Cases:    
                # -------------------------------------------------------------                
                if not order_subtotal: # only order
                    data['state'] = 'order'
                    check_pool.create(cr, uid, data, context=context)                
                elif not invoice_subtotal: # only invoice
                    data['state'] = 'invoice'
                    check_pool.create(cr, uid, data, context=context)                                
                elif difference: # check difference: 
                    data['state'] = 'difference'
                else: # no difference:
                    data['state'] = 'correct'
                check_pool.create(cr, uid, data, context=context)
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
            folder_path = os.path.expanduser(folder.path)
            for root, dirs, files in os.walk(folder_path):
                for f in files:                    
                    if not f.endswith(extension):
                        _logger.warning('Jump file: %s' % f)
                        continue
                        
                    # ---------------------------------------------------------
                    # Read file data (name and content):
                    # ---------------------------------------------------------                    
                    # Open file for get order number:                    
                    filename = os.path.join(folder_path, f)
                    f_asc = open(filename, 'r')
                    row = f_asc.readline() # XXX only one row
                    f_asc.close()
                    
                    # Parse name:
                    mode = f[:6].upper()
                    
                    date = f[6:21]
                    
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
                    elif mode == 'ELIURG':
                        mode = 'urgent'
                    elif mode == 'ELICHG':
                        mode = 'delete'
                    else:
                        mode = 'error'    
                        
                    # ---------------------------------------------------------
                    # Order info:
                    # ---------------------------------------------------------
                    # Create order record:
                    order = row[19:29]

                    order_date = row[29:37]
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
    _order = 'datetime desc'

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
            ('error', 'Error in start file name'),
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

class EdiOrderLineCkeck(orm.Model):
    """ Model name: Edi Invoice Line
    """
    
    _name = 'edi.order.line.check'
    _description = 'EDI line check'
    _rec_name = 'article'
    _order = 'article'

    _columns = {
        'order_id': fields.many2one('edi.order', 'Order'),
        'article': fields.char('Customer code', size=16),
            
        'order_qty': fields.float('Order Q.ty', digits=(16, 3)),
        'order_price': fields.float('Order Price', digits=(16, 3)),
        'order_total': fields.float('Order Subtotal', digits=(16, 3)),

        'invoice_qty': fields.float('Invoice Q.ty', digits=(16, 3)),
        'invoice_price': fields.float('Invoice Price', digits=(16, 3)),
        'invoice_total': fields.float('Invoice Subtotal', digits=(16, 3)),

        'difference': fields.float('Difference', digits=(16, 3)),

        'state': fields.selection([
            ('correct', 'Correct'),
            ('order', 'Only order'),
            ('invoice', 'Only invoice'),
            ('different', 'Different'),
            ], 'state')
        }

class EdiOrder(orm.Model):
    """ Model name: Edi Order
    """
    
    _inherit = 'edi.order'
    
    _columns = {
        'file_ids': fields.one2many('edi.order.file', 'order_id',  'Files'),
        'line_ids': fields.one2many('edi.order.line', 'order_id',  'Line'),
        'invoiced_ids': fields.one2many('edi.invoice.line', 'order_id', 
            'Invoiced'),
        'check_ids': fields.one2many('edi.order.line.check', 'order_id', 
            'Check'),
        }
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
