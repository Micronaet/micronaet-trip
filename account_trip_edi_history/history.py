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
    _order ='name,line_in,line_out'
    
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
        config_pool = self.pool.get('edi.history.configuration')
        config_ids = config_pool.search(cr, uid, [
            ('code', '=', code)], context=context)
        if not config_ids:    
            return False
        
        config_proxy = config_pool.browse(
            cr, uid, config_ids, context=context)[0]
        input_folder = config_proxy.history_path
        input_invoice = config_proxy.invoice_file
        
        i = -config_proxy.header
        old_order = False
        for invoice in csv.reader(
                open(input_invoice, 'rb'), 
                delimiter=str(config_proxy.delimiter)):
            i += 1
            if i <= 0:
                _logger.info('Jump header lines')
                continue

            # Mapping fields:
            doc_type = invoice[0].strip()
            number = invoice[1].strip()
            order_header = invoice[2].strip()
            article = invoice[3].strip()
            order_detail = invoice[4].strip()
            line = invoice[5].strip()
            
            if not order_header:
                state = 'no_order' # and no history search
            elif order_header != order_detail:
                state = 'order' # difference between line and header
            else:
                state = 'ok'
            
            self.create(cr, uid, {
                'name': order_header, # to search in history
                'name_detail': order_detail,
                'line_in': line, # TODO load from history
                'line_out': line,
                'product_code_in': article, # TODO load from history
                'product_code_out': article,
                'document_out': number,
                'document_type': doc_type,
                'state': state,                
                }, context=context)
        return True
    
    _columns = {
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
            ('only_in', 'Not imported'),
            ('only_out', 'Extra line'),
            ('article', 'Article error'),
            ('ok', 'Correct'),
            ], 'State', help='Error state'),            
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
