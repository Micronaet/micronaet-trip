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
import pdb
import sys
import netsvc
import logging
from openerp.osv import osv, orm, fields
from datetime import datetime, timedelta
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, \
    DEFAULT_SERVER_DATETIME_FORMAT, DATETIME_FORMATS_MAP, float_compare
import openerp.addons.decimal_precision as dp
from openerp.tools.translate import _


_logger = logging.getLogger(__name__)


class ResCompany(orm.Model):
    """ Class Company for operation
    """
    _inherit = 'res.company'

    def open_log_detail(self, cr, uid, ids, context=None):
        """ Open log import error
        """
        model_pool = self.pool.get('ir.model.data')
        view_id = model_pool.get_object_reference(
            cr, uid,
            'account_trip',
            'res_company_trip_log_error_view_form')[1]

        return {
            'type': 'ir.actions.act_window',
            'name': _('Errore importazione'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': ids[0],
            'res_model': 'res.company',
            'view_id': view_id,
            'views': [(view_id, 'form')],
            'domain': [],
            'context': context,
            'target': 'new',
            'nodestroy': False,
            }

    def clean_all_order(self, cr, uid, ids, context=None):
        """ Clean all order: daily operation before start work
        """
        # Clean previous error:
        self.write(cr, uid, ids, {
            'trip_master_error': False,
            'trip_master_warning': False,
        }, context=context)
        return self.pool.get('trip.order').clean_all_order(
            cr, uid, ids, context=context)

    def import_all_order(self, cr, uid, ids, context=None):
        """ Re import order: daily operation before start work
        """
        return self.pool.get('trip.order').schedule_import_trip_order(
            cr, uid, context=context)

    _columns = {
        'trip_keep_trip': fields.integer(
            'Conserva viaggi per', required=True,
            help='La cancellazione giornaliera dei viaggi parte da X giorni '
                 'precedenti',
        ),
        'trip_master_error': fields.text('Log errore viaggi'),
        'trip_master_warning': fields.text('Log warning viaggi'),
    }

    _defaults = {
        'trip_keep_trip': lambda *x: 2,
    }


class trip_tour(orm.Model):
    """ Class for manage Tours
    """
    _name = 'trip.tour'
    _description = 'Trip tour'

    # --------
    # Utility:
    # --------
    def search_tour(self, cr, uid, code, with_creation=False, context=None):
        """ Search code elements and eventually create one if request
        """
        if not code:
            return False

        tour_ids = self.search(cr, uid, [
            ('name', '=', code)], context=context)
        if tour_ids:
            return tour_ids[0]
        if with_creation:
            return self.create(cr, uid, {
                'name': code,
                'description': _("Tour code: %s") % code,
                'note': _("Automatic created"),
                }, context=context)

        _logger.warning("Tour code not found: %s" % code)
        return False

    _columns = {
        'name': fields.char('Code', size=10, required=True),
        'description': fields.char('Description', size=100),
        'note': fields.text('Note'),
        'obsolete': fields.boolean('Obsolete'),
        }


class trip_vector_camion(orm.Model):
    """ Trip vector camion
    """
    _name = 'trip.vector.camion'
    _description = 'Trip vector camion'
    _order = 'name'

    _columns = {
        'name': fields.char('Description', size=64, required=True),
        'vector_id': fields.many2one(
            'res.partner', 'Vector',
            required=True,
            domain =[('is_vector', '=', True)],
            ondelete='cascade'),
        'max_load': fields.float(
            'Max load', digits=(16, 2), required=True),
        'note': fields.text('Note'),
        }


class trip_trip(orm.Model):
    """ Class for manage Trip informations
    """
    _name = 'trip.trip'
    _description = 'Trip'
    _rec_name = 'tour_id'

    def print_trip_one(self, cr, uid, ids, context=None):
        """ Print trip order
        """
        # datas = {'multi': 1}
        return {
            'model': 'trip.trip',
            'type': 'ir.actions.report.xml',
            'report_name': 'trip_trip_report',
            # 'datas': datas,
            'res_id': context.get('active_id', ids[0]),
            'context': context,
        }

    # -------------------
    # On change function:
    # -------------------
    def onchange_camion_id(self, cr, uid, ids, camion_id, context=None):
        """ On change camion update max load
        """
        res = {'value': {}}
        if not camion_id:
           return res
        res['value']['max_load'] = self.pool.get('trip.vector.camion').browse(
            cr, uid, camion_id, context=context).max_load or 0.0
        return res

    # ------------------
    # Override function:
    # ------------------
    def name_get(self, cr, user, ids, context=None):
        """
        Return a list of tuples contains id, name.
        result format : {[(id, name), (id, name), ...]}

        @param cr: cursor to database
        @param user: id of current user
        @param ids: list of ids for which name should be read
        @param context: context arguments, like lang, time zone

        @return: returns a list of tuples contains id, name
        """
        res = []
        for item in self.browse(cr, user, ids, context=context):
            # if context.get('name_extra_info', False):
            name = _("%s (%s) >> %s [Tot. %s] ") % (
                item.tour_id.name,
                item.date,
                item.camion_id.name,
                item.prevision_load,
            )
            #else:
            #    name = "%s (%s) >> %s" % (
            #        item.tour_id.name,
            #        item.date,
            #        item.camion_id.name,
            #        )
            res.append((item.id, name))
        return res

    # ----------------
    # Fields function:
    # ----------------
    def _get_totals(self, cr, uid, ids, fields=None, args=None, context=None):
        """ Calculate totals for prevision and current (from order elements)
        """
        res = {}
        for item in self.browse(cr, uid, ids, context=context):
            res[item.id] = {}
            res[item.id]['prevision_load'] = 0.0  # Total preview
            res[item.id]['current_load'] = 0.0  # todo no tot. current/prev.
            res[item.id]['total_delivery'] = 0  # Total of delivery
            for order in item.order_ids:
                res[item.id][
                    'prevision_load'] += order.prevision_load
                res[item.id][
                    'current_load'] += order.prevision_load
                # order.current_load or
                res[item.id][
                    'total_delivery'] += 1
        return res

    def _get_tour_code(self, cr, uid, ids, name, args, context=None):
        """ First letter of tour code
        """
        res = {}
        for item in self.browse(cr, uid, ids, context=context):
            res[item.id] = item.tour_id.name[:1] if item.tour_id else False
        return res

    def _search_tour_code(self, cr, uid, obj, name, args, context=None):
        """ Search first letter of tour code
        """
        res = [('id', '=', '0')]
        if not len(args):
            return res

        tour_ids = self.pool.get('trip.tour').search(cr, uid, [
            ('name', 'ilike', args[0][2])], context=context)
        if not tour_ids:
            return res
        res = [('tour_id', 'in', tour_ids)]
        return res

    _columns = {
        'date': fields.date('Date'),

        # 'name': fields.char('Code', size=10, required=True),
        'description': fields.char('Description', size=100),
        'note': fields.text('Note'),
        'good_collection': fields.text('Good collection'),

        'max_load': fields.float('Max load', digits=(16, 2)),

        # Related for totals:
        'prevision_load': fields.function(
            _get_totals, method=True,
            type='float', digits=(16, 2), string='Prevision load',
            store=False, multi='total'),
        'current_load': fields.function(
            _get_totals, method=True, type='float',
            digits=(16, 2), string='Current load', store=False, multi='total'),
        'total_delivery': fields.function(
            _get_totals, method=True,
            type='integer', string='Total delivery', store=False,
            multi='total'),

        'tour_id': fields.many2one('trip.tour', 'Tour',
            required=True,
            ondelete='set null'),
        'tour_code': fields.function(
            _get_tour_code,
            fnct_search=_search_tour_code,
            type="char",
            method=True,
            string="Tour code",
            store=False,
            ),

        'camion_id': fields.many2one('trip.vector.camion', 'Camion',
            ondelete='set null'),
        'state': fields.selection([ # TODO remove
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('history', 'History'),
            ('cancel', 'Cancel'),
            ], 'State', required=True),
        }

    _defaults = {
        'date': datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT),
        'state': lambda *x: 'draft',
        }


class trip_order(orm.Model):
    """ Trip order (loaded from accounting)
        The list is the current order opened
    """
    _name = 'trip.order'
    _description = 'Trip order'
    _order = 'trip_id, sequence'

    def unlink_order(self, cr, uid, ids, context=None):
        """ Unlink order to trip (order not deleted)
        """
        return self.write(cr, uid, ids, {'trip_id': False}, context=context)

    def clean_all_order(self, cr, uid, ids, context=None):
        """ Clean all order: daily operation before start work
        """
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        from_days = user.company_id.trip_keep_trip

        # Clean all trip:
        trip_pool = self.pool.get('trip.trip')
        from_date = (datetime.now() - timedelta(days=from_days)).strftime(
            DEFAULT_SERVER_DATE_FORMAT)
        trip_ids = trip_pool.search(cr, uid, [
            ('tour_id.keep', '=', False),  # Delete tour not "keep"
            ('date', '<', from_date),
        ], context=context)
        trip_pool.unlink(cr, uid, trip_ids, context=context)
        _logger.warning('Removed %s trip [<%s, not keep]' % (
            len(trip_ids), from_days))

        # Clean all order: (for start new day trip)
        order_ids = self.search(cr, uid, [
            ('trip_id', '=', False),  # Order not linked with trip
        ], context=context)
        _logger.warning('Removed %s order' % len(order_ids))
        return self.unlink(cr, uid, order_ids, context=context)

    # -------------------------------------------------------------------------
    # Schedule event:
    # -------------------------------------------------------------------------
    def schedule_import_trip_order(self, cr, uid, context=None):
        """ Import order for manage trip
        """
        def log_message(message, error_block, error=True, verbose=True):
            """ Log error
            """
            message_newline = '%s\n' % message
            if error:
                error_block['master'] += message_newline
            else:
                error_block['warning'] += message_newline
            error_block['record'] += message_newline
            if verbose:
                _logger.error('[%s] %s' % (
                    'ERROR' if error else 'WARNING', message))
            return True

        try:
            # Parameter:
            idem = '07.00002'

            # Pool object:
            company_pool = self.pool.get('res.company')
            partner_pool = self.pool.get('res.partner')
            sql_pool = self.pool.get('micronaet.accounting')
            tour_pool = self.pool.get('trip.tour')

            user = self.pool.get('res.users').browse(
                cr, uid, uid, context=context)
            company_id = user.company_id.id

            # Connect to SQL:
            company_proxy = company_pool.get_from_to_dict(
                cr, uid, context=context)
            if not company_proxy:
                _logger.error('Company parameters was not set up!')
                return False

            _logger.info('Start import SQL: Trip order')
            cursor = sql_pool.get_trip_order(
                cr, uid, context=context)

            if not cursor:
                _logger.error("Unable to connect, no order importation!")
                return False

            # Consider all removed:
            cr.execute('update trip_order set removed=\'t\';')

            # Start importation order:
            order_reference = {}
            i = 0
            error_block = {
                'master': '',
                'warning': '',
                'record': '',
            }
            for record in cursor:
                try:
                    i += 1
                    if not i % 100:
                        _logger.info(
                            'Import destination code: %s record updated!' % i)

                    error_block['record'] = ''
                    name = sql_pool.KEY_OC_FORMAT % record
                    number = str(record['NGL_DOC'])
                    date = record['DTT_DOC'].strftime(
                        DEFAULT_SERVER_DATE_FORMAT)
                    tour_name = record['CDS_NOTE'].strip()
                    tour_id = tour_pool.search_tour(
                        cr, uid, tour_name,
                        with_creation=True, context=context)
                    tour_code_start = tour_name[:1]

                    partner_code = record['CKY_CNT_CLFR']
                    partner_id = partner_pool.get_partner_from_sql_code(
                        cr, uid,
                        partner_code,
                        context=context)

                    partner_start_code = partner_code[:2]
                    if not partner_id and partner_start_code != '06':
                        log_message(
                            'Saltato ordine %s cliente non ha codice 06:'
                            ' %s!' % (
                                name, partner_code),
                            error_block,
                            error=False,  # warning
                        )
                        continue

                    if not partner_id and partner_start_code == '06':
                        partner_data = {
                            'name': 'Nuovo cliente codice %s' % partner_code,
                            'sql_customer_code': partner_code,
                            'sql_import': True,
                            'is_company': True,
                            # 'street': record['CDS_INDIR'] or False,
                            # 'city': record['CDS_LOC'] or False,
                            # 'zip': record['CDS_CAP'] or False,
                            # 'phone': record['CDS_TEL_TELEX'] or False,
                            # 'email': record['CDS_INET'] or False,
                            # 'fax': record['CDS_FAX'] or False,
                            # 'mobile': record['CDS_INDIR'] or False,
                            # 'website': record['CDS_URL_INET'] or False,
                            # 'vat': record['CSG_PIVA'] or False,
                            # key_field: record['CKY_CNT'],  # key code
                            # 'country_id': countries.get(
                            #    record['CKY_PAESE'], False),
                            'type': 'default',
                            'customer': True,
                            'ref': partner_code,
                            }
                        partner_id = partner_pool.create(
                            cr, uid, partner_data, context=context)
                        log_message(
                            'Ordine %s. Cliente non trovato, creato '
                            'segnaposto: %s!' % (
                                name, partner_code),
                            error_block,
                        )

                    destination_code = record['CKY_CNT_SPED_ALT'].strip()
                    if destination_code == idem:
                        destination_id = partner_id
                        _logger.warning('Idem order replaced: %s' % name)
                    elif destination_code:
                        destination_id = \
                            partner_pool.get_partner_from_sql_code(
                                cr, uid,
                                destination_code,
                                context=context)

                        if not destination_id:
                            log_message(
                                'Ordine %s. Destinazione non trovata: %s!' % (
                                    name, destination_code),
                                error_block,
                            )
                            # continue
                    else:
                        destination_id = False  # Not passed, not searched

                    data = {
                        'name': name,
                        'partner_id': partner_id,
                        'destination_id': destination_id,
                        'date': date,
                        'description': '',  # todo
                        'note': record['CDS_NOTE'],
                        'tour_id': tour_id,
                        'tour_code_start': tour_code_start,
                        'prevision_load': record['NPS_TOT'],
                        'error': error_block['record'],
                        'removed': False,
                        'order_mode': 'D',  # Updated after
                        }

                    order_ids = self.search(cr, uid, [
                        ('name', '=', name)], context=context)
                    if order_ids:
                        self.write(cr, uid, order_ids, data, context=context)
                        order_id = order_ids[0]  # only one updated!
                    else:
                        order_id = self.create(cr, uid, data, context=context)

                    order_reference[number] = order_id
                except:
                    log_message(
                        'Errore generico importazione ordine: [%s]\n'
                        'LOG: [%s]' % (
                            record,
                            sys.exc_info(),
                        ),
                        error_block,
                    )

            # Import line detail for order:
            # todo parameter the filename:
            filename = os.path.expanduser('~/mexal/viaggi/freschi.txt')
            _logger.info('Updating extra info, file: %s' % filename)
            for line in open(filename, 'r'):
                row = line.strip().split(';')
                if len(row) != 3:
                    _logger.error('Line empty, jumped')
                    continue

                number = row[1]
                try:
                    order_mode = row[2] or 'D'
                    order_id = order_reference.get(number)
                    if order_id:
                        self.write(cr, uid, [order_id], {
                            'order_mode': order_mode,
                        }, context=context)
                except:
                    _logger.error(
                        'Cannot load extra info for order: %s' % number)
            _logger.info('All trip order is updated!')

            if error_block['master'] or error_block['warning']:
                company_pool.write(cr, uid, [company_id], {
                    'trip_master_error': error_block['master'],
                    'trip_master_warning': error_block['warning'],
                }, context=context)

        except:
            _logger.error('Generic error importing trip order [%s]' % (
                sys.exc_info(), ))
        return True

    # ----------------
    # Fields function:
    # ----------------
    def _get_tour_code(self, cr, uid, ids, name, args, context=None):
        """ First letter of tour code of the trip
        """
        res = {}
        for item in self.browse(cr, uid, ids, context=context):
            try:
                res[item.id] = item.trip_id.tour_id.name[:1]
            except:
                res[item.id] = False
        return res

    def _search_tour_code(self, cr, uid, obj, name, args, context=None):
        """ Search first letter of tour code
        """
        res = []
        if not len(args):
            return res

        trip_ids = self.pool.get('trip.trip').search(cr, uid, [
            ('tour_code', '=', args[0][2])], context=context)
        if not trip_ids:
            return res
        res = [('trip_id', 'in', trip_ids)]
        return res

    _columns = {
        # Order information from accounting:
        'name': fields.char('Ref.', size=35),
        'date': fields.date('Date'),
        'description': fields.char('Description', size=100),
        'note': fields.text('Note'),
        'partner_id': fields.many2one(
            'res.partner', 'Customer',
            # required=True,
            ondelete='cascade',
            domain=[('customer', '=', True)]
            ),
        'destination_id': fields.many2one(
            'res.partner', 'Destinazione',
            # required=True,
            ondelete='cascade',
            domain=[('is_address', '=', True)]
            ),
        'city': fields.related(
            'destination_id', 'city', type='char',
            string='City'),
        'delivery_note': fields.related(
            'destination_id', 'delivery_note',
            type='char', string='Dest. note'),
        'tour_id': fields.many2one(
            'trip.tour', 'Tour',
            ondelete='cascade',
            help="Tour setted up for order (instead use destination)"),
        'tour_code_start': fields.char(
            'Codice viaggio',
            help='Lettera legata al viaggio per filtrare la lista'),

        # Details for trip:
        'sequence': fields.integer('Position'),
        'trip_id': fields.many2one(
            'trip.trip', 'Trip',
            ondelete='set null'),  # Order remain unlinked
        'time': fields.char('Request time', size=40),
        'prevision_load': fields.float('Prevision load', digits=(16, 2)),
        'current_load': fields.float('Current load', digits=(16, 2)),
        'error': fields.text(
            'Import error',
            help="If present there's an error during importation!"),
        'order_mode': fields.selection(
            selection=[
                ('D', 'Std'),
                ('A', 'Freschi'),
                ('F', '+Freschi'),
            ], string='Modalità', required=True),
        'tour_code': fields.function(
            _get_tour_code,
            fnct_search=_search_tour_code,
            type='char',
            method=True,
            string="Tour code",
            store=False,
            ),
        'removed': fields.boolean(
            'Rimosso',
            help='Non più presente ma ancora agganciato a degli ordini'),
        }

    _defaults = {
        'order_mode': lambda *x: 'default',
    }


class res_partner(orm.Model):
    """ Add extra information to address (partner)
    """
    _name = 'res.partner'
    _inherit = 'res.partner'

    # ------------------
    # Override function:
    # ------------------
    def name_get(self, cr, uid, ids, context=None):
        """
        Return a list of tuples contains id, name.
        result format : {[(id, name), (id, name), ...]}

        @param cr: cursor to database
        @param uid: id of current user
        @param ids: list of ids for which name should be read
        @param context: context arguments, like lang, time zone

        @return: returns a list of tupples contains id, name
        """
        if context is None:
            context = {}
        show_trip = context.get('show_trip', False)
        # Only for destination let see accounting code:
        res = []
        for item in self.browse(cr, uid, ids, context=context):
            if item.is_address:
                name = "%s [%s]%s" % (
                    item.name,
                    item.sql_destination_code or '',
                    _(" <Tour: %s %s>") % (
                        item.tour1_id.name or "#",
                        item.tour2_id.name or "#",
                        ) if show_trip else "",
                    )

            else:
                name = item.name
            res.append((item.id, name))
        return res

    def name_search(self, cr, uid, name, args=None, operator='ilike',
        context=None, limit=80):
        """
        Return a list of tupples contains id, name, as internally its calls
            {def name_get}
        result format : {[(id, name), (id, name), ...]}

        @param cr: cursor to database
        @param uid: id of current user
        @param name: name to be search
        @param args: other arguments
        @param operator: default operator is ilike, it can be change
        @param context: context arguments, like lang, time zone
        @param limit: returns first n ids of complete result, default it is 80

        @return: return a list of tuples contains id, name
        """
        if not args:
            args = []
        if not context:
            context = {}
        ids = []

        if name:
            # Search also in accounting code:
            ids = self.search(cr, uid,
                args + [
                    '|',
                    ('sql_customer_code', 'ilike', name),
                    '|',
                    ('sql_supplier_code', 'ilike', name),
                    ('sql_destination_code', 'ilike', name),
                    ],
                limit=limit)
        if not ids:
            ids = self.search(cr, uid,
                args + [('name', operator, name)],
                limit=limit)
        res = self.name_get(cr, uid, ids, context=context)
        return res

    # -------------
    # Button event:
    # -------------
    def set_obsolete(self, cr, uid, ids, context=None):
        """ Set check box
        """
        return self.write(cr, uid, ids, {
            'trip_obsolete': True, }, context=context)

    def unset_obsolete(self, cr, uid, ids, context=None):
        """ Set check box
        """
        return self.write(cr, uid, ids, {
            'trip_obsolete': False, }, context=context)

    def open_destination_order(self, cr, uid, ids, context=None):
        """ Open view for read orders to this destination
        """
        # TODO
        return True

    # ---------------
    # Field function:
    # ---------------
    def _function_get_order(self, cr, uid, ids, args=None, fields=None,
        context=None):
        """ Return number of active order if is a destination
        """
        res = {}
        for partner in self.browse(cr, uid, ids, context=context):
            if partner.is_address:
                res[partner.id] = len(partner.destination_order_ids)
            else:
                res[partner.id] = 0
        return res

    _columns = {
        'tour1_id': fields.many2one('trip.tour', 'Tour 1',
            required=False,
            ondelete='set null'),
        'tour2_id': fields.many2one('trip.tour', 'Tour 2',
            required=False,
            ondelete='set null'),
        # 'sequence': fields.integer('Sequence',
        #    help="Sequence order for trip destinations"),
        # 'sequence': fields.integer('Sequence',
        # todo doppia sequence per doppia destinazione...
        #    help="Sequence order for trip destinations"),
        'delivery_note': fields.char('Delivery note', size=100),
        'active_order': fields.function(_function_get_order, method=True,
            type='integer', string='# Order', store=False),

        'trip_obsolete': fields.boolean('Trip obsolete'),

        # Vector partner:
        'is_vector': fields.boolean('Is vector'),
        'vector_note': fields.text('Delivery note'),
        # 'max_load': fields.float('Max load', digits=(16, 2)),

        # 2many relations:
        'order_ids': fields.one2many(
            'trip.order', 'partner_id', 'Orders'),
        'destination_order_ids': fields.one2many(
            'trip.order', 'destination_id', 'Destination order'),
        }

    _defaults = {
        'trip_obsolete': lambda *x: False,
        }


class trip_trip(orm.Model):
    """ Add relation fields
    """
    _inherit = 'trip.trip'

    _columns = {
        'order_ids': fields.one2many(
            'trip.order', 'trip_id', 'Order', ),
        }


class trip_tour(orm.Model):
    """ Add relation fields
    """
    _inherit = 'trip.tour'

    _columns = {
        'trip_ids': fields.one2many('trip.trip', 'tour_id',
            'Trip', ),
        'destination1_ids': fields.one2many('res.partner', 'tour1_id',
            'Destination 1'),
        'destination2_ids': fields.one2many('res.partner', 'tour2_id',
            'Destination 2'),
        'keep': fields.boolean(
            'Tenere',
            help='Sigla di viaggio che viene sempre conservata alle pulizie '
                 'giornaliere'),
    }


