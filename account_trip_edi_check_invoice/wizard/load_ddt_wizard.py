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

        # 1. Import DDT file from Mexal (previously extracted)
        
        # 2. Refresh Order in ODOO (from files loaded nightly)
        
        return True
    
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

        # ---------------------------------------------------------------------
        # Parameters and domain filter:
        # ---------------------------------------------------------------------
        wiz_proxy = self.browse(cr, uid, ids, context=context)[0]        
        
        mode = wiz_proxy.mode
        
        domain = [('has_ddt', '=', True)]
        domain_text = _('Order VS DDT (%s)') % mode
            
        
        if wiz_proxy.from_date:
            domain.append(
                ('date', '>=', wiz_proxy.from_date))
            domain_text.append(_(' - From date %s') % wiz_proxy.from_date)
        if wiz_proxy.to_date:
            domain.append(
                ('date', '<=', wiz_proxy.from_date))
            domain_text.append(_(' - To date %s') % wiz_proxy.to_date)
        
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
        f_bg_white = excel_pool.get_format('bg_white')
        f_bg_red = excel_pool.get_format('bg_red')
        f_bg_green = excel_pool.get_format('bg_green')
        
        f_number = excel_pool.get_format('number')
        
        # ---------------------------------------------------------------------
        # Format columns:
        # ---------------------------------------------------------------------
        excel_pool.column_width(ws_name, [
            20, 20, 
            15, 15, 
            15, 15, 
            15, 15, 
            20,             
            ])
        
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
            header = [
                _('DDT'),
                _('Date'),
                _('Differenza'),
                ]
        else:
            header = [
                _('DDT'),
                _('Code'),
                _('OC: Pdv'),
                _('DDT: Pdv'),
                _('OC: Q.'),
                _('DDT: Q.'),
                _('OC: Total'),
                _('DDT: Total'),
                _('Differenza'),
                ]
                    
        excel_pool.write_xls_line(
            ws_name, row, header, default_format=f_header)

        # ---------------------------------------------------------------------
        # Extract data:
        # ---------------------------------------------------------------------
        res = []
        order_ids = order_pool.search(cr, uid, domain, context=context)
        for order in self.browse(cr, uid, order_ids, context=context):
            ddt = order.ddt_id
            
            if ddt not in res:
                res[ddt] = [0.0, []]
                # DDT ref: (gap, check list)
            
            if check in ddt.check_ddt_ids:
                if abs(difference) >= res[ddt][0]:
                    res[ddt][0] += difference

                if mode != 'ddt': # add line only if not ddt mode
                    res[ddt][1].append(check)
                    
        for ddt in sorted(res, key=lambda x: x.name):
            row += 1
            excel_pool.write_xls_line(ws_name, row, [
                ddt.name, 
                ddt.date,
                res[ddt][0],                    
                ], default_format=f_text)

            # Detailed extra data:    
            if mode != 'ddt':
                excel_pool.write_xls_line(ws_name, row, [
                    '%s [%s]' % (ddt.name, ddt.date),
                    '', '', '', '', '', '', '', 
                    res[ddt][0],
                    ], default_format=f_text)
                
                # Detailed check line:    
                for check in res[ddt][1]:
                    if mode == 'difference' and abs(res[ddt][0]) <= tollerance:
                        continue # only case to jump
                        
                    row += 1
                    excel_pool.write_xls_line(ws_name, row, [
                        '',
                        check.article, 

                        check.order_price, 
                        check.invoice_price,

                        check.order_qty, 
                        check.invoice_qty, 

                        check.order_total, 
                        check.invoice_total,

                        res[ddt][0], # total difference:
                        ], default_format=f_text)

        return excel_pool.return_attachment(cr, uid, ws_name, 
            version='7.0', php=True, context=context)

    _columns = {
        'mode': fields.selection([
            ('ddt', 'DDT'),
            ('difference', 'Difference'),
            ('all', 'All'),
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
