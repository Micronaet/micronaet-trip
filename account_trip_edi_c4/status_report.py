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

class edi_company_report_this(orm.Model):
    ''' Manage more than one importation depend on company
    '''    
    _inherit = 'edi.company'
    
    # -------------------------------------------------------------------------
    # OVERRIDE: Collect data for report
    # -------------------------------------------------------------------------
    def collect_future_order_data_report(self, cr, uid, context=None):
        """ Overridable procedure for manage the report data collected in all 
            company with active EDI company
            Report: 
                'header'
                'data'
                'empty_record'
        """
        this_id = 4
        report = super(
            edi_company_report_this, self).collect_future_order_data_report(
                cr, uid, context=context)
                
        company = self.get_module_company(cr, uid, this_id, context=context)
        if not company:
            return report
        
        # =====================================================================
        # Data will be create with override:
        # =====================================================================
        this_pool = self.pool.get('edi.company.c%s' % this_id)
        trace = this_pool.trace
        
        data = report['data']
        detail = report['detail']

        # Append this company data:
        path = os.path.expanduser(company.trip_import_folder)
        for root, folders, files in os.walk(path):
            for filename in files:
                # create or delete mode TODO
                mode = this_pool.get_state_of_file(filename, []) # No forced
                if mode == 'create':
                    sign = -1  # Note: create order is negative for stock!
                else:
                    _logger.warning('Not used: %s' % filename)
                    continue   # TODO complete!!
                    # forced only
                    sign = +1

                fullname = os.path.join(root, filename)                
                order_file = open(fullname)
                deadline = False
                
                for row in order_file:
                    # Use only data row:
                    if this_pool.is_an_invalid_row(row):
                        continue

                    # Deadline information:
                    if not deadline:
                        deadline = this_pool.format_date(
                            row[trace['deadline'][0]: trace['deadline'][1]])
                        number = row[
                            trace['number'][0]: trace['number'][1]].strip()
                        
                        # Define col position:
                        if deadline < report['min']:
                            col = 0
                        elif deadline > report['max']:
                            col = report['days'] - 1 # Go in last cell
                        else:
                            col = report['header'][deadline]

                    # Extract used data:
                    default_code = row[
                        trace['detail_code'][0]:
                            trace['detail_code'][1]].strip()
                    quantity = float(row[
                        trace['detail_quantity'][0]: 
                            trace['detail_quantity'][1]])

                    # ---------------------------------------------------------
                    # Report data:                        
                    # ---------------------------------------------------------
                    if default_code not in data:
                        data[default_code] = report['empty'][:]
                    data[default_code][col] += sign * quantity    
                   
                    # Detail data:
                    detail.append([
                        default_code,
                        col,
                        'OC',
                        company.name,
                        filename,
                        number,
                        deadline,
                        quantity,
                        '', 
                        ])
                order_file.close()
        return report

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
