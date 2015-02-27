# -*- coding: utf-8 -*-
###############################################################################
#
# OpenERP, Open Source Management Solution
# Copyright (C) 2001-2015 Micronaet S.r.l. (<http://www.micronaet.it>)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
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
from openerp import SUPERUSER_ID, api
from openerp import tools
from openerp.tools.translate import _
from openerp.tools.float_utils import float_round as round
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, 
    DATETIME_FORMATS_MAP, 
    float_compare)


_logger = logging.getLogger(__name__)

class edi_company_c1(orm.Model):
    ''' Add model for parametrize function for Company 1
        Model has only function for a sort of abstract class
    '''

    _name = 'edi.company.c1'
    _description = 'EDI Company 1'

    # -------------------------------------------------------------------------    
    #                       Abstract function
    # -------------------------------------------------------------------------    
    def get_timestamp_from_file(file_in):
        ''' Get timestamp value from file name
            File is: ELIORD20141103091707.ASC
                     ------YYYYMMGGhhmmss----
            Millisecond are 
                00 for create order ELIORD
                10 for delete order ELICHG     
        '''
        return "%s-%s-%s %s:%s:%s.%s" % (
            file_in[6:10],   # Year
            file_in[10:12],  # Month
            file_in[12:14],  # Day
            file_in[14:16],  # Hour
            file_in[16:18],  # Minute
            file_in[18:20],  # Second
            "00" if file_in.startswith("ELIORD") else "10" # Millisecond
            ) 
    

class edi_company_selection(orm.Model):
    ''' Manage selection element for add Company 1 type
    '''
    
    _inherit = 'edi.company'

    # Override:
    def _type_importation_selection(self, cr, uid, context=None):
        selection = super(
            edi_company_selection, self)._type_importation_selection(
                cr, uid, context=context)

        selection.append(('c1', 'Company 1'))
        return selection
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
