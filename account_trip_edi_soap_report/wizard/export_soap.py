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


class EdiSoapExportExcelReport(orm.TransientModel):
    ''' Wizard for export data in Excel
    '''
    _name = 'edi.soap.export.excel.report'

    # --------------------
    # Wizard button event:
    # --------------------
    def action_print(self, cr, uid, ids, context=None):
        ''' Event for print report
        '''
        if context is None: 
            context = {}        

        # Pool used:
        excel_pool = self.pool.get('excel.writer')
        line_pool = self.pool.get('edi.soap.logistic.line')
        
        wiz_proxy = self.browse(cr, uid, ids, context=context)[0]
            
        # ---------------------------------------------------------------------
        # Domain creation:
        # ---------------------------------------------------------------------
        domain = []
        filter_description = _('Lista movimenti SOAP EDI')
        
        # Date:
        if wiz_proxy.from_date:
            domain.append(('date', '>=', '%s' % wiz_proxy.from_date))
            filter_description += _(', Dalla data: %s') % \
                wiz_proxy.from_date
        if wiz_proxy.to_date:
            domain.append(('date', '<=', '%s' % wiz_proxy.to_date))
            filter_description += _(', Alla data: %s') % \
                wiz_proxy.to_date

        if wiz_proxy.from_deadline:
            domain.append(('deadline', '>=', '%s' % wiz_proxy.from_deadline))
            filter_description += _(', Dalla scadenza: %s') % \
                wiz_proxy.from_deadline
        if wiz_proxy.to_deadline:
            domain.append(('deadline', '<=', '%s' % wiz_proxy.to_deadline))
            filter_description += _(', Alla scadenza: %s') % \
                wiz_proxy.to_deadline

        # Filter for details:
        filter_code = wiz_proxy.filter_code or False
        if filter_code: 
            filter_description += _(', Codice prodotto: %s') % filter_code
        
        # -----------------------------------------------------------------
        # Trip:
        # -----------------------------------------------------------------
        # Parameters:
        extension='xls'
        ws_name = _('Ordini SOAP EDI')
        ws_detail_name = _('Dettaglio')
        ws_total_name = _('Totali')

        name_of_file = _('ordini_soap.xls')            
        
        # -----------------------------------------------------------------            
        # Create Excel file:    
        # -----------------------------------------------------------------            
        # Worksheet:
        excel_pool.create_worksheet(ws_name, extension=extension)
        excel_pool.create_worksheet(ws_detail_name)
        excel_pool.create_worksheet(ws_total_name)
        
        # Format:
        excel_pool.set_format(number_format='0,#0')
        excel_pool.get_format() # Update workbook
        format_title = excel_pool.get_format('title')
        format_header = excel_pool.get_format('header')

        format_text = excel_pool.get_format('text')
        format_text_green = excel_pool.get_format('text_green')
        format_text_blue = excel_pool.get_format('text_blue')
        format_text_red = excel_pool.get_format('text_red')

        format_number = excel_pool.get_format('number')
        format_number_green = excel_pool.get_format('number_green')
        format_number_blue = excel_pool.get_format('number_blue')
        format_number_red = excel_pool.get_format('number_red')

        
        # Column setup width:
        col_width = [
            7, 20, 12, 50,            
            12, 12,            
            10, 6,
            8, 8
            ]
        excel_pool.column_width(ws_name, col_width)
        col_width.extend([15, 30, 5, 10, 10])
        excel_pool.column_width(ws_detail_name, col_width)
        excel_pool.column_width(ws_total_name, [15, 40, 5, 10])
            
        # Title:
        row = row_detail = row_total = 0
        excel_pool.write_xls_line(ws_name, row, [
            _('Filtro:'),
            filter_description,
            ], format_title)
        excel_pool.write_xls_line(ws_detail_name, row_detail, [
            _('Dettaglio prodotti da ordine:'),
            ], format_title)
        excel_pool.write_xls_line(ws_total_name, row_total, [
            _('Totale prodotti per codice e UM:'),
            ], format_title)

        # Header:            
        header = [
            _('Azienda'),
            _('Cliente'),
            _('Rif.'),
            _('Destinazione cliente'),
            
            _('Data'),
            _('Scadenza'),
            
            '', _('Tipo'),
            '', _('Ricors.'),

            '', 
            ''
            ]
            
        row = row_detail = row_total = 2
        excel_pool.write_xls_line(ws_name, row, header, format_header)
        header.extend([
            _('Codice'),
            _('Nome'),
            _('UM'),
            _('Q.'),
            _('Prezzo'),
            _('Totale'),
            ])
        excel_pool.write_xls_line(ws_detail_name, row_detail, header, 
            format_header)
        excel_pool.write_xls_line(ws_total_name, row_total, [
            _('Codice'),
            _('Nome'),
            _('UM'),
            _('Totale'),
            ], format_header)

        # -----------------------------------------------------------------            
        # Load data:            
        # -----------------------------------------------------------------            
        line_ids = line_pool.search(cr, uid, domain, context=context)
        _logger.info('Line selected: %s [%s]' % (
            len(line_ids),
            domain,
            ))

        res_total = {}
        for line in sorted(
                line_pool.browse(
                    cr, uid, line_ids, context=context), 
                key=lambda x: (x.date, x.number)):

            # -----------------------------------------------------------------
            # Write header page:
            # -----------------------------------------------------------------    
            data = [
                line.company_id.name or '',
                line.customer,
                line.number,
                line.destination_id.name,

                excel_pool.format_date(line.date),
                excel_pool.format_date(line.deadline),
                
                line.type or '',
                'X' if line.recursion > 1 else '',
                
                '', #line.tour1_id.name or '',
                '', #line.tour2_id.name or '',
                
                '', '', '', '', '', '',
                ]
                
            # Extra data for detail sheet:
            information = parse_html_to_detail(line.information)
            filter_code_present = False
            for item in information:
                # Filter code management:
                if filter_code and filter_code not in item[0]:
                    continue

                filter_code_present = True
                
                # -------------------------------------------------------------        
                # Write detail page:
                # -------------------------------------------------------------        
                row_detail += 1
                
                # Update product information:
                data[10] = item[0]
                data[11] = item[1]
                data[12] = item[2]
                data[13] = (float(
                    item[3].replace('|', '').strip()), f_number)
                data[14] = (float(
                    item[4].replace('|', '').strip()), f_number)
                data[15] = (
                    float(item[5].replace('|', '').strip()), f_number)
                
                key = (data[10], data[11], data[12])
                        
                # -------------------------------------------------------------        
                # Write total page:
                # -------------------------------------------------------------        
                # Keep only positive numbers:
                current = data[13][0]
                if current < 0.0:
                    current = 0.0
                if key in res_total:
                    res_total[key] += current
                else:    
                    res_total[key] = current
                # Write in total page:    
                excel_pool.write_xls_line(
                    ws_detail_name, row_detail, data, f_text)
           
            # Write now header data (for filter code test):
            if not filter_code or filter_code_present:
                row += 1    
                excel_pool.write_xls_line(ws_name, row, data[:10], f_text)
         

        for item in sorted(res_total):
            row_total += 1
            tot = res_total[item]
            
            excel_pool.write_xls_line(ws_total_name, row_total, [
                item[0], 
                item[1], 
                item[2], 
                (tot, f_number),
                ], format_text)
            
                            
        return excel_pool.return_attachment(cr, uid, ws_name, 
            name_of_file='estrazione_viaggi_selezionati.xls', version='7.0', 
            php=True, context=context)

    _columns = {
        # Char:
        #'ref': fields.char('Ref.', size=20),
        #'partner_name': fields.char('Partner', size=80),
        'filter_code': fields.char('Product', size=80),
        
        # Many 2 one
        #'company_id': fields.many2one('edi.company', 'Company'),

        #'destination_id': fields.many2one('res.partner', 'Destination'),

        #'tour1_id': fields.many2one('trip.tour', 'Tour 1'),
        #'tour2_id': fields.many2one('trip.tour', 'Tour 2'),
    
        # Date filter:
        'from_date': fields.date('From date'),
        'to_date': fields.date('To date'),

        'from_deadline': fields.date('From deadline'),
        'to_deadline': fields.date('To deadline'),

        #'type': fields.selection([
        #    ('importing', 'To importing'),
        #    ('anomaly', 'Delete (Anomaly)'),
        #    ('create', 'Create'),
        #    ('change', 'Change'),
        #    ('deleting', 'To delete'),
        #    ('forced', 'To force'),
        #    ('delete', 'Delete'),
        #    ], 'Type'), 
        }        
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
