#!/usr/bin/python
# -*- coding: utf-8 -*-
###############################################################################
#
# ODOO (ex OpenERP) 
# Open Source Management Solution
# Copyright (C) 2001-2015 Micronaet S.r.l. (<https://micronaet.com>)
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

class edi_company_report(orm.Model):
    ''' Manage more than one importation depend on company
    '''    
    _inherit = 'edi.company'

    # -------------------------------------------------------------------------
    # Collect data for report (overridable)
    # -------------------------------------------------------------------------
    def collect_future_order_data_report(self, cr, uid, context=None):
        """ Overridable procedure for manage the report data collected in all 
            company with active EDI company
        """
        if context is None:
            context = {}

        # Read parameters:
        account_days_covered = context.get('account_days_covered', 2)
        report_days = context.get('report_days', 28) 
        columns = report_days # Report Days total columns

        now_dt = datetime.now() 
        now = now_dt.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        from_date_dt = now_dt + timedelta(days=account_days_covered)
        to_date_dt = from_date_dt + timedelta(days=report_days)
        
        report = {
            # Title:
            'title': 'Stampa progressivi di magazzino, data: %s' % now,
            
            # Header data:
            'header': {
                # Data col: position
                },

            # Cell data:
            'data': {
                # Article record: [Q., data, list]
                },
                
            # Function used to generate empty record:
            'empty_record': lambda x: [0.0 for item in range(0, columns)],                
            }
        
        # Header creation:
        pos = 0
        for day in range(columns):
            date = from_date_dt + timedelta(days=day)
            report['header'][date.strftime('%m-%d')] = pos
            pos += 1
        
        # =====================================================================
        # XXX Data will be create with override:
        # =====================================================================
        
        return report
        
    # -------------------------------------------------------------------------
    # Report action:
    # -------------------------------------------------------------------------
    def transform_delta_record(self, start_qty, delta, excel_format):
        """ Transform delta record with quantity record
        """
        delta[0] += start_qty
        for col in range(1, len(delta)):
            new_qty += delta[col - 1] # Append previous col
            if new_qty >= 0:
                delta[col] = (new_qty, excel_format['black']['number'])
            else:    
                delta[col] = (new_qty, excel_format['red']['number'])
            
    def generate_future_order_data_report(self, cr, uid, ids, context=None):
        """ Overridable procedure for manage the report data collected in all 
            company with active EDI company
        """
        excel_pool = self.pool.get('excel.writer')
        
        if context is None:
            context = {}
        
        # ---------------------------------------------------------------------
        # Parameter for report:
        # ---------------------------------------------------------------------
        context.update({
            'account_days_covered': 2,
            'report_days':28,            
            })

        # ---------------------------------------------------------------------
        # Excel file:
        # ---------------------------------------------------------------------
        _logger.info('Start collect information for EDI stock status report')
        report = self.collect_future_order_data_report(
            cr, uid, context=context)
        
        # Get data from account
        account_data = {
            # Product code: Available data
            }

        extension = 'xlsx'
        ws_name = _('EDI stato magazzino')
        
        excel_pool.create_worksheet(ws_name, extension=extension)

        excel_pool.set_format(number_format='0.#0')
        excel_pool.get_format() # Update workbook
        
        excel_format = {
            'title': excel_pool.get_format('title'),
            'header': excel_pool.get_format('header'),
    
            'black': {
                'text': excel_pool.get_format('text'),
                'number': excel_pool.get_format('number'),                    
                },

            'green': {
                'text': excel_pool.get_format('text_green'),
                'number': excel_pool.get_format('number_green'),                    
                },

            'red': {
                'text': excel_pool.get_format('text_red'),
                'number': excel_pool.get_format('number_red'),                    
                },

            'blue': {
                'text': excel_pool.get_format('text_blue'),
                'number': excel_pool.get_format('number_blue'),                    
                },
            }

        col_width = [
            15, 40, 5, 15,
            # TODO appena date total
            ]
        col_width.extend([5 for item in range(context.get('report_days'))])            

        header = [
            _('Codice'),
            _('Nome'),
            _('UM'),
            _('Gestionale'),
            # TODO append date total title
            ]
        fixed_cols = len(header)
        excel_pool.column_width(ws_name, col_width)

        # ---------------------------------------------------------------------        
        # Title:
        # ---------------------------------------------------------------------        
        row = 0
        excel_pool.write_xls_line(ws_name, row, (
            report['title'], 
            ), excel_format['title'])
        
        # ---------------------------------------------------------------------        
        # Header:
        # ---------------------------------------------------------------------        
        row += 2
        excel_pool.write_xls_line(
            ws_name, row, header, excel_format['header'])
        # Integration:
        excel_pool.write_xls_line(
            ws_name, row, sorted(report['header'].keys()), 
            excel_format['header'], col=fixed_cols)
            
        # ---------------------------------------------------------------------        
        # Data
        # ---------------------------------------------------------------------
        black = excel_format['black']
        red = excel_format['red']
        
        for default_code in report['data']:
            row +=1 

            delta = report['data'][product]
            #default_code = product.default_code

            start_qty = account_data.get(default_code, 0)
            self.transform_delta_record(start_qty, delta, excel_format)
            
            excel_pool.write_xls_line(ws_name, row, [
                default_code,
                default_code, # TODO Name
                '', # TODO UOM
                (start_qty, black['number'])
                ], black['text'])
                
            # Integration:
            excel_pool.write_xls_line(
                ws_name, row, delta, excel_format['header'], 
                col=fixed_cols)
            
            
        
        
        
        return excel_pool.return_attachment(cr, uid, ws_name, 
            name_of_file='future_stock_status.xls', version='7.0', 
            php=True, context=context)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
