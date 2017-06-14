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
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, DATETIME_FORMATS_MAP, float_compare)
import openerp.addons.decimal_precision as dp
from openerp.tools.translate import _
import pickle


_logger = logging.getLogger(__name__)

# TEMP REMOVE vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv
"""class res_company(osv.osv):
    ''' Add extra parameters for importation
    '''
    _inherit = 'res.company'
        
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
        }"""
        
class edi_company_importation(orm.Model):
    ''' This class elements are populated with extra modules:
        account_trip_edi_c*
    '''    
    _name = 'edi.company.importation'
    _description = 'EDI Company importation'
    
    _columns = {
        'name': fields.char('Importation type', size=20, required=True),
        'code': fields.char('Code', size=10),
        'object': fields.char('Object', size=64, required=True),
        'note': fields.char('Note'),
        }

class edi_company(orm.Model):
    ''' Manage more than one importation depend on company
    '''    
    _name = 'edi.company'
    _description = 'EDI Company'
    
    # -------------------------------------------------------------------------
    #                             Utility function
    # -------------------------------------------------------------------------
    def get_trip_import_edi_folder(self, cr, uid, company_id, value='folder', 
            context=None):
        ''' Read parameter for default EDI folder (set up in company)
            value: 'folder' (default) folder of EDI in file
                   'file' for file used to pass forced list
                   'delete' for folder used for deletion elements
        '''        
        try:
            company_proxy = self.browse(
                cr, uid, company_id, context=context)
                
            if value == 'folder':
                return os.path.expanduser(company_proxy.trip_import_folder)
            elif value == 'file': 
                return os.path.expanduser(company_proxy.trip_todo_file)
            else: # 'delete': 
                return os.path.expanduser(company_proxy.trip_delete_folder)                
        except:
            _logger.error(_("Error trying to read EDI folder"))
        return False

    def store_forced(self, cr, uid, company_id, forced_list, context=None):
        ''' Store passed forced list pickle in a file (for company_id passed) 
        '''
        try:
            # Read EDI file for passed force list
            filename = self.get_trip_import_edi_folder(
                cr, uid, company_id, value='file', context=context)

            pickle.dump(forced_list, open(filename, "wb" ) )
            return True
        except:
            return False    

    def load_forced(self, cr, uid, company_id, context=None):
        ''' Load list of forced from file (for company_id passed)
        '''
        try:
            filename = self.get_trip_import_edi_folder(
                cr, uid, company_id, value='file', context=context)
            return pickle.load(open(filename, 'rb')) or []
        except: 
            return []

    def _type_importation_selection(self, cr, uid, context=None):
        ''' Empty without extra importation modules
        '''
        return []

    _columns = {
        'name': fields.char('Code', size=15, required=True),
        'partner_id': fields.many2one(
            'res.partner', 'Partner', required=False),
        'import':fields.boolean('Import'),    
        'type_importation_id': fields.many2one(
            'edi.company.importation', 'Importation type', required=True),
            
        # Folders:
        'trip_import_folder': fields.char(
            'Trip import folder', size=150, required=True,
            help="Tuple value, like: ('~', 'etl', 'edi')"),
        'trip_delete_folder': fields.char(
            'Trip delete folder', size=150, required=True,
            help="Tuple value, like: ('~', 'etl', 'edi', 'removed')"),
        'trip_todo_file': fields.char(
            'Trip TODO file', size=150, required=True, 
            help="File export where indicate TODO element, used by import "
                "file script for force some future importation order. "
                "Write a tuple, like: ('~', 'etl', 'export', 'todo.txt')"),
        }
        
    _defaults = {
        'import': lambda *x: False,
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
