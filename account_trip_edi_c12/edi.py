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
from openerp.osv import fields, osv, expression, orm
from datetime import datetime, timedelta
from openerp.tools.translate import _

_logger = logging.getLogger(__name__)


class edi_company_c12(orm.Model):
    """ Add model for parametrize function for Company 10
        Model has only function for a sort of abstract class
    """

    _name = 'edi.company.c12'
    _description = 'EDI Company 12'

    # -------------------------------------------------------------------------
    #                     Abstract function and property:
    # -------------------------------------------------------------------------
    # todo align in correct new format for 12:
    trace = {
        'number': (46, 59),
        'deadline': (37, 45),  # DDMMYYYY
        'date': (259, 267),  # DDMMYYYY
        'customer': (0, 0),  # Not present
        'detail_code': (162, 178),
        'detail_description': (179, 239),
        'detail_um': (240, 242),
        'detail_quantity': (146, 161),  # OK
        'detail_price': (0, 0),  # todo add from partic
        'detail_total': (0, 0),  # Not present

        # Destination blocks:
        # todo add also 25 char for type of stock?
        # todo correct data:
        'destination_facility': (0, 0),  # OK Stock code
        'destination_cost': (15, 25),  # OK CDC (ok?)
        'destination_site': (0, 0),  # OK Address code
        'destination_description': (366, 406),
        }

    # todo align in correct new format for 12:
    def get_timestamp_from_file(self, file_in, path_in=None):
        """ Get timestamp value from file name
            File is: 31218_20221006_906.txt
                     Date Time Filename
        """
        # todo better is manage data in file instead change name!!
        date_block = file_in.split('_')[2]
        hour_block = file_in.split('_')[3]
        return "%s/%s/%s %s:%s:%s" % (
            date_block[:4],
            date_block[4:6],
            date_block[6:8],

            hour_block[:2],
            hour_block[2:4],
            hour_block[4:6],
            )

    # todo align in correct new format for 12:
    def is_an_invalid_row(self, row):
        """ Always valid
        """
        return False

    # todo align in correct new format for 12:
    def get_state_of_file(self, file_in, forced_list):
        """ Test state of file depend on name and forced presence
        """
        # Always create (no modify management)
        return 'create'

    # todo align in correct new format for 12:
    def get_destination(self, facility, cost, site):
        """ Mask for code destination (only the last: site is used)
        """
        return "[%s]" % cost

    # todo align in correct new format for 12:
    def get_destination_id(self, cr, uid, facility, cost, site, context=None):
        """ Get 3 parameters for destination and return ID get from res.partner
            generated during importation
        """
        return self.pool.get('res.partner').search_supplier_destination(
            cr, uid, '', cost, context=context)

    # todo align in correct new format for 12:
    def get_priority(self, cr, uid, file_in):
        """ Always normal (no priority management)
        """
        return 'normal'

    # Format:
    # todo align in correct new format for 12:
    def format_int(self, value):
        """ EDI integer format
        """
        return value

    # todo align in correct new format for 12:
    def format_float(
            self, value, decimal=3, with_separator=False, separator='.'):
        """ EDI float format
        """
        value = value.replace(',', '.').strip()
        if not value:
            return 0.0
        try:
            return float(value)
        except:
            _logger.error('Cannot convert float: %s' % value)
            return 0.0

    # todo align in correct new format for 12:
    def format_date(self, value, date_format='ISO'):
        """ EDI file date format DDMMYYYY
        """
        value = value.strip()
        if not value:
            return False
        # return '%s-%s-%s' % (value[4:8], value[2:4], value[:2])
        return '%s-%s-%s' % (value[:4], value[4:6], value[6:8])

    # todo align in correct new format for 12:
    def format_string(self, value):
        """ EDI file string
        """
        return value.strip()
