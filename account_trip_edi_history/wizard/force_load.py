 # -*- coding: utf-8 -*-
###############################################################################
#
#    Copyright (C) 2001-2014 Micronaet SRL (<http://www.micronaet.it>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
import os
import sys
import netsvc
import logging
import pickle
from openerp.osv import osv, orm, fields
from datetime import datetime, timedelta
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, DATETIME_FORMATS_MAP, float_compare)
import openerp.addons.decimal_precision as dp
from openerp.tools.translate import _


_logger = logging.getLogger(__name__)

class edi_history_check_load_wizard(osv.osv_memory):
    ''' Force reload of activity (saved in scheduler)
    '''

    _name = 'edi.history.check.load.wizard'
    _description = 'EDI check reload data'

    # -------------
    # Button event: 
    # -------------
    def edi_check_load(self, cr, uid, ids, context=None):
        ''' Call function passing scheduled parameters
        '''
        return True

    _columns = {
        'note': fields.text('Importation note'),
        }
    
    _defaults = {
        'note': lambda *x: """
             <h4>Force load of check data</h4>
             <p>
                 Operation must be lauched after run Export operation in
                 accounting program
             </p>""",
        }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
