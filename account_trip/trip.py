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


class ResCompnay(orm.Model):
    """ Class Company for operation
    """
    _inherit = 'res.company'

    def clean_all_order(self, cr, uid, ids, context=None):
        """ Clean all order: daily operation before start work
        """
        return self.pool.get('trip.order').clean_all_order(
            cr, uid, ids, context=context)

    def import_all_order(self, cr, uid, ids, context=None):
        """ Re import order: daily operation before start work
        """
        return self.pool.get('trip.order').schedule_import_trip_order(
            cr, uid, context=context)


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

    _columns = {
        'name': fields.char('Description', size=64, required=True),
        'vector_id': fields.many2one('res.partner', 'Vector',
            required=True,
            domain = [('is_vector', '=', True)],
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
        Return a list of tupples contains id, name.
        result format : {[(id, name), (id, name), ...]}

        @param cr: cursor to database
        @param user: id of current user
        @param ids: list of ids for which name should be read
        @param context: context arguments, like lang, time zone

        @return: returns a list of tuples contains id, name
        """
        res = []
        for item in self.browse(cr, user, ids, context=context):
            if context.get('name_extra_info', False):
                name = _("%s (%s) [Prev. %s] ") % (  # [Curr. %s]
                    item.tour_id.name,
                    item.date,
                    item.prevision_load,
                    # item.current_load,
                    )
            else:
                name = "%s (%s)" % (
                    item.tour_id.name,
                    item.date,
                    )
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
                    'current_load'] += order.prevision_load  # order.current_load or
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

        #'name': fields.char('Code', size=10, required=True),
        'description': fields.char('Description', size=100),
        'note': fields.text('Note'),
        'good_collection': fields.text('Good collection'),

        'max_load': fields.float('Max load', digits=(16, 2)),

        # Related for totals:
        'prevision_load': fields.function(_get_totals, method=True,
            type='float', digits=(16, 2), string='Prevision load',
            store=False, multi='total'),
        'current_load': fields.function(_get_totals, method=True, type='float',
            digits=(16, 2), string='Current load', store=False, multi='total'),
        'total_delivery': fields.function(_get_totals, method=True,
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
        # Clean all trip:
        trip_pool = self.pool.get('trip.trip')
        trip_ids = trip_pool.search(cr, uid, [], context=context)
        trip_pool.unlink(cr, uid, trip_ids, context=context)
        _logger.warning('Removed %s trip' % len(trip_ids))

        # Clean all order: (for start new day trip)
        delete_ids = self.search(cr, uid, [
            # ('trip_id', '!=', False),  # Trip associated
            # ('date', '<=', (  # Trip older: date -7
            #        datetime.now() - timedelta(days=7)).strftime(
            #    DEFAULT_SERVER_DATE_FORMAT)),
        ], context=context)
        _logger.warning('Removed %s order' % len(delete_ids))
        return self.unlink(cr, uid, delete_ids, context=context)

    # -------------------------------------------------------------------------
    # Schedule event:
    # -------------------------------------------------------------------------
    def schedule_import_trip_order(self, cr, uid, context=None):
        """ Import order for manage trip
        """
        try:
            # Pool object:
            company_pool = self.pool.get('res.company')
            partner_pool = self.pool.get('res.partner')
            sql_pool = self.pool.get('micronaet.accounting')
            tour_pool = self.pool.get('trip.tour')

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

            # Start importation order:
            order_reference = {}
            i = 0
            for record in cursor:
                try:
                    i += 1
                    if not i % 100:
                        _logger.info(
                            'Import destination code: %s record updated!' % i)

                    error = ""
                    name = sql_pool.KEY_OC_FORMAT % record
                    tour_name = record['CDS_NOTE'].strip()
                    tour_id = tour_pool.search_tour(
                        cr, uid, tour_name,
                        with_creation=True, context=context)

                    partner_id = partner_pool.get_partner_from_sql_code(
                        cr, uid,
                        record['CKY_CNT_CLFR'],
                        context=context)

                    if not partner_id:
                        error += _('Partner not found: %s!\n') % \
                                 record['CKY_CNT_CLFR']
                        _logger.error(
                            'Partner not found: %s!' % record['CKY_CNT_CLFR'])
                        continue

                    destination_id = partner_pool.get_partner_from_sql_code(
                        cr, uid,
                        record['CKY_CNT_SPED_ALT'],
                        context=context)

                    if not destination_id:
                        error += _(
                            'Destination not found: %s!\n') % record[
                                'CKY_CNT_SPED_ALT']
                        _logger.error(
                            'Destination not found: %s!' % record[
                                'CKY_CNT_SPED_ALT'])
                        continue

                    data = {
                        'name': name,
                        'partner_id': partner_id,
                        'destination_id': destination_id,
                        'date': False,  # todo record['DTT_DOC']
                        'description': '',  # todo
                        'note': record['CDS_NOTE'],
                        'tour_id': tour_id,
                        'prevision_load': record['NPS_TOT'],
                        'error': error,
                        }

                    order_ids = self.search(cr, uid, [
                        ('name', '=', name)], context=context)
                    if order_ids:
                        self.write(cr, uid, order_ids, data, context=context)
                        order_id = order_ids[0]  # only one updated!
                    else:
                        order_id = self.create(cr, uid, data, context=context)

                    order_reference[name] = order_id
                except:
                    _logger.error(
                        'Error importing order record: [%s] \n LOG: [%s]\n' % (
                            record,
                            sys.exc_info(), ))

            # Import line detail for order:
            # todo parameter the filename:
            filename = os.path.expanduser('~/mexal/viaggi/freschi.txt')
            _logger.info('Updating extra info, file: %s' % filename)
            for line in open(filename, 'r'):
                row = line.strip()
                number = row[1]
                order_mode = row[2] or 'D'
                order_id = order_reference.get(number)
                if order_id:
                    self.write(cr, uid, [order_id], {
                        'order_mode': order_mode,
                    }, context=context)
            _logger.info('All trip order is updated!')
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
            domain = [('customer', '=', True)]
            ),
        'destination_id': fields.many2one(
            'res.partner', 'Destinazione',
            # required=True,
            ondelete='cascade',
            domain = [('is_address', '=', True)]
            ),
        'city': fields.related('destination_id','city', type='char',
            string='City'),
        'delivery_note': fields.related('destination_id','delivery_note',
            type='char', string='Dest. note'),
        'tour_id': fields.many2one(
            'trip.tour', 'Tour',
            ondelete='cascade',
            help="Tour setted up for order (instead use destination)"),

        # Details for trip:
        'sequence': fields.integer('Position'),
        'trip_id': fields.many2one('trip.trip', 'Trip',
            ondelete='set null'), # Order remain unlinked
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
        Return a list of tupples contains id, name.
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
            #Search also in accounting code:
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
        #'sequence': fields.integer('Sequence',
        #    help="Sequence order for trip destinations"),
        #'sequence': fields.integer('Sequence',  # TODO doppia sequence per doppia destinazione...
        #    help="Sequence order for trip destinations"),
        'delivery_note': fields.char('Delivery note', size=100),
        'active_order': fields.function(_function_get_order, method=True,
            type='integer', string='# Order', store=False),

        'trip_obsolete': fields.boolean('Trip obsolete'),

        # Vector partner:
        'is_vector': fields.boolean('Is vector'),
        'vector_note': fields.text('Delivery note'),
        #'max_load': fields.float('Max load', digits=(16, 2)),

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
    _name = 'trip.trip'
    _inherit = 'trip.trip'

    _columns = {
        'order_ids': fields.one2many('trip.order', 'trip_id',
            'Order', ),
        }

class trip_tour(orm.Model):
    """ Add relation fields
    """
    _name = 'trip.tour'
    _inherit = 'trip.tour'

    _columns = {
        'trip_ids': fields.one2many('trip.trip', 'tour_id',
            'Trip', ),
        'destination1_ids': fields.one2many('res.partner', 'tour1_id',
            'Destination 1'),
        'destination2_ids': fields.one2many('res.partner', 'tour2_id',
            'Destination 2'),
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
