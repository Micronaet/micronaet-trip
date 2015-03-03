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

class trip_import_edi_wizard(osv.osv_memory):
    ''' Read EDI folder and list all files
        TODO: now TS is get from file, before from OS datetime
             (leave the old code for backport)
    '''

    _name = 'trip.edi.wizard'
    _description = 'EDI import wizard'

    # -------------
    # Button event: 
    # -------------
    def load_edi_list(self, cr, uid, ids, context=None):
        ''' Refresh button for load EDI file list in wizard
        '''
        
        # ---------------------------------------------------------------------
        #                        Utility function:        
        # ---------------------------------------------------------------------
        def format_date(value):
            ''' EDI file date format YYYYMMDD
            '''
            return "%s-%s-%s" % (value[:4], value[4:6], value[6:8])

        def format_string(value):
            ''' EDI file string 
            '''
            return value.strip()
        
        # ---------------------------------------------------------------------
        #                  Main code (common part)
        # ---------------------------------------------------------------------
        edi_company_pool = self.pool.get('edi.company')
        partner_pool = self.pool.get('res.partner')
        line_pool = self.pool.get('trip.edi.line')

        order_info = {
            'create': {},   # last numer created
            'deleting': [], # list of order to deleting
            'anomaly': [],  # list order to delete without create (warning)
            }
            
        recursion = {}
        
        # Check period for importation (particular case)
        today = datetime.now()
        if today.weekday() in (3, 4, 5):
            reference_date = (today + timedelta(days=5)).strftime(
                DEFAULT_SERVER_DATE_FORMAT)
        else:
            reference_date = (today + timedelta(days=3)).strftime(
                DEFAULT_SERVER_DATE_FORMAT)
        
        # Delete all previous: 
        # TODO >> force single company importation?
        # If we create a wizard for select only one company:
        line_ids = line_pool.search(cr, uid, [], context=context)
        try:
            line_pool.unlink(cr, uid, line_ids, context=context)
        except:
            pass # No comunication of error        
        
        # Load destination dict:
        destination_not_found = []

        # ---------------------------------------------------------------------
        #                      Different for company
        # ---------------------------------------------------------------------
        # Read company to import:
        edi_company_ids = edi_company_tool.search(cr, uid, [
            ('import', '=', True)], context=context)

        for company in edi_company_pool.browse(
                cr, uid, edi_company_ids, context=context): 
       
            # Load object for use the same function name where needed:
            parametrized = self.pool.get(company.type_importation_id.object)
            
            trace = parametrized.trace
            
            forced_list = edi_company_pool.load_forced(
                cr, uid, company.id, context=context)

            # Get folder path:
            path_in = edi_company_pool.get_trip_import_edi_folder(
                cr, uid, company.id, context=context)
            
            if not path_in:
                pass # TODO comunicate error
            
            file_list = []
            try:
                # Sort correctly the files:       
                for file_in in [
                        f for f in os.listdir(path_in) if os.path.isfile(
                            os.path.join(path_in, f))]:            
                    file_list.append((
                        parametrized.get_timestamp_from_file(file_in), 
                        file_in,
                        ))
                file_list.sort()
                
                # Print list of sorted files for logging the operation:
                for ts, file_in in file_list:  
                    # Reset parameter for destination code:              
                    supplier_facility = ""
                    supplier_cost = ""
                    supplier_site = ""

                    # Open file for read informations:
                    fin = open(os.path.join(path_in, file_in), "r")
                    
                    # Type mode valutation:
                    mode_type = parametrized.get_state_of_file(
                        file_in, forced_list)
                    
                    html = """
                        <style>
                            .table_trip {
                                 border:1px 
                                 padding: 3px;
                                 solid black;
                           
                            .table_trip td {
                                 border:1px 
                                 solid black;
                                 padding: 3px;
                                 text-align: center;
                            }
                            .table_trip th {
                                 border:1px 
                                 solid black;
                                 padding: 3px;
                                 text-align: center;
                                 background-color: grey;
                                 color: white;
                            }
                        </style>
                        """
                    start = True

                    # TODO load elements in importing state (depend on date)
                    if mode_type == 'delete':
                        # Short read (get info from 1st line only) 
                        line = fin.readline()
                        
                        # Read fields:
                        number = format_string(
                            line[trace['number'][0]:trace['number'][1]])
                        date = format_date(
                            line[trace['date'][0]:trace['date'][1]])
                        deadline = format_date(
                            line[trace['deadline'][0]:trace['deadline'][1]])
                        if deadline < reference_date: # Next importation
                            mode_type = 'importing'
                            
                        customer = False
                        destination = False
                        
                    else: # create   
                        for line in fin:
                            if start: # header value (only one)
                                start = False

                                # Read fields
                                date = format_date(
                                    line[
                                        trace['date'][0]:
                                        trace['date'][1]])
                                deadline = format_date(
                                    line[
                                        trace['deadline'][0]:
                                        trace['deadline'][1]])
                                number = format_string(
                                    line[
                                        trace['number'][0]:
                                        trace['number'][1]])
                                customer = format_string(
                                    line[
                                        trace['customer'][0]:
                                        trace['customer'][1]])

                                # Read all destination code (max 3 parts):                                
                                supplier_facility = format_string(line[
                                        trace['destination_facility'][0]:
                                        trace['destination_facility'][1]])
                                supplier_cost = format_string(line[
                                        trace['destination_cost'][0]:
                                        trace['destination_cost'][1]])
                                supplier_site = format_string(line[
                                        trace['destination_site'][0]:
                                        trace['destination_site'][1]])
                                destination = parametrized.get_destination((
                                    supplier_facility, 
                                    supplier_cost, 
                                    supplier_site, 
                                    ))
                                
                                # Create an HMTL element for preview file:        
                                html += "<p>"
                                html += _("Date: %s<br/>") % date
                                html += _("Deadline: %s<br/>") % deadline
                                html += _("Destination: %s<br/>") % destination
                                html += _("Customer ref.: %s<br/>") % customer
                                html += "</p>"
                                html += _(
                                    """<table class='table_trip'>
                                       <tr>
                                           <th>Code</th>
                                           <th>Description</th>
                                           <th>UM</th>
                                           <th>Q.</th>
                                           <th>Price</th>
                                           <th>Total</th>
                                       </tr>""")
                            html += """
                                <tr>
                                     <td>%s</td>
                                     <td>%s</td>
                                     <td>%s</td>
                                     <td>%s</td>
                                     <td>%s</td>
                                     <td>%s</td>
                                 </tr>""" % (
                                     format_string(
                                         line[
                                             trace['detail_code'][0]:
                                             trace['detail_code'][1]]),
                                     format_string(
                                         line[
                                             trace['detail_description'][0]:
                                             trace['detail_description'][1]]),
                                     format_string(
                                         line[
                                             trace['detail_um'][0]:
                                             trace['detail_um'][1]]),
                                     format_string(
                                         line[
                                             trace['detail_quantity'][0]:
                                             trace['detail_quantity'][1]]),
                                     format_string(
                                         line[
                                             trace['detail_price'][0]:
                                             trace['detail_price'][1]]),
                                     format_string(
                                         line[
                                             trace['detail_total'][0]:
                                             trace['detail_total'][1]]),
                                     )
                        html += "</table>"  # TODO if empty??
                    fin.close()
                        
                    # Create file list
                    # TODO old code: Read from file
                    #timestamp = datetime.fromtimestamp(ts).strftime(
                    #        DEFAULT_SERVER_DATETIME_FORMAT + ".%f" )
                    destination_id = parametrize.get_destination_id(
                        self, supplier_facility, supplier_cost, supplier_site)
                    
                    # Remember destination not fount        
                    if not destination_id and (
                            destination_id not in destination_not_found): 
                        destination_not_found.append(destination)
                            
                    line_id = line_pool.create(cr, uid, {
                        'name': file_in,
                        'timestamp': ts,
                        'deadline': deadline,
                        'date': date,
                        'number': number,
                        'customer': customer,
                        'destination': destination,
                        'destination_id': destination_id,
                        'type': mode_type,
                        'information': html,
                        }, context=context)
                        
                    # Create record for test recursions:    
                    if number not in recursion:
                        recursion[number] = [1, [line_id]]
                    else:
                        recursion[number][0] += 1
                        recursion[number][1].append(line_id)

                    # TODO parametrize:
                    # Particular case for create-delete-recreate management:
                    if mode_type == 'create':
                        # last (for test delete)
                        order_info['create'][number] = line_id 
                    elif mode_type == 'delete':
                        if number in order_info['create']:                    
                            order_info['deleting'].append(
                                order_info['create'][number])
                        else:    
                            order_info['anomaly'].append(line_id)
                            
                if destination_not_found: 
                    _logger.warning(_('\n\nDestination not found: \n[%s]') % (
                        destination_not_found, )  )
            except:
                _logger.error("Generic error: %s" % (sys.exc_info(), ))
                

        # Update recursion informations (write totals recursions):
        for key in recursion:
            total, record_ids = recursion[key]
            line_pool.write(cr, uid, record_ids, {
                'recursion': total,
                }, context=context)
        
        # TODO parametrize:
        # Update type informations (for create-delete-recreate management):
        for key in order_info:
            if key == 'deleting':
                if order_info['deleting']:
                    line_pool.write(cr, uid, order_info['deleting'], {
                        'type': 'deleting',
                        }, context=context)
            elif key == 'anomaly':
                if order_info['anomaly']:
                    line_pool.write(cr, uid, order_info['anomaly'], {
                        'type': 'anomaly',
                        }, context=context)
            else: # create
                pass
                
        return {          
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'trip.edi.line',
            'type': 'ir.actions.act_window',
            'context': {'search_default_type_create': 1},
            }  

    _columns = {
        'note': fields.text('Importation note'),
        }
    
    _defaults = {
        'note': lambda *x: "Import EDI files in a manageable list",
        }
        
class trip_import_edi_wizard(orm.Model):
    ''' EDI file present in folder
    '''
    _name = 'trip.edi.line'
    _description = 'EDI import line'
    _order = 'timestamp'

    # -------------------
    # Override operation:
    # -------------------
    # TODO 
    '''def unlink(self, cr, uid, ids, context=None):
        """
        Delete only type != create (for duplicated records)
        (test also if user have right)    
        @param cr: cursor to database
        @param uid: id of current user
        @param ids: list of record ids to be removed from table
        @param context: context arguments, like lang, time zone
        
        @return: True on success, False otherwise
        """    
        if type(ids) not in (tuple, list):
            ids = [ids]
        
        #TODO: process before delete resource
        item_ids = self.search(cr, uid, ids, context=context)
        item_proxy = self.browse(cr, uid, item_ids, context=context)
        for item in item_proxy:
            if item.type in ('delete', 'deleting'): # only this can remove
                pass
                # TODO
                # Move file to history deleted elements folder:
                # Save log of operation                         
            else:
                try:
                    ids.remove(item.id) # Remove other elements (nothing to do)
                except:
                    pass # no error comunication    

        if ids:        
            res = super(trip_import_edi_wizard, self).unlink(
                cr, uid, ids, context=context)
        else:
            res = True        

        # TODO reload elements with wizard
        return res'''
    
    # -------------
    # Button event:
    # -------------
    # Utility (for button):
    def force_import_common(self, cr, uid, ids, force=True, context=None):
        ''' Common procedure for 2 botton for force and unforce
        '''
        # Read transit file:
        forced_list = self.load_forced(cr, uid, context=context)
        
        # Save if not present:
        file_proxy = self.browse(cr, uid, ids, context=context)[0]
        modified = False
        if force: # add to pickle list
            if file_proxy.name not in forced_list:
                forced_list.append(file_proxy.name)
                modified = True
            state = 'forced'
        else:     # remove from pickle list
            if file_proxy.name in forced_list:
                forced_list.remove(file_proxy.name)  # TODO only one? yes!?
                modified = True
            state = 'create'                
        if modified: # only if changed:
            self.store_forced(cr, uid, forced_list, context=context)
            
        # Set record to importing    
        self.write(cr, uid, ids, {
            'type': state, }, context=context)
        return True
       
    def force_import(self, cr, uid, ids, context=None):
        ''' Force importation of order (using pickle file)
        '''
        return self.force_import_common(
            cr, uid, ids, force=True, context=context)

    def unforce_import(self, cr, uid, ids, context=None):
        ''' Unforce importation of order (using pickle file)
        '''
        return self.force_import_common(
            cr, uid, ids, force=False, context=context)

    def delete_order(self, cr, uid, ids, context=None):
        ''' Move order in delete folder
        '''
        # TODO parametrize company_id
        try:
            company_pool = self.pool.get('res.company')
            origin_folder = company_pool.get_trip_import_edi_folder(
                    cr, uid, value='folder', context=context)
            delete_folder = company_pool.get_trip_import_edi_folder(
                    cr, uid, value='delete', context=context)
            if not all((origin_folder, delete_folder)):
                raise osv.except_osv(
                    _("Error"), 
                    _("Set in Company view: origin and delete folder!"))  

            item_proxy = self.browse(cr, uid, ids, context=context)[0]
            os.rename(
                os.path.join(origin_folder, item_proxy.name),
                os.path.join(delete_folder, item_proxy.name),
                )
            return self.unlink(cr, uid, ids, context=context)    
        except:
            raise osv.except_osv(
                _("Error"), 
                _("Error deleting file %s") % (sys.exc_info(), ),
                )            
            return False    
    
    _columns = {
        'name': fields.char('Name', size=80, required=True, readonly=True),
        'timestamp': fields.char('Timestamp', size=30, help='Arriving order'),
        'date': fields.date('Date'),
        'deadline': fields.date('Deadline'),
        'number': fields.char('Reference', size=20, readonly=True),        
        'customer': fields.char('Customer', size=100, readonly=True),
        'destination': fields.char('Destination (customer)', size=110, 
            readonly=True),
        'company_id':fields.many2one('edi.company', 'Company', required=True),
        'destination_id': fields.many2one('res.partner', 
            'Destination (internal)', 
            readonly=True, domain=[('is_address', '=', True)],
            ondelete='set null'),
        'tour1_id': fields.related('destination_id','tour1_id', 
            type='many2one', 
            relation='trip.tour', string='Trip 1', store=True),
        'tour2_id': fields.related('destination_id','tour2_id', 
            type='many2one', 
            relation='trip.tour', string='Trip 2', store=True),
        'information': fields.text('Information', 
            help='Short info about context of order (detail, destination'),
        'type': fields.selection([
            ('importing', 'To importing'),   # Next importation files
            ('anomaly', 'Delete (Anomaly)'), # Delete, not found create before
            ('create', 'Create'),            # Create
            ('change', 'Change'),            # Change an order 
            ('deleting', 'To delete'),       # Create, but delete before
            ('forced', 'To force'),          # Force to load next importation
            ('delete', 'Delete')], 'Type', required=True), # To delete
        'recursion': fields.integer('Recursion')
        }
        
    _defaults = {
        'type': lambda *x: 'create',
        }

class res_partner(osv.osv):
    ''' Add extra info for calculate waiting order for destination
    '''
    _inherit = 'res.partner'
    
    # ---------------
    # Field function:
    # ---------------
    def _function_get_order_wait(self, cr, uid, ids, args=None, fields=None, 
            context=None):
        ''' Return number of active order if is a destination
        '''
        res = {}
        for partner in self.browse(cr, uid, ids, context=context):        
            if partner.is_address:
                res[partner.id] = len(partner.destination_order_waiting_ids)
            else:
                res[partner.id] = 0
        return res   
        
    _columns = { 
        'destination_order_waiting_ids': fields.one2many(
            'trip.edi.line', 'destination_id', 'Destination order wait'),             
        'active_order_wait': fields.function(
            _function_get_order_wait, method=True, 
            type='integer', string='# Order wait', store=False),            
        }    

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
