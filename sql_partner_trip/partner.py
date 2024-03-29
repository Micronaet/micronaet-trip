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
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, DATETIME_FORMATS_MAP, float_compare
import openerp.addons.decimal_precision as dp
from openerp.tools.translate import _


_logger = logging.getLogger(__name__)


class res_partner(osv.osv):
    """ Add extra info for trip (partner address)
    """
    _inherit = 'res.partner'

    # Utility for search
    def search_supplier_destination(
            self, cr, uid, facility, code, context=None):
        """ Search code in alternative code if more than one is present
            search also facility
        """
        destination_ids = self.search(cr, uid, [
            ('trip_supplier_destination_code', '=', code)], context=context)

        if destination_ids:
            if len(destination_ids) == 1:
                return destination_ids[0]
            else:
                destination_ids = self.search(cr, uid, [
                    ('trip_supplier_destination_code', '=', code),
                    ('trip_supplier_facility_code', '=', facility),
                    ], context=context)
                if len(destination_ids) == 1:
                    return destination_ids[0]
                elif len(destination_ids) == 0:
                    _logger.error(
                        "Find no facility with more code [%s | %s]" % (
                            code,
                            facility))
                else:
                    _logger.error("Find more than one (%s) [%s | %s]" % (
                        len(destination_ids),
                        code,
                        facility))
        return False

    # -----------------
    # Scheduled action:
    # -----------------
    def schedule_import_destination_code(self, cr, uid, context=None):
        """ Launch update of destination reading M*SQL tables
        """
        try:
            company_pool = self.pool.get('res.company')
            tour_pool = self.pool.get('trip.tour')
            sql_pool = self.pool.get('micronaet.accounting')

            company_proxy = company_pool.get_from_to_dict(
                cr, uid, context=context)
            if not company_proxy:
                _logger.error('Company parameters not set up!')
                return False

            # -----------------------------
            # Destination code importation:
            # -----------------------------
            _logger.info('Start import SQL: destination code')
            cursor = sql_pool.get_destination_code(
                cr, uid, prefix=company_proxy.sql_destination_from_code,
                context=context)

            if not cursor:
                _logger.error("Unable to connect, no destination coding!")
                return False

            i = 0
            destination_lost = []
            _logger.info('UPDATING SITE INFORMATION IN PARTNER:')
            for record in cursor:
                i += 1
                code = record['CKY_CNT'].strip()
                if not i % 200:
                    _logger.info(
                        'Import destination code: %s record updated!' % i)
                destination_id = self.get_partner_from_sql_code(
                    cr, uid, code, context=context)
                if not destination_id:
                    _logger.error(
                        'Destination not found: %s!' % code)
                    destination_lost.append(code)
                    # todo Create a lite destination?
                    continue

                self.write(cr, uid, destination_id, {
                    'trip_supplier_destination_code':
                        record['CSG_CODALT'] or '',
                    'trip_supplier_facility_code':
                        record['CDS_COD__IMPIANTO_'] or '',
                    }, context=context)
            _logger.info('All supplier destination code is updated!\n'
                         'Destination lost: %s' % (destination_lost, ))

            # ----------------------
            # Tour code importation:
            # ----------------------
            _logger.info('Start import SQL: destination tour code')
            cursor = sql_pool.get_destination_tour(
                cr, uid, context=context)

            if not cursor:
                _logger.error("Unable to connect, no destination tour coding!")
                return False

            i = 0
            _logger.info('UPDATING TOUR DELIVERY NOTE IN PARTNER:')
            for record in cursor:
                try:
                    i += 1
                    code = record['CKY_CNT'].strip()
                    if not i % 200:
                        _logger.info(
                            'Import destination tour code: %s record '
                            'updated!' % i)
                    destination_id = self.get_partner_from_sql_code(
                        cr, uid, code, context=context)
                    if not destination_id:
                        _logger.error(
                            'Destination not found: %s!' % code)
                        # todo Create a lite destination?
                        continue

                    self.write(cr, uid, destination_id, {
                        'tour1_id': tour_pool.search_tour(
                            cr, uid, record["CDS_PRIMO_GIRO"],
                            with_creation=True,
                            context=context),
                        'tour2_id': tour_pool.search_tour(
                            cr, uid, record["CDS_SECONDO_GIRO"],
                            with_creation=True,
                            context=context),
                        'delivery_note': record['CDS_NOTE_CONSEGNA'].strip(),
                        }, context=context)
                except:
                    _logger.error(
                        'Error updating partner tout / delivery info [%s]!' %
                        code)

            _logger.info('All supplier destination tour code is updated!')

        except:
            _logger.error('Record %s Generic: import destination: [%s]' % (
                code, sys.exc_info(), ))
            return False
        return True

    _columns = {
        'trip_supplier_destination_code': fields.char(
            'Supplier destination code', size=80),  # cost + site
        'trip_supplier_facility_code': fields.char(
            'Supplier facility code', size=40,
            help="Patricular for EDI importation",   # facility
            ),
        }
