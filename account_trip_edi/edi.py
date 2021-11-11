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
import shutil
from openerp.osv import osv, orm, fields
from datetime import datetime, timedelta
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT,
    DEFAULT_SERVER_DATETIME_FORMAT, DATETIME_FORMATS_MAP, float_compare)
import openerp.addons.decimal_precision as dp
from openerp.tools.translate import _
import pickle


_logger = logging.getLogger(__name__)


class trip_import_edi_wizard(orm.Model):
    """ EDI file present in folder
    """
    _name = 'trip.edi.line'
    _description = 'EDI import line'
    _order = 'timestamp'

    # --------------
    # Server Action:
    # --------------
    def load_edi_list(self, cr, uid, ids, context=None):
        """ Refresh button for load EDI file list in wizard
        """
        # ---------------------------------------------------------------------
        #                        Common function:
        # ---------------------------------------------------------------------
        def ascii_check3(value):
            """ Try to remove not ascii char (replaced with #)
            """
            try:
                value.decode("utf8") # test for raise error
                return value
            except:
                # remove char not ascii
                v = ""
                for char in value:
                    try:
                        char.decode("utf8")
                        v += char
                    except:
                        v += "#" # replaced
                return v

        def ascii_check(value):
            value = value or ''
            res = ''
            for c in value:
                if ord(c) < 127:
                    res += c
                else:
                    res += '#'
            # Particular case:
            res = res.replace('###', '') # Error (file start with wrong char!)
            return res.replace('##', '#')
            #return res

        # ---------------------------------------------------------------------
        #                  Main code (common part)
        # ---------------------------------------------------------------------
        edi_company_pool = self.pool.get('edi.company')
        partner_pool = self.pool.get('res.partner')

        today = datetime.now()

        # Log operation:
        log_file = open(os.path.expanduser('~/refresh.edi.log'), 'a')
        log_file.write('%s. Inizio caricamento EDI, ID Utente: %s\n' % (
            today, uid,
            ))
        log_file.close()

        order_info = {
            'create': {},  # last numer created
            'deleting': [],  # list of order to deleting
            'anomaly': [],  # list order to delete without create (warning)
            }

        recursion = {}

        # Check period for importation (particular case)
        if today.weekday() in (3, 4, 5):
            reference_date = (today + timedelta(days=5)).strftime(
                DEFAULT_SERVER_DATE_FORMAT)
        else:
            reference_date = (today + timedelta(days=3)).strftime(
                DEFAULT_SERVER_DATE_FORMAT)

        # Delete all previous:
        # TODO >> force single company importation?
        # If we create a wizard for select only one company:
        line_ids = self.search(cr, uid, [], context=context)
        try:
            self.unlink(cr, uid, line_ids, context=context)
        except:
            pass # No comunication of error

        # Load destination dict:
        destination_not_found = []

        # ---------------------------------------------------------------------
        #                      Different for company
        # ---------------------------------------------------------------------
        # Read company to import:
        edi_company_ids = edi_company_pool.search(cr, uid, [
            ('import', '=', True)], context=context)
        for company in edi_company_pool.browse(
                cr, uid, edi_company_ids, context=context):
            # Load object for use the same function name where needed:
            parametrized = self.pool.get(company.type_importation_id.object)
            _logger.warning('Reading %s...' % company.name)

            # Normal trace:
            trace = parametrized.trace

            # Structured trace (in flat file not present):
            try:
                structured = parametrized.structured or {}
            except:
                structured = False
            try:
                start_structure = parametrized.start_structure or 0
            except:
                start_structure = 0

            forced_list = edi_company_pool.load_forced(
                cr, uid, company.id, context=context)

            # Get folder path:
            path_in = edi_company_pool.get_trip_import_edi_folder(
                cr, uid, company.id, context=context)

            if not path_in:
                pass  # TODO comunicate error

            file_list = []
            try:
                # Sort correctly the files:
                for file_in in [
                        f for f in os.listdir(path_in) if os.path.isfile(
                            os.path.join(path_in, f))]:
                    file_list.append((
                        parametrized.get_timestamp_from_file(file_in, path_in),
                        file_in,
                        ))
                file_list.sort()

                # Print list of sorted files for logging the operation:
                for ts, file_in in file_list:
                    _logger.info('Read file: %s' % file_in)

                    # Reset parameter for destination code:
                    supplier_facility = ""
                    supplier_cost = ""
                    supplier_site = ""
                    destination_description = ""
                    # destination = ""
                    # deadline = False
                    # date = False

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

                    start = True # not structured (read header only first line)
                    # TODO load elements in importing state (depend on date)
                    if mode_type == 'delete':
                        # Short read (get info from 1st line only)
                        line = fin.readline()

                        # TODO check structured type! (for now not important)
                        # Read fields:
                        number = parametrized.format_string(
                            line[trace['number'][0]:trace['number'][1]])
                        date = parametrized.format_date(
                            line[trace['date'][0]:trace['date'][1]])
                        deadline = parametrized.format_date(
                            line[trace['deadline'][0]:trace['deadline'][1]])
                        # NOTE: removed for color test on OpenERP (instead of
                        # have all grey
                        # if deadline < reference_date: # Next importation
                        #    mode_type = 'importing'

                        customer = False
                        destination = False

                    else: # create
                        for line in fin:
                            # Check if line is cancel
                            if parametrized.is_an_invalid_row(line):
                                continue # Line cancel

                            line = ascii_check(line)
                            # -------------------------------------------------
                            #                       HEADER
                            # -------------------------------------------------
                            line_type = line[0: start_structure]  # for struct.
                            if structured:
                                # ---------------------------------------------
                                #                 STRUCTURED
                                # ---------------------------------------------
                                if start: # Part only one:
                                    start = False
                                    # TODO Extra html header not present here!!
                                    # Only HTML header for structure
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

                                if structured['date'] == line_type:
                                    date = parametrized.format_date(
                                        line[
                                            trace['date'][0]:
                                            trace['date'][1]])
                                if structured['deadline'] == line_type:
                                    deadline = parametrized.format_date(
                                        line[
                                            trace['deadline'][0]:
                                            trace['deadline'][1]])
                                if structured['number'] == line_type:
                                    number = parametrized.format_string(
                                        line[
                                            trace['number'][0]:
                                            trace['number'][1]])
                                if structured['customer'] == line_type:
                                    customer = parametrized.format_string(
                                        line[
                                            trace['customer'][0]:
                                            trace['customer'][1]])

                                # Read all destination code (max 3 parts):
                                # NOTE: All 3 parts stay on same line (for now)
                                if structured[
                                        'destination_facility'] == line_type:
                                    supplier_facility = \
                                        parametrized.format_string(line[
                                            trace['destination_facility'][0]:
                                            trace['destination_facility'][1]])
                                    supplier_cost = parametrized.format_string(
                                        line[
                                            trace['destination_cost'][0]:
                                            trace['destination_cost'][1]])
                                    supplier_site = parametrized.format_string(
                                        line[
                                            trace['destination_site'][0]:
                                            trace['destination_site'][1]])
                                    destination_description = parametrized.format_string(line[
                                        trace['destination_description'][0]:
                                        trace['destination_description'][1]])
                                    destination = parametrized.get_destination(
                                        supplier_facility,
                                        supplier_cost,
                                        supplier_site,
                                        )

                            else:
                                # ---------------------------------------------
                                #            NOT STRUCTURED HEADER
                                # ---------------------------------------------
                                if start: # header value (only one)
                                    start = False

                                    # Read fields
                                    date = parametrized.format_date(
                                        line[
                                            trace['date'][0]:
                                            trace['date'][1]])
                                    deadline = parametrized.format_date(
                                        line[
                                            trace['deadline'][0]:
                                            trace['deadline'][1]])
                                    number = parametrized.format_string(
                                        line[
                                            trace['number'][0]:
                                            trace['number'][1]])
                                    customer = parametrized.format_string(
                                        line[
                                            trace['customer'][0]:
                                            trace['customer'][1]])

                                    # Read all destination code (max 3 parts):
                                    supplier_facility = parametrized.format_string(line[
                                        trace['destination_facility'][0]:
                                        trace['destination_facility'][1]])
                                    supplier_cost = parametrized.format_string(line[
                                        trace['destination_cost'][0]:
                                        trace['destination_cost'][1]])
                                    supplier_site = parametrized.format_string(line[
                                        trace['destination_site'][0]:
                                        trace['destination_site'][1]])
                                    destination_description = parametrized.format_string(line[
                                        trace['destination_description'][0]:
                                        trace['destination_description'][1]])
                                    destination = parametrized.get_destination(
                                        supplier_facility,
                                        supplier_cost,
                                        supplier_site,
                                        )

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

                            # -------------------------------------------------
                            #                      DETAILS:
                            # -------------------------------------------------
                            # Common part:
                            if not structured or structured[ # test w/art. code
                                   'detail_code'] == line_type:
                                html += """
                                    <tr>
                                         <td>&nbsp;%s&nbsp;</td>
                                         <td>&nbsp;%s&nbsp;</td>
                                         <td>&nbsp;%s&nbsp;</td>
                                         <td>&nbsp;%s&nbsp;</td>
                                         <td>&nbsp;%s&nbsp;</td>
                                         <td>&nbsp;%s&nbsp;</td>
                                     </tr>""" % (
                                         parametrized.format_string(
                                             line[
                                                 trace['detail_code'][0]:
                                                 trace['detail_code'][1]]),
                                         parametrized.format_string(
                                         line[
                                             trace[
                                                 'detail_description'][0]:
                                             trace[
                                                 'detail_description'][1]]
                                                 ),
                                         parametrized.format_string(
                                             line[
                                                 trace['detail_um'][0]:
                                                 trace['detail_um'][1]]),
                                         parametrized.format_float(
                                             line[
                                                 trace['detail_quantity'][0]:
                                                 trace['detail_quantity'][1]]),
                                         parametrized.format_float(
                                             line[
                                                 trace['detail_price'][0]:
                                                 trace['detail_price'][1]]),
                                         parametrized.format_float(
                                             line[
                                                 trace['detail_total'][0]:
                                                 trace['detail_total'][1]]),
                                         )
                        html += "</table>"  # TODO if empty??
                    fin.close()

                    # Create file list
                    # TODO old code: Read from file
                    # timestamp = datetime.fromtimestamp(ts).strftime(
                    #        DEFAULT_SERVER_DATETIME_FORMAT + ".%f" )
                    destination_id = parametrized.get_destination_id(
                        cr, uid, supplier_facility, supplier_cost,
                        supplier_site)

                    # Remember destination not fount
                    if not destination_id and (
                            destination_id not in destination_not_found):
                        destination_not_found.append(destination)

                    data_line = {
                        'name': file_in,
                        'timestamp': ts,
                        'deadline': deadline,
                        'date': date,
                        'number': number,
                        'customer': customer,
                        'destination': destination,
                        'destination_id': destination_id,
                        'destination_description': destination_description,
                        'company_id': company.id,
                        'type': mode_type,
                        'information': html,
                        'priority': parametrized.get_priority(
                            cr, uid, file_in),
                        }
                    line_id = self.create(
                        cr, uid, data_line, context=context)

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
                        destination_not_found, ))
            except:
                _logger.error("Generic error: %s" % (sys.exc_info(), ))

        # Update recursion informations (write totals recursions):
        for key in recursion:
            total, record_ids = recursion[key]
            self.write(cr, uid, record_ids, {
                'recursion': total,
                }, context=context)

        # TODO parametrize:
        # Update type informations (for create-delete-recreate management):
        for key in order_info:
            if key == 'deleting':
                if order_info['deleting']:
                    self.write(cr, uid, order_info['deleting'], {
                        'type': 'deleting',
                        }, context=context)
            elif key == 'anomaly':
                if order_info['anomaly']:
                    self.write(cr, uid, order_info['anomaly'], {
                        'type': 'anomaly',
                        }, context=context)
            else: # create
                pass

        # Log operation:
        log_file = open(os.path.expanduser('~/refresh.edi.log'), 'a')
        log_file.write('%s. Fine caricamento EDI, ID Utente: %s\n' % (
            today, uid,
            ))
        log_file.close()

        return {
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'trip.edi.line',
            'type': 'ir.actions.act_window',
            'context': {'search_default_type_create': 1},
            }

    # -------------
    # Button event:
    # -------------
    def action_null(self, cr, uid, ids, context=None):
        """ Do Nothing
        """
        return True

    # Utility (for button):
    def force_import_common(self, cr, uid, ids, force=True, context=None):
        """ Common procedure for 2 botton for force and unforce
        """
        # Read company elements:
        line_proxy = self.browse(cr, uid, ids, context=context)[0]
        company_id = line_proxy.company_id.id
        # Read transit file:
        edi_pool = self.pool.get("edi.company")
        forced_list = edi_pool.load_forced(
            cr, uid, company_id, context=context)

        # Save if not present:
        file_proxy = self.browse(cr, uid, ids, context=context)[0]
        modified = False
        log_file = open(os.path.join(
            os.path.expanduser('~'),
            'forced_edi_order.log',
            ), 'a')

        if force: # add to pickle list
            if file_proxy.name not in forced_list:
                forced_list.append(file_proxy.name)
                modified = True
            state = 'forced'

            # Log forced:
            log_file.write('[INFO] %s. USER: %s FORCED: %s RIF: %s\r\n' % (
                datetime.now(), uid, file_proxy.name, file_proxy.number))

        else:     # remove from pickle list
            if file_proxy.name in forced_list:
                forced_list.remove(file_proxy.name)  # TODO only one? yes!?
                modified = True
            state = 'create'

            # Log forced:
            log_file.write('[INFO] %s. USER: %s UNFORCED: %s RIF: %s\r\n' % (
                datetime.now(), uid, file_proxy.name, file_proxy.number))

        log_file.close()
        if modified:  # only if changed:
            edi_pool.store_forced(
                cr, uid, company_id, forced_list, context=context)

        # Set record to importing
        self.write(cr, uid, ids, {
            'type': state, }, context=context)
        return True

    def force_import(self, cr, uid, ids, context=None):
        """ Force importation of order (using pickle file)
        """
        return self.force_import_common(
            cr, uid, ids, force=True, context=context)

    def unforce_import(self, cr, uid, ids, context=None):
        """ Unforce importation of order (using pickle file)
        """
        return self.force_import_common(
            cr, uid, ids, force=False, context=context)

    def delete_order(self, cr, uid, ids, context=None):
        """ Move order in delete folder
        """
        comment = ''
        try:
            company_id = self.browse(
                cr, uid, ids, context=context)[0].company_id.id
            edi_pool = self.pool.get('edi.company')
            origin_folder = edi_pool.get_trip_import_edi_folder(
                    cr, uid,
                    company_id,
                    value='folder',
                    context=context)
            delete_folder = edi_pool.get_trip_import_edi_folder(
                    cr, uid,
                    company_id,
                    value='delete',
                    context=context)
            if not all((origin_folder, delete_folder)):
                raise osv.except_osv(
                    _('Error'),
                    _('Set in EDI Company view: origin and delete folder!'))

            item_proxy = self.browse(cr, uid, ids, context=context)[0]
            f_in = os.path.join(origin_folder, item_proxy.name)
            f_out = os.path.join(delete_folder, item_proxy.name)
            try:
                shutil.move(f_in, f_out)
                comment = 'File moved'
            except:
                # 1. Delete
                try:
                    os.remove(f_out)
                except:
                    pass

                # 1. Move
                try:
                    shutil.move(f_in, f_out)
                    comment = 'Moved after delete existent!'
                except:
                    comment = 'Error moving deleted file!'
                    _logger.error('Error moving deleted file!')

            self.unlink(cr, uid, ids, context=context)

            # -----------------------------------------------------------------
            # Log deletion:
            # -----------------------------------------------------------------
            log_file = open(os.path.join(
                delete_folder, 'log', 'delete.log'), 'a')
            log_file.write('[INFO] %s. USER: %s FILE: %s RIF: %s [%s]\r\n' % (
                datetime.now(), uid, item_proxy.name, item_proxy.number,
                comment))
            log_file.close()
            return True
        except:
            raise osv.except_osv(
                _("Error"),
                _("Error deleting file %s") % (sys.exc_info(), ),
                )

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
        'destination_id': fields.many2one(
            'res.partner', 'Destination (internal)',
            readonly=True, domain=[('is_address', '=', True)],
            ondelete='set null'),
        'destination_description': fields.char('Destination description',
            size=100, readonly=True),
        'tour1_id': fields.related('destination_id','tour1_id',
            type='many2one',
            relation='trip.tour', string='Trip 1', store=True),
        'tour2_id': fields.related('destination_id','tour2_id',
            type='many2one',
            relation='trip.tour', string='Trip 2', store=True),
        'information': fields.text('Information',
            help='Short info about context of order (detail, destination'),
        'priority': fields.selection([
            ('low', 'Low'),
            ('normal', 'Normal'),
            ('high', 'High'),
            ], 'Priority'),
        'type': fields.selection([
            ('importing', 'To importing'),   # Next importation files
            ('anomaly', 'Delete (Anomaly)'),  # Delete, not found create before
            ('create', 'Create'),            # Create
            ('change', 'Change'),            # Change an order
            ('deleting', 'To delete'),       # Create, but delete before
            ('forced', 'To force'),          # Force to load next importation
            ('delete', 'Delete')], 'Type', required=True),  # To delete
        'recursion': fields.integer('Recursion')
        }

    _defaults = {
        'type': lambda *x: 'create',
        }


class res_partner(osv.osv):
    """ Add extra info for calculate waiting order for destination
    """
    _inherit = 'res.partner'

    # ---------------
    # Field function:
    # ---------------
    def _function_get_order_wait(self, cr, uid, ids, args=None, fields=None,
            context=None):
        """ Return number of active order if is a destination
        """
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


class edi_company_importation(orm.Model):
    """ This class elements are populated with extra modules:
        account_trip_edi_c*
    """
    _name = 'edi.company.importation'
    _description = 'EDI Company importation'

    _columns = {
        'name': fields.char('Importation type', size=20, required=True),
        'code': fields.char('Code', size=10),
        'object': fields.char('Object', size=64, required=True),
        'note': fields.char('Note'),
        }


class res_company(orm.Model):
    """ Add parameters fields
    """
    _inherit = 'res.company'

    _columns = {
        'edi_account_data': fields.char(
            'Cartella dati EDI', size=80, required=True,
            help='Cartella dove vengono esportati i dati del gestionale'
            ),
        }


class edi_company(orm.Model):
    """ Manage more than one importation depend on company
    """
    _name = 'edi.company'
    _description = 'EDI Company'

    # -------------------------------------------------------------------------
    #                             Utility function
    # -------------------------------------------------------------------------
    def get_trip_import_edi_folder(
            self, cr, uid, company_id, value='folder', context=None):
        """ Read parameter for default EDI folder (set up in company)
            value: 'folder' (default) folder of EDI in file
                   'file' for file used to pass forced list
                   'delete' for folder used for deletion elements
        """
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
        """ Store passed forced list pickle in a file (for company_id passed)
        """
        try:
            # Read EDI file for passed force list
            filename = self.get_trip_import_edi_folder(
                cr, uid, company_id, value='file', context=context)

            pickle.dump(forced_list, open(filename, 'wb'))
            return True
        except:
            return False

    def load_forced(self, cr, uid, company_id, context=None):
        """ Load list of forced from file (for company_id passed)
        """
        try:
            filename = self.get_trip_import_edi_folder(
                cr, uid, company_id, value='file', context=context)
            return pickle.load(open(filename, 'rb')) or []
        except:
            return []

    def _type_importation_selection(self, cr, uid, context=None):
        """ Empty without extra importation modules
        """
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
