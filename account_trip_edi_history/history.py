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
import netsvc
import logging
import csv
import time
from openerp.osv import osv, orm, fields
from datetime import datetime, timedelta
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, DATETIME_FORMATS_MAP, float_compare)
import openerp.addons.decimal_precision as dp
from openerp.tools.translate import _
import pickle


_logger = logging.getLogger(__name__)

class EdiHistoryOrder(osv.osv):
    ''' EDI original order (result of creation and change recurred)
    '''
    _name = 'edi.history.order'
    _description = 'EDI history order'
    
    _columns = {
        'name': fields.char('Order #', size=30, required=True),
        'note': fields.text('Result'), # HTML format
        'modified': fields.boolean('Modified')
        }
    
    _defaults = {
        'modified': lambda *x: False,
        }    
        

class EdiHistoryConfiguration(osv.osv):
    ''' Manage path for all company EDI that has active routes
    '''
    _name = 'edi.history.configuration'
    _description = 'EDI history configuration'
    
    _columns = {
        'name': fields.many2one('edi.company.importation', 
            'EDI company', required=True),
        'code': fields.related('name', 'code', 
            type='char', size=10, string='Code', store=True), 
        'active': fields.boolean('Active'),
        'header': fields.integer('Header lines'),
        'delimiter': fields.char('Delimiter'),     
        'verbose': fields.integer('Verbose every', 
            help='Log an import event every X lines (0 = nothing)'),     
        'history_path': fields.char('History path', size=100, 
            help='Path of history files, use also like: "~/company/history"'),
            
        # TODO: maybe use invoice path if more than one file, else the file:    
        'invoice_path': fields.char('Invoice path', size=100, 
            help='Path of history files, use also like: "~/company/history"'),
        'invoice_file': fields.char('Invoice path', size=100, 
            help='Path of invoice file, use: "~/company/account/invoice.csv"'),
        }
        
    # TODO set unique key for name    
    _defaults = {
        'active': lambda *x: True,
        'delimiter': lambda *x: ';',
        'header': lambda *x: 0,        
        'verbose': lambda *x: 100,    
        }    

class EdiHistoryCheck(osv.osv):
    ''' Manage path for all company EDI that has active routes
    '''
    
    _name = 'edi.history.check'
    _description = 'EDI history check'
    _order = 'sequence,name,line_in,line_out'
    

    # -------------------------------------------------------------------------
    #                             Scheduled action
    # -------------------------------------------------------------------------
    def import_invoce_check(self, cr, uid, code, context=None):
        ''' Import procedure for check if order are correctly imported and 
            match with invoice / delivery document in account
            self: instance object
            cr: cursor for database
            uid: user ID
            context: parameter arguments passed
        '''
        # TODO code will be list if used in other company

        # ---------------------------------------------------------------------
        #                            Utility function
        # ---------------------------------------------------------------------
        def get_in_sequence(filelist):
            ''' Internal utility for sort list get priority to orders and
                then to ordchg after to normal order
            '''
            # TODO add some controls (need to be right)
            # Split in 2 list the element depend on type:
            if len(filelist) in (0, 1): # 0 raise error?
                return filelist
                
            import pdb; pdb.set_trace()        
            orders = sorted([
                filename for filename in filelist if 'ORDERS' in filename])
                
            ordchg = sorted([
                filename for filename in filelist if 'ORDCHG' in filename])
            
            # order and merge as is:    
            orders.extend(ordchg)
            return orders
            
        def load_order_from_history(order, history_filename, order_record, 
                order_in_check):
            ''' Function that load all files and create a dictionary with row
                key
                The function also save in database the order for a readable 
                check in.
                
                order: order code origin
                history_filename: database of filename (list for every order)
                order_record: dict with order line imported from history files
                order_in_check: list of all record (for set order_in attribute)
            '''     
            # Function utility:
                
            to_save = False
            modified = False

            if order == '4506021944': 
                import pdb; pdb.set_trace()

            if order not in order_record:
                order_record[order] = {}
                to_save = True # After all write order for history in OpenERP

            order_history_filename = get_in_sequence(
                history_filename.get(order, []))
            for filename in order_history_filename:
                # Read all files and update dict with row record:
                f = open(filename)
                m_time = time.ctime(os.path.getmtime(filename))
                c_time = time.ctime(os.path.getctime(filename))
                for row in f:
                    file_type = row[10:16] # ORDERS or ORDCHG
                    update_type = row[16:19] # 003 ann, 001 mod. q.
                    line_in = row[2336:2341] # 5
                    article = row[2356:2367].strip() # 11
                    quantity = float(row[2631:2641].strip() or '0')
                    price = float(row[2964:2994].strip() or '0')

                    if file_type == 'ORDERS':
                        line_type = 'original'
                    else: # ORDCHG
                        modified = True
                        if update_type == '001':
                            line_type = 'update' 
                        elif update_type == '003':    
                            line_type = 'cancel'
                        else: # operation non in list
                            _logger.error(
                                'Update code not found: %s' % update_type)
                            line_type = 'error'                    
                    order_record[order][line_in] = (
                        # For check with account information:
                        article, line_type, quantity, price, 
                        # For history record file in database:
                        filename, c_time, m_time)
                    order_in_check.append((order, line_in)) # add key for test  
                    
            # Save file for create a HTML order more readable:                          
            if to_save and order: # jump empty
                order_html = _('''
                    <style>
                        .table_bf {
                             border: 1px solid black;
                             padding: 3px;
                             }                             
                        .table_bf td {
                             border: 1px solid black;
                             padding: 3px;
                             text-align: center;
                             }
                        .table_bf_wo td {
                             border: 1px solid black;
                             padding: 3px;
                             text-align: center;
                             background-color: AntiqueWhite;
                             text-decoration: line-through;
                             }                             
                        .table_bf_upd td {
                             border: 1px solid black;
                             padding: 3px;
                             text-align: center;
                             background-color: Gainsboro;
                             }                             
                        .table_bf th {
                             border: 1px solid black;
                             padding: 3px;
                             text-align: center;
                             background-color: grey;
                             color: white;
                             }
                    </style>

                    <table class='table_bf'>
                        <tr class='table_bf'>
                            <th>Line</th><th>Article</th><th>Quant.</th>
                            <th>Price</th><th>File</th><th>Create</th>
                            <th>Mod.</th>
                        </tr>''')
                
                for line_in in sorted(order_record[order].keys()):
                    # Chose color line with class:
                    if order_record[order][line_in][1] == 'cancel':
                        row_class = 'class="table_bf_wo"'
                    elif order_record[order][line_in][1] == 'update':
                        row_class = 'class="table_bf_upd"'
                    else:
                        row_class = ''    
                    
                    order_html += '''
                        <tr %s>
                            <td>%s</td><td>%s</td><td>%s</td>
                            <td class='{text-align: right;}'>%s</td>
                            <td class='{text-align: right;}'>%s</td>
                            <td>%s</td><td>%s</td>
                        </tr>
                        ''' % (
                            row_class, # Cancel state
                            line_in, # Row
                            order_record[order][line_in][0], # Article
                            order_record[order][line_in][2], # Quant.
                            order_record[order][line_in][3], # Price
                            order_record[order][line_in][4], # Filename
                            order_record[order][line_in][5], # Create date
                            order_record[order][line_in][6], # Modifty date
                            )
                order_html += '</table>'    
                            
                order_pool = self.pool.get('edi.history.order')
                order_ids = order_pool.search(cr, uid, [
                    ('name', '=', order)], context=context)
                if order_ids: 
                    order_id = order_ids[0]    
                    order_pool.write(cr, uid, order_id, {
                        'note': order_html,
                        'modified': modified,
                        }, context=context)    
                else:
                    order_id = order_pool.create(cr, uid, {
                        'name': order,
                        'modified': modified,
                        'note': order_html,
                        }, context=context)    
                         
            return # TODO order_id?
            
        # ---------------------------------------------------------------------
        #        Start procedure and get configuration parameters
        # ---------------------------------------------------------------------
        _logger.info('Start import history order for check')
        
        # Read configuration record:
        config_pool = self.pool.get('edi.history.configuration')
        config_ids = config_pool.search(cr, uid, [
            ('code', '=', code)], context=context)
        if not config_ids:    
            return False
        config_proxy = config_pool.browse(
            cr, uid, config_ids, context=context)[0]
        input_folder = config_proxy.history_path # history order
        input_invoice = config_proxy.invoice_file # account invoice
        
        # Precision for price / quantiyi evaluation
        price_prec = 0.01 # TODO put in configuration?
        quant_prec = 0.01

        # ---------------
        # Clean database:
        # ---------------
        remove_ids = self.search(cr, uid, [], context=context)
        self.unlink(cr, uid, remove_ids, context=context)

        # -------------------
        # Read files history:
        # -------------------
        # Save in dict for future access (that parse whole order and modify)
        history_filename = {} # list of file (key=order, value=filename)
        order_record = {} # record in file (k order, v {row: (art, state)}
        order_in_check = []
        for root, directories, files in os.walk(input_folder):
            for filename in files:                
                filepath = os.path.join(root, filename)
                f = open(filepath, 'rb')
                line_in = f.read()
                f.close()
                order = line_in[19:29].strip()
                if not order:
                    _logger.error(
                        'Found order without name (jump): %s' % filename)
                    continue
                if order not in history_filename:
                    history_filename[order] = [] # Create empty list
                #os.path.getmtime(filepath) # TODO for evaluation order prior.
                history_filename[order].append(filepath)

        # ---------------------
        # Start import invoice:
        # ---------------------
        # Read all lines and save only duplicated
        invoice_row = {} # List of order-row for check duplication
        i = -config_proxy.header
        sequence = 0
        
        old_order = False
        old_line = False
        # TODO problem with order (not sorted with invoice/ddt)
        for invoice in csv.reader(
                open(input_invoice, 'rb'), 
                delimiter=str(config_proxy.delimiter)):
            i += 1
            sequence += 1
            if i <= 0:
                _logger.info('Jump header lines')
                continue

            # Mapping fields:
            doc_type = invoice[0].strip()
            number = invoice[1].strip()
            order = invoice[2].strip() # header
            article = invoice[3].strip()
            order_detail = invoice[4].strip()
            line_out = invoice[5].strip()            
            quantity = float(invoice[6].strip().replace(',', '.') or '0')
            price = float(invoice[7].strip().replace(',', '.') or '0')
            # TODO check alias article for get correct element
            
            # Load order if not present in database:
            if order not in order_record:
                load_order_from_history(
                    order, history_filename, order_record, order_in_check)
            
            date = {
                'sequence': sequence, # import sequence (for read line error)
                'name': order, # to search in history
                'name_detail': order_detail,
                'line_in': False, # TODO write when read
                'line_out': line_out,
                'quantity_in': False,
                'quantity_out': quantity,
                'price_in': False,
                'price_out': price,                
                'product_code_in': False,
                'product_code_out': article,
                'document_out': number,
                'document_type': doc_type,
                }

            # -------------------------------
            # STATE MANAGE: Speed check case:
            # -------------------------------
            if not order:
                date['state'] = 'no_order'
                self.create(cr, uid, date, context=context)
                continue
            elif order != order_detail:
                date['state'] = 'order'
                self.create(cr, uid, date, context=context)
                continue
            else:
                date['state'] = 'ok' # temporary OK after account check
            
            # -----------------------------
            # STATE MANAGE: Duplicated row:
            # -----------------------------
            if order not in invoice_row:
                invoice_row[order] = {}    
                        
            if line_out in invoice_row[order]:
                date['state'] = 'duplicated'
                self.create(cr, uid, date, context=context)
                continue # Jump line

            # -----------------------------
            # STATE MANAGE: Sequence error:
            # -----------------------------
            wrong_sequence = False
            # Note: sequence is evaluated here for old counter but, if present,
            # Write operation is done after wrong_line & only out, this because
            # are more important than sequence error
            if old_order == order:
                if old_line and line_out < old_line:
                    old_line = line_out
                    date['state'] = 'sequence'
                    wrong_sequence = True 
                else:
                    old_line = line_out
            else:
                # If change order reset line:
                old_order = order
                old_line = line_out # first line of order

            # ---------------------------------------------------
            # HISTORY ANALYSIS: Wrong line (not present in order)
            # ---------------------------------------------------
            # NOTE: More important than sequence!!
            if line_out not in order_record[order]: # (article, line_type)
                date['state'] = 'wrong_line' # not presen in order
                self.create(cr, uid, date, context=context)
                continue # Jump line

            # ---------------------------------------------------------------
            # HISTORY ANALYSIS: Line removed (present in order but cancelled)
            # ---------------------------------------------------------------
            if order_record[order][line_out][1] == 'cancel':
                date['state'] = 'only_out' # present but deleted in order
                self.create(cr, uid, date, context=context)
                continue # Jump line

            # Note: Here we write wrong sequence, before valuated, if present:
            if wrong_sequence:
                self.create(cr, uid, date, context=context)
                continue


            # key: order-line now exist so remove for order_in test:
            try:
                order_in_check.remove((order, line_out))
            except:
                pass # no problem on error
            
            # ------------------------------------------
            # HISTORY ANALYSIS: Test article is the same
            # ------------------------------------------
            date['product_code_in'] = order_record[order][line_out][0]
            if order_record[order][line_out][0] != article[:11]:
                date['line_in'] = line_out
                date['state'] = 'article'
                self.create(cr, uid, date, context=context)
                continue # Jump line
                
            # -------------------------------------------
            # HISTORY ANALYSIS: Test quantity is the same
            # -------------------------------------------
            date['quantity_in'] = order_record[order][line_out][2] # 3 element
            if abs(date['quantity_in'] - quantity) > quant_prec:
                date['line_in'] = line_out
                date['state'] = 'quantity'
                self.create(cr, uid, date, context=context)
                continue # Jump line

            # ----------------------------------------
            # HISTORY ANALYSIS: Test price is the same
            # ----------------------------------------
            date['price_in'] = order_record[order][line_out][3] # 4 element
            if abs(date['price_in'] - price) > price_prec:
                date['line_in'] = line_out
                date['state'] = 'price'
                self.create(cr, uid, date, context=context)
                continue # Jump line
            
            # Write only_in for remain lines not tested
            #for (order, line_out) in order_in_check:
            #    # Create record with left values:
            #    # TODO 
            #    pass
            
            # ----------------------------
            # CORRECT RECORD: Save article
            # ----------------------------
            date['line_in'] = line_out # TODO check after all: write line in, now are equals!
            invoice_row[order][line_out] = (
                self.create(cr, uid, date, context=context),
                article, 
                ) # ID, Article

        # -------------------------------------------
        # Update field for show all order with errors
        # -------------------------------------------
        # NOTE: Splitted in two, maybe for precedence problems
        _logger.info('Mark order with problem:')
        # Line with problems
        line_ko_ids = self.search(cr, uid, [
            ('state', '!=', 'ok'), ], context=context)
            
        # Order code list:    
        order_ko_list = [
            item.name for item in self.browse(
                cr, uid, line_ko_ids, context=context)]
        
        # All order lines:    
        order_ko_ids = self.search(cr, uid, [
            ('name', 'in', order_ko_list), ], context=context)
        
        # Update filed for search whole order:    
        self.write(cr, uid, order_ko_ids, {
            'order_error': True
            }, context=context)

        return True
    
    _columns = {
        'sequence': fields.integer('Sequence'),

        'name': fields.char('Order name', size=25, 
            help='Order ID of company'),
        'name_detail': fields.char('Order detail', size=25, 
            help='Order ID in accounting detail'),

        'price_in': fields.float('Price in', digits=(16, 2)), 
        'price_out': fields.float('Price out', digits=(16, 2)), 

        'quantity_in': fields.float('Quantity in', digits=(16, 2)), 
        'quantity_out': fields.float('Quantity out', digits=(16, 2)), 

        'line_in': fields.char('Line in', size=5, help='Order line'),
        'line_out': fields.char('Line out', size=5, 
            help='Delivery of invoice line'),

        'product_code_in': fields.char('Product in', size=18, 
            help='Order product in'),
        'product_code_out': fields.char('Product out', size=18, 
            help='Invoice or delivery product out'),

        'document_out': fields.char('Document out', size=20,
            help='Number of document, delivery or invoice, out'),
        'document_type': fields.selection([
            ('OC', 'Order'),
            ('BC', 'Document of transport'),
            ('FT', 'Invoice'),
            ], 'Document type', help='Document out type'),

        'order_error': fields.boolean('Order error', 
            help='As if the line is correct in order there\'s almost one line'
                'with error'),

        'state': fields.selection([
            # First control, readind account file:
            ('no_order', 'Order not present'),
            ('order', 'Order doesn\'t match'),
            ('sequence', 'Sequence error'),
            ('duplicated', 'Row duplicated'),
            
            # Control reading history:
            ('only_in', 'Not imported'), # not present in accounting
            ('only_out', 'Extra line'), # only out (order was cancel)
            ('wrong_line', 'Wrong line'), # not present in order
            ('article', 'Article error'),
            ('quantity', 'Quantity error'), # TODO Manage
            ('price', 'Price error'), # TODO 
            ('unmanaged', 'Error unmanaged'),
            
            # If all correct:
            ('ok', 'Correct'),
            ], 'State', help='Error state'),            
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
