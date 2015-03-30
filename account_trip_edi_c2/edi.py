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

class edi_company_c2(orm.Model):
    ''' Add model for parametrize function for Company 2
        Model has only function for a sort of abstract class
    '''

    _name = 'edi.company.c2'
    _description = 'EDI Company 2'

    # -------------------------------------------------------------------------    
    #                     Abstract function and property:
    # -------------------------------------------------------------------------    
    trace = {
        'number': (19, 29),
        'date': (29, 37), # 8
        'deadline': (45, 53), #8
        'customer': (1545, 1645), # 100
        'detail_code': (2356, 2391), # 35
        'detail_description': (2531, 2631), # 100
        'detail_um': (2641, 2644), # 3
        'detail_quantity': (2631, 2641), # 10 
        'detail_price': (2877, 2887), # 10 
        'detail_total': (2907, 2917), # 10
        
        # Destination blocks:
        'destination_facility': (0, 0), # 35 facility  TODO: 1225 1260     
        'destination_cost': (0, 0), # 30 cost
        'destination_site': (1224, 1259), # 35 site             
        'destination_description': (1259, 1359) # 100 description
        }

    def get_timestamp_from_file(self, file_in, path_in=None):
        # TODO
        ''' Get timestamp value from file name
            File is: ELIORD20141103091707.ASC
                     ------YYYYMMGGhhmmss----
            Millisecond are 
                00 for create order ELIORD
                10 for delete order ELICHG     
        '''
        ts = os.path.getctime(os.path.join(path_in, file_in))
        return datetime.fromtimestamp(ts).strftime(
            DEFAULT_SERVER_DATETIME_FORMAT + ".%f" )
        
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
            
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
