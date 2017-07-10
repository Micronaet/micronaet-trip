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

class edi_company_c4(orm.Model):
    ''' Add model for parametrize function for Company 4
        Model has only function for a sort of abstract class
    '''

    _name = 'edi.company.c4'
    _description = 'EDI Company 4'

    # -------------------------------------------------------------------------    
    #                     Abstract function and property:
    # -------------------------------------------------------------------------    
    trace = {
        'number': (15, 24),
        'date': (0, 10), # 8
        'deadline': (0, 10), #8   # TODO ???? not present!!!<<<<<<<<<<<<<<<<<<<
        'customer': (0, 0), # TODO not present<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
        'detail_code': (40, 56), # 35
        'detail_description': (56, 96), # 100
        'detail_um': (96, 99), # 3
        'detail_quantity': (99, 108), # 10 
        'detail_price': (108, 118), # 10 
        'detail_total': (2907, 2917), # 10 TODO not present!!!
        
        # Destination blocks:
        'destination_facility': (0, 0), # 35 TODO not present!!
        'destination_cost': (0, 0), # 30 TODO not present!!
        'destination_site': (1224, 1259), # 35 TODO not present!!<<<<<<<<<<<<<<
        'destination_description': (1259, 1359) # 100 TODO not present!!<<<<<<<
        }

    def get_timestamp_from_file(self, file_in, path_in=None):
        # TODO
        ''' Get timestamp value from file name
            File is: 20151231_270.ASC
        '''
        return "%s-%s-%s" % (
            file_in[:4], 
            file_in[4:6], 
            file_in[6:8], 
            )
        
    def get_state_of_file(self, file_in, forced_list):
        ''' Test state of file depend on name and forced presence
        '''
        try:
            type_file = file_in.split("_")[1]
        except:
            type_file = False # TODO lot error
                
        if file_in in forced_list: # Forced (pickle file)
            return 'forced'
        elif type_file == 'ORDCHG': # change (usually ORDERS)
            return 'change'
        elif not type_file : # change (usually ORDERS)
            return 'anomaly'
        else: # OR or ORDERS
            return 'create'

    def get_destination(self, facility, cost, site):
        ''' Mask for code destination (only the last: site is used)'''
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

    # Format:
    def format_int(self, value):
        ''' EDI integer format
        '''
        return value

    def format_float(self, value, decimal=3, with_separator=False, separator='.'):
        ''' EDI float format
        '''
        return value

    def format_date(self, value, date_format='ISO'):
        ''' EDI file date format YYYYMMDD
        '''        
        return "%s-%s-%s" % (value[:4], value[4:6], value[6:8])

    def format_string(self, value):
        ''' EDI file string 
        '''
        return value.strip()
            
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: