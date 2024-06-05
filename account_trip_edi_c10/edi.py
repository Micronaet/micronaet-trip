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

import logging
from openerp.osv import fields, osv, expression, orm

_logger = logging.getLogger(__name__)


class edi_company_c10(orm.Model):
    """ Add model for parametrize function for Company 10
        Model has only function for a sort of abstract class
    """

    _name = 'edi.company.c10'
    _description = 'EDI Company 10'

    # -------------------------------------------------------------------------
    #                     Abstract function and property:
    # -------------------------------------------------------------------------
    trace = {
        'number': (19, 28),
        'date': (29, 37),  # 8
        'deadline': (45, 53),  # 8
        'customer': (1545, 1645),  # 100
        'detail_code': (2356, 2391),  # 35
        'detail_description': (2531, 2631),  # 100
        'detail_um': (2641, 2644),  # 3
        'detail_quantity': (2631, 2641),  # 10
        'detail_price': (2877, 2887),  # 10
        'detail_total': (2907, 2917),  # 10

        # Destination blocks:
        'destination_facility': (871, 906),  # 35 facility
        'destination_cost': (253, 283),  # 30 cost
        'destination_site': (1189, 1224),  # 35 site
        'destination_description': (1259, 1359)  # 100 description
        }

    def is_an_invalid_row(self, row):
        """ Check if the row is not (A) = Cancel
        """
        if row[2644:2645] == 'A':
            return True
        return False

    def get_timestamp_from_file(self, file_in, path=None):
        """ Get timestamp value from file name
            File is: ELIORD20141103091707.ASC
                     ------YYYYMMGGhhmmss----
            Millisecond are
                00 for create order ELIORD
                10 for delete order ELICHG
        """
        return '%s-%s-%s %s:%s:%s.%s' % (
            file_in[6:10],  # Year
            file_in[10:12],  # Month
            file_in[12:14],  # Day
            file_in[14:16],  # Hour
            file_in[16:18],  # Minute
            file_in[18:20],  # Second
            '00' if file_in.startswith('ELIORD') else '10'  # Millisecond
            )

    def get_state_of_file(self, file_in, forced_list):
        """ Test state of file depend on name and forced presence
        """
        if file_in in forced_list:  # Forced (pickle file)
            return 'forced'
        elif file_in.startswith('ELIORD') or file_in.startswith('ELIURG'):
            return 'create'
        else:
            return 'delete'  # Update file

    def get_destination(self, facility, cost, site):
        """ Mask for code destination
        """
        return '[%s|%s|%s]' % (facility, cost, site)

    def get_destination_id(self, cr, uid, facility, cost, site, context=None):
        """ Get 3 parameters for destination and return ID get from res.partner
            generated during importation
        """
        # The 3 part of destination, in importation, are stored in 2 fields
        return self.pool.get('res.partner').search_supplier_destination(
            cr, uid, facility, '%s%s' % (cost, site), context=context)

    def get_priority(self, cr, uid, file_in):
        """ Return priority value depend on file name
        """
        if file_in.startswith('ELIURG'):
            return 'high'
        return 'normal'

    # Format:
    def format_int(self, value):
        """ EDI integer format
        """
        return value

    def format_float(
            self, value, decimal=3, with_separator=False, separator='.'):
        """ EDI float format
        """
        return value

    def format_date(self, value, date_format='ISO'):
        """ EDI file date format YYYYMMDD
        """
        return '%s-%s-%s' % (value[:4], value[4:6], value[6:8])

    def format_string(self, value):
        """ EDI file string
        """
        return value.strip()
