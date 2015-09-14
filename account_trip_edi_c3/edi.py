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
from openerp import SUPERUSER_ID
from openerp import tools
from openerp.tools.translate import _
from openerp.tools.float_utils import float_round as round
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, 
    DATETIME_FORMATS_MAP, 
    float_compare)


_logger = logging.getLogger(__name__)

class edi_company_c3(orm.Model):
    ''' Add model for parametrize function for Company 3
        Model has only function for a sort of abstract class
    '''

    _name = 'edi.company.c3'
    _description = 'EDI Company 3'

    # -------------------------------------------------------------------------    
    #                     Abstract function and property:
    # -------------------------------------------------------------------------    
    start_structure = 3 # char
    structured = { # field > block
        'number': 'BGM',
        'date': 'BGM',
        'customer': 'BGM',

        'deadline': 'DTM',
        
        'destination_facility': 'NAD',
        'destination_cost': 'NAD',
        'destination_site': 'NAD',
        
        'detail_code': 'LIN',
        'detail_description': 'LIN',
        'detail_um': 'LIN',
        'detail_quantity': 'LIN',
        'detail_price': 'LIN',
        'detail_total': 'LIN',
        }

    trace = { # structured:
        # BGM
        'number': (115, 150),
        'date': (150, 158), # 8
        'customer': (0, 0), # not used

        # DTM
        'deadline': (3, 11), #8
        
        # NAS - Destination blocks:
        'destination_facility': (0, 0), # 35 
        'destination_cost': (0, 0), # 30 
        'destination_site': (3, 20), # 17
        'destination_description': (23, 93), # 70
        # TODO address?
        
        # LIN'
        'detail_code': (82, 117), # 35
        'detail_description': (152, 187), # 35
        'detail_um': (205, 208), # 3
        'detail_quantity': (190, 205), # 15
        'detail_price': (208, 223), # 15
        'detail_total': (0, 0), 
        }

    def get_timestamp_from_file(self, file_in, path_in=None):
        # TODO
        ''' Get timestamp value from file name
            File is: COMPANY_orderdate_order_deadline.eur
        '''
        part = file_in.split('_')        
        return "%s-%s-%s" % (
            part[1][:4], 
            part[1][4:6], 
            part[1][6:8], 
            )
        
    def get_state_of_file(self, file_in, forced_list):
        ''' Test state of file depend on name and forced presence
            2 state: forced or create (no update here)
        '''
        if file_in in forced_list: # Forced (pickle file)
            return 'forced'
        return 'create'

    def get_destination(self, facility, cost, site):
        ''' Mask for code destination (only the last: site is used here)
        '''
        return "[%s]" % site

    def get_destination_id(self, cr, uid, facility, cost, site, context=None):
        ''' Get 3 parameters for destination and return ID get from res.partner
            generated during importation
        '''
        return self.pool.get('res.partner').search_supplier_destination(
            cr, uid, "", site, context=context)

    def get_priority(self, cr, uid, file_in):
        ''' Always normal (no priority management)
        '''
        return 'normal'    
            
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
