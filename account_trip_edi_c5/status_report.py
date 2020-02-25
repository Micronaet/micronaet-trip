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

class edi_company_report_c1(orm.Model):
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
        report = super(
            edi_company_report_c1, self).collect_future_order_data_report(
                cr, uid, context=context)
                
        company = self.get_module_company(cr, uid, 5, context=context)
        if not company:
            return report
        
        # =====================================================================
        # XXX Data will be create with override:
        # =====================================================================
        # Append this company data:
        
        return report




# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
