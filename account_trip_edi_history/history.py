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
        'modified': fields.boolean('Modified'),
        'file': fields.text('File', help='File list for check the order'), 
        'total': fields.integer('Total', help='Total of file for this order'), 
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
        'quantity_precision': fields.float('Quantity precision', digits=(16, 2)),     
        'price_precision': fields.float('Price precision', digits=(16, 2)),     
        }
        
    # TODO set unique key for name    
    _defaults = {
        'active': lambda *x: True,
        'delimiter': lambda *x: ';',
        'header': lambda *x: 0,        
        'verbose': lambda *x: 100,    
        'quantity_precision': lambda *x: 0.01,    
        'price_precision': lambda *x: 0.01,    
        }    

class EdiHistoryCheck(osv.osv):
    ''' Manage path for all company EDI that has active routes
    '''
    
    _name = 'edi.history.check'
    _description = 'EDI history check'
    _order = 'name,sequence,line_out,line_in'
    
    # ----------------------------
    # Button and utility function:
    # ----------------------------
    def button_header_out(self, cr, uid, ids, context=None):
        return self.get_order_out(cr, uid, ids, 'header', context=context)

    def button_detail_out(self, cr, uid, ids, context=None):
        return self.get_order_out(cr, uid, ids, 'detail', context=context)
                
    def button_document_out(self, cr, uid, ids, context=None):
        return self.get_order_in(cr, uid, ids, 'account', context=context)

    def get_order_out(self, cr, uid, ids, button_mode='header', context=None):
        ''' Open view for see all order OUT
            button_mode for choose the type of filter: 
                'header', 'detail', 'account'
        '''
        if context is None:
            context = {}

        order_proxy = self.browse(cr, uid, ids, context=context)[0]
        
        button_mode = context.get('button_mode', 'header')
        if button_mode == 'header':
            domain = [('name', '=', order_proxy.name)]
        elif button_mode == 'detail':   
            domain = [('name', '=', order_proxy.name_detail)]
        else:    
            domain = [('document_out', '=', order_proxy.document_out)]

        return {
            'res_model': 'edi.history.check',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'view_type': 'form',
            'view_mode': 'tree,form',
            #'res_id': context.get('active_id', False),
            'context': {'search_default_order_state_urgent_grouped': False},
            'domain': domain, 
            }

    def button_header_in(self, cr, uid, ids, context=None):
        return self.get_order_in(cr, uid, ids, 'header', context=context)

    def button_detail_in(self, cr, uid, ids, context=None):
        return self.get_order_in(cr, uid, ids, 'detail', context=context)

        
    def get_order_in(self, cr, uid, ids, button_mode='header', context=None):
        ''' Open view for see all order IN
            context for pass button_mode: 'header' (def.), 'detail'
        '''
        if context is None:
            context = {}

        # Search header or detail order code
        order_proxy = self.browse(cr, uid, ids, context=context)[0]
        order_pool = self.pool.get('edi.history.order')
        
        button_mode = context.get('button_mode', 'header')
        if button_mode == 'header':
            order = _('Order header IN: %s') % order_proxy.name
            domain = [('name', '=', order_proxy.name)]
        else:
            order = _('Order detail IN: %s') % order_proxy.name_detail
            domain = [('name_detail', '=', order_proxy.name_detail)]

        order_ids = order_pool.search(cr, uid, domain, context=context)
        if order_ids:            
            return {
                'res_model': 'edi.history.order',
                'type': 'ir.actions.act_window',
                'target': 'new',
                'view_type': 'form',
                'view_mode': 'form',
                'res_id': order_ids[0],
                'context': {
                    'search_default_order_state_urgent_grouped': False},
                'domain': [('name', '=', order_ids[0])], 
                }

        raise osv.except_osv(
            _('Error!'), 
            _('Order not found in archive: %s' % order),
            )
        
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
        def remove_from_list(order_in_check, order, line):
            ''' Remove without error
            '''
            try: 
                order_in_check.remove((order, line_out)) # error if not present
            except:
                pass # no problem on error
            return
            
        def sort_sequence(filelist):
            ''' Internal utility for sort list get priority to orders and
                then to ordchg after to normal order
            '''
            # TODO add some controls (need to be right)
            
            # Split in 2 list the element depend on type:
            if len(filelist) in (0, 1): # 0 raise error?
                return filelist
                
            orders = sorted([
                filename for filename in filelist if 'ORDERS' in filename])
            if len(orders) > 1:
                _logger.error('More than one ORDERS file %s' % orders )    
                # TODO what to do now?

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
            
            if order in order_record: # pass only the first time
                return 

            modified = False            
            order_record[order] = {}

            sort_history_filename = sort_sequence(
                history_filename.get(order, []))
            for filename in sort_history_filename:
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
                    
                    if (order, line_in) not in order_in_check: # for modify!
                        order_in_check.append(
                            (order, line_in)) # add key for test A - B 
                    
            # Save file for create a HTML order more readable:                          
            if order: # jump empty
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
                            # Filename (base name extract from full path:
                            os.path.basename(order_record[order][line_in][4]),                             
                            order_record[order][line_in][5], # Create date
                            order_record[order][line_in][6], # Modifty date
                            )
                order_html += '</table>'    
                            
                order_pool = self.pool.get('edi.history.order')
                order_ids = order_pool.search(cr, uid, [
                    ('name', '=', order)], context=context)
                # Create file list:
                file_list = ""
                for f in sort_history_filename:
                    file_list += "%s\n" % os.path.basename(f)
                if order_ids: 
                    order_id = order_ids[0]    
                    order_pool.write(cr, uid, order_id, {
                        'note': order_html,
                        'modified': modified,
                        'file': file_list, 
                        'total': len(sort_history_filename),
                        }, context=context)    
                else:
                    order_id = order_pool.create(cr, uid, {
                        'name': order,
                        'modified': modified,
                        'note': order_html,
                        'file': file_list,
                        'total': len(sort_history_filename),
                        }, context=context)    
                         
            return # TODO order_id?
            
        # ---------------------------------------------------------------------
        #        Start procedure and get configuration parameters
        # ---------------------------------------------------------------------
        _logger.info('Start import history order for check')
        
        # --------------------------
        # Read configuration record:
        # --------------------------
        # Read record for code passed in scheduling:
        config_pool = self.pool.get('edi.history.configuration')
        config_ids = config_pool.search(cr, uid, [
            ('code', '=', code)], context=context)
        if not config_ids:    
            _logger.error('Code %s not found in configuration file!' % code)
            return False
        config_proxy = config_pool.browse(
            cr, uid, config_ids, context=context)[0]
            
        # Folder path:    
        input_folder = config_proxy.history_path # history order
        input_invoice = config_proxy.invoice_file # account invoice
        
        # Precision for price / quantity evaluation
        quant_prec = config_proxy.quantity_precision
        price_prec = config_proxy.price_precision

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
                row = f.read()
                f.close()
                order = row[19:29].strip()
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
        order_out_check = [] # List of order-row for check duplication
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
                'sequence': sequence, # for sort as account (check seq. err.)
                'name': order, # to search in history
                'name_detail': order_detail,
                'line_in': False,
                'line_out': line_out,
                'quantity_in': False,
                'quantity_out': quantity,
                'price_in': False,
                'price_out': price,                
                'product_code_in': False,
                'product_parent_in': False,
                'product_code_out': article,
                'product_parent_out': article[:3],
                'document_out': number,
                'document_type': doc_type,
                }

            # -------------------------------
            # STATE MANAGE: Speed check case:
            # -------------------------------
            if not order:
                date['name'] = _('NOT FOUND!')
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
            if (order, line_out) in order_out_check:
                # if duplicated was yet removed from order_in_check
                date['state'] = 'duplicated'
                self.create(cr, uid, date, context=context)
                continue # Jump line

            order_out_check.append((order, line_out)) # used for check dupl.

            # -----------------------------
            # STATE MANAGE: Sequence error:
            # -----------------------------
            wrong_sequence = False
            # Note: sequence is evaluated here for "old" counter but,
            # if present, the write operation is done after wrong_line & only 
            # out, this because are more important than sequence error
            if old_order == order:
                if old_line and line_out < old_line:
                    old_line = line_out
                    date['state'] = 'sequence'
                    wrong_sequence = True 
                else:
                    old_line = line_out # No error, save this as old
            else: # If change order reset line:
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


            # Remove here line for only_in test (so out removed from in)
            remove_from_list(order_in_check, order, line_out) 
            
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
            
            # ----------------------------
            # CORRECT RECORD: Save article
            # ----------------------------
            # Note: line_in now are equals to line_out!
            date['line_in'] = line_out # must to be here (after all)
            self.create(cr, uid, date, context=context)
        
        # Write line present in IN and not in OUT:
        # Note: must be before mark order evaluation!
        order_yet_found = []
        for (order, line_in) in order_in_check:
            if order not in order_record:
                _logger.error(
                    'Order %s with in line not found not present!' % order)
                continue    

            order_in = order_record[order] # yet loaded master loop        
            # Create line for order in without order out fields:
            date = {
                'sequence': 0, # first line not prest in order out
                'name': order,
                'name_detail': False,
                'line_in': line_in, # Use line_out
                'line_out': False,
                'quantity_in': order_in[line_in][2],
                'quantity_out': False,
                'price_in': order_in[line_in][3],
                'price_out': False,                
                'product_code_in': order_in[line_in][0],
                'product_parent_in': order_in[line_in][0][:3],
                'product_code_out': False,
                'product_parent_out': False,
                'document_out': False,
                'document_type': False,
                'state': 'only_in',
                }
            self.create(cr, uid, date, context=context)
            if order not in order_yet_found: # write only once
                _logger.warning('Order with only_in case: %s' % order)
                order_yet_found.append(order)

        # -------------------------------------------
        # Update field for show all order with errors
        # -------------------------------------------
        # Mark all order as error where there's almost one line (after all!)
        
        # NOTE: Splitted in two, maybe for precedence problems
        _logger.info('Mark all order error if has line problem:')
                
        line_ko_ids = self.search(cr, uid, [ # Line with problems
            ('state', '!=', 'ok'), # OK
            ('state', '!=', 'quantity'), # No order error if quantity
            ], context=context)            

        order_ko_list = [ # Order code list:    
            item.name for item in self.browse(
                cr, uid, line_ko_ids, context=context)]
                
        order_ko_ids = self.search(cr, uid, [ # All order lines:    
            ('name', 'in', order_ko_list), ], context=context)
        
        self.write(cr, uid, order_ko_ids, { # Upd. field for search whole order
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

        # 3 char of product    
        'product_parent_in': fields.char('Product parent in', size=3, 
            help='Order product parent out (first 3 char)'),
        'product_parent_out': fields.char('Product parent out', size=3, 
            help='Order product parent in (first 3 char)'),

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
