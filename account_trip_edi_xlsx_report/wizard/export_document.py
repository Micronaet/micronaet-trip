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


class QualityExportExcelReport(orm.TransientModel):
    ''' Wizard for export data in Excel
    '''
    _name = 'edi.export.excel.report'

    # --------------------
    # Wizard button event:
    # --------------------
    def action_print(self, cr, uid, ids, context=None):
        ''' Event for print report
        '''
        # Utility:
        def parse_html_to_detail(html):
            ''' Explode line from HTML table text:
            '''
            res = []
            start = False
            record_on = False
            for line in html.split('\n'):
                line = line.strip()
                if not start and line == '</tr>':
                    start = True
                    continue
                if not start:
                    continue    

                if line == '</tr>':
                    # record end:
                    record_on = False
                    res.append(record)
                    continue

                if line == '<tr>':
                    # record start:
                    record_on = True
                    record = []
                    continue
                    
                if record_on:
                    record.append(
                        line.replace(
                            '&nbsp;', '').replace(
                                '<td>', '').replace('</td>', ''))
                    continue
                
            return res
        
        def write_order_detail(excel_pool, ws_name, row, order, details):
            ''' Write order details on sheet
            '''
            # TODO 
            return row
            
        if context is None: 
            context = {}        

        # Pool used:
        excel_pool = self.pool.get('excel.writer')
        wiz_proxy = self.browse(cr, uid, ids, context=context)[0]
            
        # ---------------------------------------------------------------------
        # Domain creation:
        # ---------------------------------------------------------------------
        domain = []
        filter_description = _('Lista movimenti EDI')
        
        # Text:
        if wiz_proxy.ref:
            domain.append(('number', 'ilike', wiz_proxy.ref))
            filter_description += _(', Rif.: "%s"') % wiz_proxy.ref
        if wiz_proxy.partner_name:
            domain.append(('customer', 'ilike', wiz_proxy.partner_name))
            filter_description += _(', Cliente: "%s"') % wiz_proxy.partner_name

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
        
        # One2many:    
        if wiz_proxy.company_id:
            domain.append(('company_id', '=', wiz_proxy.company_id.id))
            filter_description += _(', Azienda: %s') % \
                wiz_proxy.company_id.name
        if wiz_proxy.destination_id:
            domain.append(('destination_id', '=', wiz_proxy.destination_id.id))
            filter_description += _(', Destinazione: %s') % \
                wiz_proxy.destination_id.name
                
        if wiz_proxy.tour1_id:
            domain.append(('tour1_id', '=', wiz_proxy.tour1_id.id))
            filter_description += _(', Viaggio 1: %s') % \
                wiz_proxy.tour1_id.name
        if wiz_proxy.tour2_id:
            domain.append(('tour2_id', '=', wiz_proxy.tour2_id.id))
            filter_description += _(', Viaggio 2: %s') % \
                wiz_proxy.tour2_id.name

        # -----------------------------------------------------------------
        # Trip:
        # -----------------------------------------------------------------
        # Parameters:
        ws_name = _('Ordini EDI')
        ws_detail_name = _('Dettaglio')
        ws_total_name = _('Totali')

        name_of_file = _('ordini.xls')            
        
        # -----------------------------------------------------------------            
        # Create Excel file:    
        # -----------------------------------------------------------------            
        # Worksheet:
        excel_pool.create_worksheet(ws_name)
        excel_pool.create_worksheet(ws_detail_name)
        excel_pool.create_worksheet(ws_total_name)
        
        # Format:
        excel_pool.set_format()
        format_title = excel_pool.get_format('title')
        format_header = excel_pool.get_format('header')
        format_text = excel_pool.get_format('text')
        
        # Column setup width:
        col_width = [
            7, 20, 50,            
            12, 12,            
            10, 3,
            7, 7
            ]
        excel_pool.column_width(ws_name, col_width)
        col_width.extend([15, 10])
        excel_pool.column_width(ws_detail_name, col_width)
        excel_pool.column_width(ws_total_name, [15, 20, 10])
            
        # Title:
        row = row_detail = row_total = 0
        excel_pool.write_xls_line(ws_name, row, [
            _('Filtro:'),
            filter_description,
            ], format_title)
        excel_pool.write_xls_line(ws_detail_name, row_detail, [
            _('Dettaglio prodotti da ordine:'),
            ], format_title)
        excel_pool.write_xls_line(ws_name, row_total, [
            _('Totale prodotti'),
            ], format_title)

        # Header:            
        header = [
            _('Azienda'),
            _('Cliente'),
            _('Destinazione cliente'),
            
            _('Data'),
            _('Scadenza'),
            
            _('Tipo'),
            _('Ricors.'),

            _('Viaggio 1'),
            _('Viaggio 2'),
            ]
            
        row = row_detail = row_total = 1
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
        excel_pool.write_xls_line(ws_detail_name, row_total, [
            _('Codice'),
            _('Nome'),
            _('Totale'),
            ], format_header)

        # -----------------------------------------------------------------            
        # Load data:            
        # -----------------------------------------------------------------            
        trip_pool = self.pool.get('trip.edi.line')
        trip_ids = trip_pool.search(cr, uid, domain, context=context)
        _logger.info('Trip selected: %s [%s]' % (
            len(trip_ids),
            domain,
            ))
        for trip in sorted(
                trip_pool.browse(
                    cr, uid, trip_ids, context=context), 
                key=lambda x: (x.date, x.number)):
            row += 1    
            data = [
                trip.company_id.name or '',
                trip.customer,
                trip.destination_id.name,

                trip.date,
                trip.deadline,
                
                trip.type or '',
                'X' if trip.recursion else '',
                
                trip.tour1_id.name or '',
                trip.tour2_id.name or '',
                
                
                # Extra data for detail sheet:
                '',
                '',
                '',
                '',
                '',
                '',
                ]
            excel_pool.write_xls_line(ws_name, row, data, format_text)

            # Get detail of line:            
            information = parse_html_to_detail(trip.information)
            for item in information:
                row_detail += 1
                # Update prodcut information:
                data[9] = item[0]
                data[10] = item[1]
                data[11] = item[2]
                data[12] = item[3]
                data[13] = item[4]
                data[14] = item[5]
                
                excel_pool.write_xls_line(
                    ws_detail_name, row_detail, data, format_text)
        
        return excel_pool.return_attachment(cr, uid, ws_name, 
            name_of_file='estrazione_viaggi_selezionati', version='7.0', 
            php=True, context=context)

    _columns = {
        # Char:
        'ref': fields.char('Ref.', size=20),
        'partner_name': fields.char('Partner', size=80),
        
        # Many 2 one
        'company_id': fields.many2one('edi.company', 'Company'),

        'destination_id': fields.many2one('res.partner', 'Destination'),

        'tour1_id': fields.many2one('trip.tour', 'Tour 1'),
        'tour2_id': fields.many2one('trip.tour', 'Tour 2'),
    
        # Date filter:
        'from_date': fields.date('From date'),
        'to_date': fields.date('To date'),

        'from_deadline': fields.date('From deadline'),
        'to_deadline': fields.date('To deadline'),

        'type': fields.selection([
            ('importing', 'To importing'),
            ('anomaly', 'Delete (Anomaly)'),
            ('create', 'Create'),
            ('change', 'Change'),
            ('deleting', 'To delete'),
            ('forced', 'To force'),
            ('delete', 'Delete'),
            ], 'Type'), 
        }        
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
