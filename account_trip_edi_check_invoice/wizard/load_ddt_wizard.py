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


class EdiLoadDdtLineWizard(orm.TransientModel):
    ''' Wizard for load DDT report
    '''
    _name = 'edi.load.ddt.line.wizard'

    # --------------------
    # Wizard button event:
    # --------------------
    def action_reload(self, cr, uid, ids, context=None):
        ''' Reload DDT file 
            Update Order touched
        '''
        if context is None: 
            context = {}        
        
        # Launch opeation scheduled for reimport DDT (previous exported)
        folder_pool = self.pool.get('edi.order.folder')
        _logger.info('Reimport DDT and check lines')
        return folder_pool.load_scheduled_folder_selected(cr, uid, load_file=False, 
            generate_line=False, import_invoice=False, import_ddt=True,
            context=context)
    
    def action_export_report(self, cr, uid, ids, context=None):
        ''' Extract DDT report with parameters
        '''
        _logger.info('Start export order VS DDT')
        tollerance = 0.0001

        if context is None: 
            context = {}
        
        # Pool used:
        excel_pool = self.pool.get('excel.writer')
        order_pool = self.pool.get('edi.order')
        ddt_line_pool = self.pool.get('edi.ddt.line')

        # ---------------------------------------------------------------------
        # Parameters and domain filter:
        # ---------------------------------------------------------------------
        wiz_proxy = self.browse(cr, uid, ids, context=context)[0]        
        
        mode = wiz_proxy.mode
        
        domain = [('has_ddt', '=', True)]
        domain_text = _('Order VS DDT (%s)') % mode
            
        # DDT filter:    
        domain_ddt = []
        if wiz_proxy.from_date:
            domain_ddt.append(
                ('ddt_id.date', '>=', wiz_proxy.from_date))
            domain_text += _(' - Dalla date DDT %s') % excel_pool.format_date(
                wiz_proxy.from_date)
        if wiz_proxy.to_date:
            domain_ddt.append(
                ('ddt_id.date', '<=', wiz_proxy.from_date))
            domain_text += _(' - Alla data DDT %s') % excel_pool.format_date(
                wiz_proxy.to_date)
        if domain_ddt:
            ddt_ids = ddt_line_pool.search(
                cr, uid, domain_ddt, context=context)
            find_order_ids = [
                line.order_id.id for line in ddt_line_pool.browse(
                    cr, uid, ddt_ids, context=context)]
            domain.append(('id', 'in', tuple(set(find_order_ids))))
        
        # ---------------------------------------------------------------------
        # Create XSXL file:
        # ---------------------------------------------------------------------        
        ws_name = _('Order')
        row = 0
        
        excel_pool.create_worksheet(ws_name)
        
        # ---------------------------------------------------------------------
        # Format elements:
        # ---------------------------------------------------------------------
        excel_pool.set_format()
        
        f_title = excel_pool.get_format('title')
        f_header = excel_pool.get_format('header')
        
        f_text = excel_pool.get_format('text')        

        # Color setup:
        f_bg_white = excel_pool.get_format('bg_white')
        f_bg_red = excel_pool.get_format('bg_red')
        f_bg_green = excel_pool.get_format('bg_green')
        f_bg_yellow = excel_pool.get_format('bg_yellow')
        f_bg_blue = excel_pool.get_format('bg_blue')

        f_bg_white_number = excel_pool.get_format('bg_white_number')
        f_bg_red_number = excel_pool.get_format('bg_red_number')
        f_bg_green_number = excel_pool.get_format('bg_green_number')
        f_bg_yellow_number = excel_pool.get_format('bg_yellow_number')
        f_bg_blue_number = excel_pool.get_format('bg_blue_number')
        
        f_number = excel_pool.get_format('number')
        
        # ---------------------------------------------------------------------
        # Write title and header:
        # ---------------------------------------------------------------------
        # Title:
        excel_pool.write_xls_line(ws_name, row, [
            _('Filter:'), 
            domain_text,
            ], default_format=f_title)
        
        # Header:
        row += 2
        if mode == 'ddt':
            excel_pool.column_width(ws_name, [22, 22, 35, 10])
            header = [
                _('DDT'),
                _('Ordine'),
                _('Data'),
                _('Differenza'),
                ]
        else:
            excel_pool.column_width(ws_name, [
                22, 22, 
                20, 20,
                10, 10, 10, 10, 10, 10, 10,             
                ])

            header = [
                _('DDT'),
                _('Ordine'),
                _('Ns Codice'),
                _('Vs Codice'),
                _('OC: Pdv'),
                _('DDT: Pdv'),
                _('OC: Q.'),
                _('DDT: Q.'),
                _('OC: Totale'),
                _('DDT: Totale'),
                _('Differenza'),
                ]
                    
        excel_pool.write_xls_line(
            ws_name, row, header, default_format=f_header)

        # ---------------------------------------------------------------------
        # Extract data:
        # ---------------------------------------------------------------------
        # Database for DDT and order:
        ddt_db = {}
        ddt_ids = ddt_line_pool.search(cr, uid, [], context=context)
        for line in ddt_line_pool.browse(cr, uid, ddt_ids, context=context):
            if line.order_id.id not in ddt_db:
                ddt_db[line.order_id.id] = []
            if line.ddt_id not in ddt_db[line.order_id.id]:
                ddt_db[line.order_id.id].append(line.ddt_id)

        # Read order:
        res = {}
        order_ids = order_pool.search(cr, uid, domain, context=context)
        for order in order_pool.browse(cr, uid, order_ids, context=context):            
            if order not in res:
                # Order ref: (gap, DDT check, Invoice check)
                res[order] = [0.0, [], []]

            # -----------------------------------------------------------------            
            # DDT and invoice check:
            # -----------------------------------------------------------------            
            for level, list_ids in (
                    (1, order.check_ddt_ids), 
                    (2, order.check_invoice_ids)):
                for check in list_ids:
                    if abs(check.difference) >= tollerance:
                        res[order][0] += check.difference

                    if mode != 'ddt': # add line only if not ddt mode
                        res[order][level].append(check)
                    
        # Print sorted order:
        total = 0.0
        for order in sorted(res, key=lambda x: x.name):

            # DDT Line color depend on difference: (red - green - white)
            difference = res[order][0]
            total += difference
            if abs(difference) <= tollerance:
                f_text_default = f_bg_white
                f_number_default = f_bg_white_number
                if mode == 'difference':
                    continue # jump line that write DDT header without diff.
            elif difference > 0:
                f_text_default = f_bg_red
                f_number_default = f_bg_red_number
            else: # >0
                f_text_default = f_bg_green
                f_number_default = f_bg_green_number
                
            row += 1
            ddt_text = ''
            for item in ddt_db.get(order.id, ()):
                ddt_text += '%s%s [%s]' % (
                    ', ' if ddt_text else '',
                    item.name,
                    excel_pool.format_date(item.date),
                    )

            # Only DDT:                    
            if mode == 'ddt':
                excel_pool.write_xls_line(ws_name, row, [
                    ddt_text,
                    '%s%s' % (
                        order.name, 
                        '(FATT.)' if order.has_invoice else '',
                        ),                        
                    order.date,
                    (difference, f_number_default),                    
                    ], default_format=f_text_default)
            else:
                excel_pool.write_xls_line(ws_name, row, [
                    ddt_text,
                    '%s%s [%s]' % (
                        order.name, 
                        '(FATT.)' if order.has_invoice else '',
                        order.date,
                        ),
                    '', '', '', '', '', '', '', '', 
                    (res[order][0], f_number_default),
                    ], default_format=f_text_default)
                
                # Detailed check line:
                for level in (1, 2):   
                    for check in res[order][1]:
                        difference = check.difference or 0.0
                        if mode == 'difference' and abs(difference) <= tollerance:
                            continue # only case to jump
                            
                        row += 1
                        # DDT Line color depend on status:
                        if check.state == 'correct':
                            f_text_default = f_bg_white
                            f_number_default = f_bg_white_number
                        elif check.state == 'difference':
                            f_text_default = f_bg_red
                            f_number_default = f_bg_red_number
                        elif check.state == 'order':
                            f_text_default = f_bg_blue
                            f_number_default = f_bg_blue_number
                        elif check.state == 'invoice':
                            f_text_default = f_bg_yellow
                            f_number_default = f_bg_yellow_number
                        
                        excel_pool.write_xls_line(ws_name, row, [
                            '(DDT)' if level == 1 else '(FATT)',
                            check.name, 
                            check.article, 

                            (check.order_price, f_number_default), 
                            (check.invoice_price, f_number_default),

                            (check.order_qty, f_number_default), 
                            (check.invoice_qty, f_number_default), 

                            (check.order_total, f_number_default), 
                            (check.invoice_total, f_number_default),

                            (difference, f_number_default),
                            ], default_format=f_text_default, col=1)

        row += 1
        if mode=='ddt':
            col = 2
        else:
            col = 9
        if total > 0:
            excel_pool.write_xls_line(ws_name, row, ['Totale', total, ], 
                default_format=f_bg_green_number, col=col)
        else:    
            excel_pool.write_xls_line(ws_name, row, ['Totale', total, ], 
                default_format=f_bg_red_number, col=col)

        return excel_pool.return_attachment(cr, uid, ws_name, 
            version='7.0', php=False, context=context)

    _columns = {
        'mode': fields.selection([
            ('ddt', 'Only DDT'),
            ('difference', 'With difference'),
            ('all', 'All details'),
            ], 'Mode', required=True),
            
        'from_date': fields.date('From date'),
        'to_date': fields.date('To date'),
        
        'note': fields.text('Procedure', readonly=True),
        }
        
    _defaults = {
        'mode': lambda *x: 'ddt',
        
        'note': lambda *x: _('''
            <b>DDT compare procedure:</b><br/>
            <p>
            Launch sprix from Mexal Service menu:
            # 780 (Export DDT)
            </p>
            <p>
            When the exprot is finished press <b>DONE</b>
            </p>
            '''),
        }    

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
