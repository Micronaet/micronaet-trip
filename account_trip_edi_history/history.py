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
from openerp.osv import osv, orm, fields
from datetime import datetime, timedelta
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, DATETIME_FORMATS_MAP, float_compare)
import openerp.addons.decimal_precision as dp
from openerp.tools.translate import _
import pickle


_logger = logging.getLogger(__name__)

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
            code: edi.company.importation for force 
            delimiter
            context: parameter arguments passed
        '''
        # TODO code will be list if used in other company
        
        def load_order_from_history(order, history_list, order_files):
            ''' Function that load all files and create a dictionary with row
                key
            '''
            if order not in order_files:
                order_files[order] = {}
            for filename in history_list.get(order, []):
                # Read all files and update dict with row record:
                f = open(filename)
                for row in f:
                    file_type = row[10:16] # ORDERS or ORDCHG
                    update_type = row[16:19] # 003 ann, 001 mod. q.
                    line = row[2337:2342] # 5
                    article = row[2357:2368] # 11
 
                    if file_type == 'ORDERS':
                        line_type = 'original'
                    else: # ORDCHG
                        if update_type == '001':
                            line_type = 'update' 
                        elif update_type == '003':    
                            line_type = 'cancel'
                        else: # operation non in list
                            _logger.error(
                                'Update code not found: %s' % update_type)
                            line_type = 'error'                    
                    order_files[order][line] = (article, line_type)
            return
            
        # -----------------------------
        # Get configuration parameters:
        # -----------------------------
        config_pool = self.pool.get('edi.history.configuration')
        config_ids = config_pool.search(cr, uid, [
            ('code', '=', code)], context=context)
        if not config_ids:    
            return False
        config_proxy = config_pool.browse(
            cr, uid, config_ids, context=context)[0]
        input_folder = config_proxy.history_path
        input_invoice = config_proxy.invoice_file

        # ---------------
        # Clean database:
        # ---------------
        remove_ids = self.search(cr, uid, [], context=context)
        self.unlink(cr, uid, remove_ids, context=context)

        # -------------------
        # Read files history:
        # -------------------
        # Save in dict for future access
        history_files = {} # list of file (key=order, value=filename)
        order_files = {} # record in file (key=order, value {row: (art, state)}
        for root, directories, files in os.walk(input_folder):
            for filename in files:                
                filepath = os.path.join(root, filename)
                f = open(filepath, 'rb')
                line = f.read()
                f.close()
                order = line[19:29]
                if order not in history_files:
                    history_files[order] = []
                #os.path.getmtime(filepath)
                history_files[order].append(filepath)

        # ---------------------
        # Start import invoice:
        # ---------------------
        # Read all lines and save only duplicated
        invoice_row = {}
        i = -config_proxy.header
        sequence = 0
        
        old_order = False
        old_line = False
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
            line = invoice[5].strip()
            
            # Load order if not present in database:
            if order not in order_files:
                load_order_from_history(
                    order, history_files, order_files)
            
            date = {
                'sequence': sequence, # import order
                'name': order, # to search in history
                'name_detail': order_detail,
                'line_in': False, # TODO load from history
                'line_out': line,
                'product_code_in': False, # TODO load from history
                'product_code_out': article,
                'document_out': number,
                'document_type': doc_type,
                }

            # -----------------------------------------------------------------
            #                         State manage
            # -----------------------------------------------------------------

            # -----------
            # Rapid case:
            # -----------
            if not order:
                date['state'] = 'no_order'
                self.create(cr, uid, date, context=context)
                continue
            elif order != order_detail:
                date['state'] = 'order'
            else:
                date['state'] = 'ok'
            
            # ---------------
            # Duplicated row:
            # ---------------
            if order not in invoice_row:
                invoice_row[order] = {}
            
            if line in invoice_row[order]:
                date['state'] = 'duplicated'
                self.create(cr, uid, date, context=context)
                continue # Jump line

            # --------------
            # Sequence error
            # --------------
            if old_order == order:
                if old_line and line < old_line:
                    old_line = line
                    date['state'] = 'sequence'
                    self.create(cr, uid, date, context=context)
                    continue                    
                else:
                    old_line = line
            else:
                # If change order reset line:
                old_order = order
                old_line = line # first line of order


            # ------------
            # Save article
            # ------------
            invoice_row[order][line] = (
                self.create(cr, uid, date, context=context),
                article, 
                ) # ID, Article

        return True
    
    _columns = {
        'sequence': fields.integer('Sequence'),
        'name': fields.char('Order name', size=25, 
            help='Order ID of company'),
        'name_detail': fields.char('Order detail', size=25, 
            help='Order ID in accounting detail'),
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
            ('BC', 'Document of transport'),
            ('FT', 'Invoice'),
            ], 'Document type', help='Document out type'),
        'state': fields.selection([
            ('no_order', 'Order not present'),
            ('order', 'Order dont\'t match'),
            ('sequence', 'Sequence error'),
            ('duplicated', 'Row duplicated'),
            ('only_in', 'Not imported'),
            ('only_out', 'Extra line'),
            ('article', 'Article error'),
            ('ok', 'Correct'),
            ], 'State', help='Error state'),            
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
