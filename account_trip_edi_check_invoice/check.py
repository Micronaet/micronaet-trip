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
import xlsxwriter
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


class EdiDDT(orm.Model):
    """ Model name: Edi DDT
    """
    
    _name = 'edi.ddt'
    _description = 'EDI DDT'
    _rec_name = 'name'
    _order = 'name'
    
    _columns = {
        'name': fields.char('Number', size=20, required=True),
        'date': fields.date('DDT date', required=True),
        }

class EdiDDTLine(orm.Model):
    """ Model name: Edi DDT Line
    """
    
    _name = 'edi.ddt.line'
    _description = 'EDI DDT line'
    _rec_name = 'name'
    _order = 'ddt_id,name'
    
    def import_ddt_line_from_account(self, cr, uid, context=None):
        ''' Import procedure for get all ddt line for check
            Export with sprix: spx780
        '''
        # Parameter:
        float_convert = 1000.0 # Every float has 3 dec. without comma
        
        # Pool used:
        ddt_pool = self.pool.get('edi.ddt')
        order_pool = self.pool.get('edi.order')
        
        filename = '~/etl/edi/elior/controllo/ddt.txt'
        filename = os.path.expanduser(filename)
        
        # ---------------------------------------------------------------------
        # Clean previous elements:
        # ---------------------------------------------------------------------
        # DDT Details:
        line_ids = self.search(cr, uid, [], context=context)
        self.unlink(cr, uid, line_ids, context=context)
        _logger.info('Delete DDT line: %s' % len(line_ids))
        
        # DDT:
        ddt_ids = ddt_pool.search(cr, uid, [], context=context)
        ddt_pool.unlink(cr, uid, ddt_ids, context=context)
        _logger.info('Delete DDT: %s' % len(line_ids))
        
        ddt_db = {}
        order_db = {}
        i = 0
        for row in open(filename, 'r'):
            i += 1
            if i % 1000 == 0:
                _logger.info('Import DDT line: %s' % i)
                
            # -----------------------------------------------------------------
            # Header data:
            # -----------------------------------------------------------------
            # ddt part:
            ddt_number = row[:6].strip()
            ddt_date = '%s-%s-%s' % ( # mandatory
                row[6:10],
                row[10:12],
                row[12:14],
                )
            ddt_number = 'DDT-%s-%s' % (
                row[6:10], 
                ddt_number, 
                )
                
            if ddt_number not in ddt_db:
                ddt_db[ddt_number] = ddt_pool.create(cr, uid, {
                    'name': ddt_number,
                    'date': ddt_date,
                    }, context=context)
                _logger.info('ddt create: %s' % ddt_number)    
            
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
                'ddt_id': ddt_db.get(ddt_number, False),

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
        
        # Set order ddt:
        _logger.info('Set DDT order [Tot.: %s]' % len(order_db))
        return order_pool.write(cr, uid, order_db.values(), {
            'has_ddt': True,
            }, context=context)            
        
    _columns = {
        'ddt_id': fields.many2one('edi.ddt', 'DDT'),
        'order_id': fields.many2one('edi.order', 'Order'),
        'order_sequence': fields.integer('Order position', readonly=True),
        'name': fields.char('Company code', size=16, 
            required=True, readonly=True),
        'article': fields.char('Customer code', size=16, readonly=True),
        'qty': fields.float('Q.ty', digits=(16, 3), readonly=True),
        'price': fields.float('Price', digits=(16, 3), readonly=True),
        'subtotal': fields.float('Subtotal', digits=(16, 3), readonly=True),
        'description': fields.char('Description', size=16, readonly=True),
        'order_number': fields.char('Company order #', size=25, readonly=True),
        'order_date': fields.date('Order date', readonly=True),
        }

class EdiDDT(orm.Model):
    """ Model name: Edi DDT
    """
    
    _inherit = 'edi.ddt'

    _columns = {
        'line_ids': fields.one2many('edi.ddt.line', 'ddt_id', 'Lines'),
        }

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
        _logger.info('Delete invoice line: %s' % len(line_ids))
        
        # Invoice:
        invoice_ids = invoice_pool.search(cr, uid, [], context=context)
        invoice_pool.unlink(cr, uid, invoice_ids, context=context)
        _logger.info('Delete invoice: %s' % len(line_ids))
        
        # Set order all not invoiced:
        order_ids = order_pool.search(cr, uid, [
            ('has_invoice', '=', True),
            ], context=context)
        order_pool.write(cr, uid, order_ids, {
            'has_invoice': False,
            }, context=context)
        _logger.info('Set all order as not invoiced')
        
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
        
        # Set order invoiced:
        _logger.info('Set invoiced order [Tot.: %s]' % len(order_db))
        return order_pool.write(cr, uid, order_db.values(), {
            'has_invoice': True,
            }, context=context)            
        
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
        # Reset last state:    
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
                
            if len(order.file_ids) == 1:
                last_file = order.file_ids[0]
            else:
                last_file = sorted(
                    order.file_ids, key=lambda x: x.datetime)[-1]
                    
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

    # -------------------------------------------------------------------------
    # Button event:
    # -------------------------------------------------------------------------
    def generate_check_database_mode_ddt(self, cr, uid, ids, context=None):
        ''' Generate check database for DDT:
        '''
        return self.generate_check_database(
            cr, uid, ids, mode='ddt', context=context)

    def generate_check_database_mode_invoice(self, cr, uid, ids, context=None):
        ''' Generate check database for Invoice:
        '''
        return self.generate_check_database(
            cr, uid, ids, mode='invoice', context=context)

    # -------------------------------------------------------------------------
    # Procedure:    
    # -------------------------------------------------------------------------
    def generate_check_database(self, cr, uid, ids, mode='invoice', 
            context=None):
        ''' Generate mixed database invoice-order for check
        '''
        # Parameter:
        difference_gap = 0.005 # error on difference
        
        # Delete all check line:
        check_pool = self.pool.get('edi.order.line.check')
        if mode == 'ddt':
            key_field = 'ddt_order_id'
            detail_field = 'ddt_ids'
            foreign_field = 'ddt_id'
        else:    
            key_field = 'invoice_order_id'
            detail_field = 'invoiced_ids'
            foreign_field = 'invoice_id'

        check_ids = check_pool.search(cr, uid, [
            (key_field, 'in', ids),
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
                        
                        # Invoice / DDT:
                        0.0, 0.0, 0.0,
                        
                        [], # invoice / DDT                      
                        line.name, # Company code
                        ]
                current_db[article][1] += line.qty # append qty
                current_db[article][2] += line.total # append subtotal
            
            # -----------------------------------------------------------------
            # Add database from invoice
            # -----------------------------------------------------------------
            for line in order.__getattr__(detail_field):
                article = line.article
                document = line.__getattr__(foreign_field)
                
                if article not in current_db:
                    current_db[article] = [
                        # Order: price, qty, total
                        0.0, 0.0, 0.0,
                        # Invoice / DDT: price, qty, total
                        line.price, 0.0, 0.0,
                        [], # Invoice / DDT
                        line.name, # Company code
                        ]
                if not current_db[article][3]:
                    current_db[article][3] = line.price
                current_db[article][4] += line.qty # append qty
                current_db[article][5] += line.subtotal # append subtotal
                if document.name not in current_db[article][6]:
                    current_db[article][6].append(document.name)
            
            # Write data:
            for article, record in current_db.iteritems():
                # Parse fields:
                (
                    order_price, order_qty, order_subtotal,
                    invoice_price, invoice_qty, invoice_subtotal,
                    invoice_info, name) = record
                    
                difference = invoice_subtotal - order_subtotal
                if abs(difference) < difference_gap: # no difference:
                    difference = 0.0
                data = {
                    'article': article,
                    'name': name,
                    key_field: order.id,
                    
                    'order_price': order_price, 
                    'order_qty': order_qty, 
                    'order_total': order_subtotal,
                    
                    'invoice_price': invoice_price, 
                    'invoice_qty': invoice_qty, 
                    'invoice_total': invoice_subtotal,
                    
                    'difference': difference,
                    
                    'invoice_info': ', '.join(invoice_info),
                    }
                    
                # -------------------------------------------------------------
                # Cases:
                # -------------------------------------------------------------        
                if not order_subtotal: # only order
                    data['state'] = 'invoice'
                elif not invoice_subtotal: # only invoice
                    data['state'] = 'order'
                elif difference: # check difference: 
                    data['state'] = 'difference'
                else: # no difference:
                    data['state'] = 'correct'
                check_pool.create(cr, uid, data, context=context)
        return True
        
    def extract_check_data_xlsx(self, cr, uid, ids, context=None):
        ''' Extract order passed in in check XLSX file
        '''
        # ---------------------------------------------------------------------
        # Utility:
        # ---------------------------------------------------------------------
        def write_xls_mrp_line(WS, row, line):
            ''' Write line in excel file
            '''
            col = 0
            for item, format_cell in line:
                WS.write(row, col, item, format_cell)
                col += 1
            return True
        
        if context is None:
            context = {}
            
        # Pool used:
        attachment_pool = self.pool.get('ir.attachment')
        # ---------------------------------------------------------------------
        # XLS file:
        # ---------------------------------------------------------------------
        filename = '/tmp/edi_invoice_check.xlsx'
        filename = os.path.expanduser(filename)
        _logger.info('Start export status on %s' % filename)

        # Open file and write header
        WB = xlsxwriter.Workbook(filename)
        # 2 Sheets
        WS_db = {
            'order': WB.add_worksheet('Solo ordini'),
            'invoice': WB.add_worksheet('Solo fatture'),
            'difference': WB.add_worksheet('Differenze'),
            }
        counter = {
            'order': 1,
            'invoice': 1,
            'difference': 1,
            }    
            
        # ---------------------------------------------------------------------
        # Format elements:
        # ---------------------------------------------------------------------
        num_format = '0.##0'
        # Text:
        format_title = WB.add_format({
            'bold': True, 
            'font_color': 'black',
            'font_name': 'Arial',
            'font_size': 10,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': 'gray',
            'border': 1,
            #'text_wrap': True,
            })

        format_text = WB.add_format({
            'font_name': 'Arial',
            'align': 'left',
            'font_size': 9,
            'border': 1,
            })
            
        # Number:
        format_white = WB.add_format({
            'font_name': 'Arial',
            'align': 'right',
            'font_size': 9,
            'border': 1,
            'num_format': num_format,
            #'bg_color': '#ff9999', #'red',
            })
        format_red = WB.add_format({
            'font_name': 'Arial',
            'align': 'right',
            'font_size': 9,
            'border': 1,
            'num_format': num_format,
            'bg_color': '#ff9999', #'red',
            })
        format_green = WB.add_format({
            'font_name': 'Arial',
            'align': 'right',
            'font_size': 9,
            'border': 1,
            'num_format': num_format,
            'bg_color': '#c1ef94', #'green',
            })
        
        # Number database for heat / cold:    
        cold = {
            0: WB.add_format({
                'font_name': 'Arial',
                'align': 'right',
                'font_size': 9,
                'border': 1,
                'num_format': num_format,
                'bg_color': '#ddffd9',
                }),
            1: WB.add_format({
                'font_name': 'Arial',
                'align': 'right',
                'font_size': 9,
                'border': 1,
                'num_format': num_format,
                'bg_color': '#b4ecac',
                }),
            2: WB.add_format({
                'font_name': 'Arial',
                'align': 'right',
                'font_size': 9,
                'border': 1,
                'num_format': num_format,
                'bg_color': '#74a96d',
                }),
            3: WB.add_format({
                'font_name': 'Arial',
                'align': 'right',
                'font_size': 9,
                'border': 1,
                'num_format': num_format,
                'bg_color': '#4e7449',
                }),
            }
             
        heat = {    
            0: WB.add_format({
                'font_name': 'Arial',
                'align': 'right',
                'font_size': 9,
                'border': 1,
                'num_format': num_format,
                'bg_color': '#ececec',
                }),
            1: WB.add_format({
                'font_name': 'Arial',
                'align': 'right',
                'font_size': 9,
                'border': 1,
                'num_format': num_format,
                'bg_color': '#c8c8c8',
                }),
            2: WB.add_format({
                'font_name': 'Arial',
                'align': 'right',
                'font_size': 9,
                'border': 1,
                'num_format': num_format,
                'bg_color': '#838383',
                }),
            3: WB.add_format({
                'font_name': 'Arial',
                'align': 'right',
                'font_size': 9,
                'border': 1,
                'num_format': num_format,
                'bg_color': '#5f5e5e',
                }),
            }

        # ---------------------------------------------------------------------
        # Format columns:
        # ---------------------------------------------------------------------
        # Column dimension:
        #WS.set_row(0, 30)
            
        # Generate report for export:
        # Header: 
        header = [
            ('Articolo', format_title),
            ('Nostro', format_title),
            ('OC: Pdv', format_title),
            ('FT: Pdv', format_title),
            ('OC: Q.', format_title),
            ('FT: Q.', format_title),
            ('OC: Totale', format_title),
            ('FT: Totale', format_title),
            ('Ordine', format_title),
            ('Fatture', format_title),
            ('Differenza', format_title),
            ]
            
        # Write all header:
        for key, WS in WS_db.iteritems():
            # Column setup:
            WS.set_column('A:B', 20)
            WS.set_column('I:J', 20)
           
            # Column header:
            write_xls_mrp_line(WS, 0, header)
            
        # Body:
        for order in self.browse(cr, uid, ids, context=context):
            for check in order.check_invoice_ids:
                if check.state == 'correct':
                    continue # jump correct line (TODO write in different WS?)
                WS = WS_db[check.state]
                
                # -------------------------------------------------------------
                # Format:
                # -------------------------------------------------------------
                if check.order_price == check.invoice_price:
                    format_price = format_white
                else:    
                    format_price = format_red
                    
                if check.order_qty == check.invoice_qty:
                    format_qty = format_white
                else:    
                    format_qty = format_red
                    
                #if check.order_total == check.invoice_total:
                #    format_total = format_text
                #else:    
                #    format_total = format_red
                
                # Heat map:
                if check.difference >= 0:
                    format_db = cold
                else:
                    format_db = heat                
                difference_abs = abs(check.difference)
                if difference_abs <= 50:
                    format_color = format_db[0]
                elif difference_abs <= 200:
                    format_color = format_db[1]
                elif difference_abs <= 1000:
                    format_color = format_db[2]
                else:
                    format_color = format_db[3]
                
                # -------------------------------------------------------------
                # Record data written:
                # -------------------------------------------------------------
                record = [                
                    (check.article, format_text),
                    (check.name, format_text),
                    (check.order_price, format_price),
                    (check.invoice_price, format_price),
                    (check.order_qty, format_qty),
                    (check.invoice_qty, format_qty),
                    (check.order_total, format_white),
                    (check.invoice_total, format_white),
                    (order.name, format_text),
                    (check.invoice_info, format_text),
                    (check.difference, format_color),
                    ]
                write_xls_mrp_line(WS, counter[check.state], record)
                counter[check.state] += 1

        _logger.info('End export status on %s' % filename)        
        WB.close()

        xlsx_raw = open(filename, 'rb').read()
        b64 = xlsx_raw.encode('base64')

        # ---------------------------------------------------------------------
        # Open attachment form:
        # ---------------------------------------------------------------------
        attachment_id = attachment_pool.create(cr, uid, {
            'name': 'Controllo EDI fatturato',
            'datas_fname': 'edi_invoice_check.xlsx',
            'type': 'binary',
            'datas': b64,
            'partner_id': 1,
            'res_model': 'res.partner',
            'res_id': 1,
            }, context=context)

        return {
            'type': 'ir.actions.act_window',
            'name': 'XLS Controllo EDI fatturato',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': attachment_id,
            'res_model': 'ir.attachment',
            'views': [(False, 'form')],
            'context': context,
            'target': 'current',
            'nodestroy': False,
            }
                    
    _columns = {
        'name': fields.char('Number', size=25, required=True),
        'date': fields.date('Date', readonly=True),
        'has_invoice': fields.boolean('Has invoice'),
        'has_ddt': fields.boolean('Has DDT'),
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
        def change_datetime_gmt(timestamp):
            ''' Change datetime removing gap from now and GMT 0
            '''
            extra_gmt = datetime.now() - datetime.utcnow()
            ts = datetime.strptime(timestamp, DEFAULT_SERVER_DATETIME_FORMAT) 
            return (ts - extra_gmt).strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        
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
                _logger.warning('Root folder %s' % root)
                i = 0
                for f in files:                    
                    i += 1
                    if i % 100 == 0:
                        _logger.warning('Root folder %s files# %s' % (root, i))
                        
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
                    
                    timestamp = f[6:21]
                    
                    timestamp = '%s-%s-%s %s:%s:%s' % (
                        # Date:
                        timestamp[:4],
                        timestamp[4:6],
                        timestamp[6:8],
                        
                        # Time:
                        timestamp[8:10],
                        timestamp[10:12],
                        timestamp[12:14],
                        )
                    # TODO correct hour    
                    #timestamp = change_datetime_gmt(timestamp)
                    
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
                        'datetime': timestamp,
                        'mode': mode,
                        }, context=context)
                break # only base folder XXX maybe parametrize        
        # TODO regenerate order information        
        return True                    

    def load_scheduled_folder_selected(self, cr, uid, load_file=True, 
            generate_line=True, import_invoice=True, import_ddt=True,
            check_invoice=True, check_ddt=True, context=None):
        ''' Load all selected folder
        '''
        order_pool = self.pool.get('edi.order')
        invoice_pool = self.pool.get('edi.invoice.line')
        now = datetime.now()
        
        # ---------------------------------------------------------------------
        # 1. Load order file in all autoload folder:
        # ---------------------------------------------------------------------
        _logger.info('Now: %s Passed [min: %s]' % (
            now, (datetime.now() - now).seconds / 60.0))
            
        if load_file:
            _logger.warning('YES: Load files of order in autoload folder')
            folder_ids = self.search(cr, uid, [
                ('autoload', '=', True),
                ], context=context)
            self.load_file_in_folder(cr, uid, folder_ids, context=context)
        else:    
            _logger.warning('NO: Load files of order in autoload folder')

        # ---------------------------------------------------------------------
        # 2. Generate order line detail from file:
        # ---------------------------------------------------------------------
        _logger.info('Now: %s Passed [min: %s]' % (
            now, (datetime.now() - now).seconds / 60.0))
        order_ids = order_pool.search(cr, uid, [], context=context)
        if generate_line: 
            _logger.warning('YES: Generate order line detail from file')
            order_pool.load_order_line_details(
                cr, uid, order_ids, context=context)
        else:    
            _logger.warning('NO: Generate order line detail from file')

        # ---------------------------------------------------------------------
        # 3. Import invoice:
        # ---------------------------------------------------------------------
        _logger.info('Now: %s Passed [min: %s]' % (
            now, (datetime.now() - now).seconds / 60.0))
        if import_invoice: 
            _logger.warning('YES: Import invoice')
            invoice_pool.import_invoice_line_from_account(
                cr, uid, context=context)
        else:    
            _logger.warning('NO: Import invoice')

        # ---------------------------------------------------------------------
        # 4. Import DDT
        # ---------------------------------------------------------------------
        _logger.info('Now: %s Passed [min: %s]' % (
            now, (datetime.now() - now).seconds / 60.0))
        if import_ddt:
            _logger.warning('YES: Import DDT')
        else:    
            _logger.warning('NO: Import DDT')

        # ---------------------------------------------------------------------
        # 5. Compare line with invoice
        # ---------------------------------------------------------------------
        _logger.info('Now: %s Passed [min: %s]' % (
            now, (datetime.now() - now).seconds / 60.0))
        if check_invoice:
            _logger.warning('YES: Compare line with invoice')
            order_pool.generate_check_database(
                cr, uid, order_ids, mode='invoice', context=context)
        else:    
            _logger.warning('NO: Compare line with invoice')

        # ---------------------------------------------------------------------
        # 6. Compare line with DDT
        # ---------------------------------------------------------------------
        _logger.info('Now: %s Passed [min: %s]' % (
            now, (datetime.now() - now).seconds / 60.0))
        if check_ddt: 
            _logger.warning('YES: Compare line with DDT')
            order_pool.generate_check_database(
                cr, uid, order_ids, mode='ddt', context=context)
        else:    
            _logger.warning('NO: Compare line with DDT')
        
        return True
        
    _columns = {
        'autoload': fields.boolean('Auto load', 
            help='Schedule for auto load operation'),
        'name': fields.char('Name', size=25, required=True),
        'path': fields.char('Path', size=180, required=True),
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
        'datetime': fields.datetime('Datetime',
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
        # Mode fields:
        'invoice_order_id': fields.many2one('edi.order', 'Order invoiced'),
        'ddt_order_id': fields.many2one('edi.order', 'Order DDT'),
        
        'name': fields.char('Company code', size=16),
        'article': fields.char('Customer code', size=16),
            
        'order_qty': fields.float('Order Q.ty', digits=(16, 3)),
        'order_price': fields.float('Order Price', digits=(16, 3)),
        'order_total': fields.float('Order Subtotal', digits=(16, 3)),

        # Used both DDT and invoice values:
        'invoice_qty': fields.float('Q.ty', digits=(16, 3)),
        'invoice_price': fields.float('Price', digits=(16, 3)),
        'invoice_total': fields.float('Subtotal', digits=(16, 3)),
        'difference': fields.float('Difference', digits=(16, 3)),

        'invoice_info': fields.text('Invoice info'),
        'ddt_info': fields.text('DDT info'),

        'state': fields.selection([
            ('correct', 'Correct'),
            ('order', 'Only order'),
            ('invoice', 'Not in order'),
            ('difference', 'Difference'),
            ], 'State'),
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
        'ddt_ids': fields.one2many('edi.ddt.line', 'order_id', 
            'DDT'),
            
        'check_invoice_ids': fields.one2many('edi.order.line.check', 
            'invoice_order_id', 'Check Invoice'),
        'check_ddt_ids': fields.one2many('edi.order.line.check', 
            'ddt_order_id', 'Check DDT'),
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
