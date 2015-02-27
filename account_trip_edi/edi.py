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
from openerp.osv import osv, orm, fields
from datetime import datetime, timedelta
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, DATETIME_FORMATS_MAP, float_compare
import openerp.addons.decimal_precision as dp
from openerp.tools.translate import _


_logger = logging.getLogger(__name__)


class res_company(osv.osv):
    ''' Add extra parameters for importation
    '''
    _name = 'res.company'
    _inherit = 'res.company'
    
    def get_trip_import_edi_folder(self, cr, uid, value='folder', context=None):
        ''' Read parameter for default EDI folder (set up in company)
            value: 'folder' (default) folder of EDI in file
                   'file' for file used to pass forced list
                   'delete' for folder used for deletion elements
        '''
        try:
            company_ids = self.search(cr, uid, [], context=context)
            company_proxy = self.browse(
                cr, uid, company_ids, context=context)[0]
            if value == 'folder':
                trip_import_folder = eval(company_proxy.trip_import_folder)
                return os.path.expanduser(os.path.join(*trip_import_folder))
            elif value == 'file': 
                trip_todo_file = eval(company_proxy.trip_todo_file)
                return os.path.expanduser(os.path.join(*trip_todo_file))
            else: # 'delete': 
                trip_delete_folder = eval(company_proxy.trip_delete_folder)
                return os.path.expanduser(os.path.join(*trip_delete_folder))                
        except:
            _logger.error(_("Error trying to read EDI folder"))
        return False
        
    _columns = {
        'trip_import_folder': fields.char(
            'Trip import folder', size=150, required=False, readonly=False, 
            help="Tuple value, like: ('~', 'etl', 'edi')"),
        'trip_delete_folder': fields.char(
            'Trip delete folder', size=150, required=False, readonly=False, 
            help="Tuple value, like: ('~', 'etl', 'edi', 'removed')"),
        'trip_todo_file': fields.char(
            'Trip TODO file', size=150, required=False, readonly=False, 
            help="File export where indicate TODO element, used by import "
                "file script for force some future importation order. "
                "Write a tuple, like: ('~', 'etl', 'export', 'todo.txt')"),
        }
        
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
