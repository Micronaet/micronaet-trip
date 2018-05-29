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
        if context is None: 
            context = {}        

        # Pool used:
        excel_pool = self.pool.get('excel.writer')
        wiz_proxy = self.browse(cr, uid, ids, context=context)[0]
            
        # ---------------------------------------------------------------------
        # Domain creation:
        # ---------------------------------------------------------------------
        trip_ids = context.get('active_ids', [])        

        # -----------------------------------------------------------------
        # Trip:
        # -----------------------------------------------------------------
        # Parameters:
        ws_name = _('Ordini EDI')
        name_of_file = _('ordini.xls')            
        
        header = [
            _('Azienda'),
            _('Cliente'),
            _('Destinazione cliente'),
            
            _('Data'),
            _('Scadenza'),
            
            _('Tipo'),

            _('Viaggio 1'),
            _('Viaggio 2'),
            _('Dettaglio'),
            ]

        # -----------------------------------------------------------------            
        # Create Excel file:    
        # -----------------------------------------------------------------            
        # Worksheet:
        ws = excel_pool.create_worksheet(ws_name)
        
        # Format:
        excel_pool.set_format()
        format_title = excel_pool.get_format('title')
        format_header = excel_pool.get_format('header')
        format_text = excel_pool.get_format('text')
        
        # Column satup:
        excel_pool.column_width(ws_name, [
            15,
            30,
            30,
            
            15,
            15,
            
            10,
            
            15,
            15,
            60,
            ])
            
        # Title:
        row = 0
        excel_pool.write_xls_line(ws_name, row, [
            _('Esportazione testate viaggio selezionate'),
            ], format_title)

        # Header:            
        row = 1
        excel_pool.write_xls_line(ws_name, row, header, format_header)

        # -----------------------------------------------------------------            
        # Load data:            
        # -----------------------------------------------------------------            
        trip_pool = self.pool.get('edi.trip.line')
        trip_ids = trip_pool.search(cr, uid, domain, context=context)
        for trip in sorted(
                trip_pool.browse(
                    cr, uid, trip_ids, context=context), 
                key=lambda x: (x.date, x.ref)):
            row += 1    
            data = [
                trip.compnany_id.name or '',
                trip.customer,
                trip.destination_id.name,

                trip.date,
                
                trip.type or '',
                
                trip.tour1_id.name or '',
                trip.tour2_id.name or '',
                trip.information,
                ]

            excel_pool.write_xls_line(ws_name, row, data, format_text)
        
        return excel_pool.return_attachment(cr, uid, ws_name, 
            name_of_file='extrazione_viaggi_selezionati', version='7.0', 
            php=True, context=context)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:


