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


class edi_company_c10(orm.Model):
    """ Add model for parametrize function for Company 10
        Model has only function for a sort of abstract class
    """

    _name = 'edi.company.c10'
    _description = 'EDI Company 10'

    # -------------------------------------------------------------------------
    #                     Abstract function and property:
    # -------------------------------------------------------------------------
    # todo align in correct new format for 10:
    trace = {
        'number': (46, 59),
        'date': (259, 267),  # Insert with parser function
        'deadline': (37, 45),
        'customer': (0, 0),  # Not present
        'detail_code': (65, 81),  # (162, 178),
        'detail_description': (179, 239),
        'detail_um': (240, 242),
        'detail_quantity': (243, 258),
        'detail_price': (0, 0),  # Not present
        'detail_total': (0, 0),  # Not present

        # Destination blocks:
        'destination_facility': (4, 14),
        'destination_cost': (15, 25),
        'destination_site': (26, 36),
        'destination_description': (0, 0),  # Not present
        }

    # todo align in correct new format for 10:
    def get_timestamp_from_file(self, file_in, path_in=None):
        """ Get timestamp value from file name
            File is: 20151231_120000_NAME.ASC
                     Date Time Filename
        """
        # TODO better is manage data in file instead change name!!
        date_block = file_in[:15]
        return "%s/%s/%s %s:%s:%s" % (
            date_block[:4],
            date_block[4:6],
            date_block[6:8],

            date_block[9:11],
            date_block[11:13],
            date_block[13:15],
            )

    # todo allign in correct new format for 10:
    def is_an_invalid_row(self, row):
        """ Always valid
        """
        return False

    # todo allign in correct new format for 10:
    def get_state_of_file(self, file_in, forced_list):
        """ Test state of file depend on name and forced presence
        """
        # Always create (no modify management)
        try:
            if file_in in forced_list:  # Forced (pickle file)
                return 'forced'
            else:
                file_part = file_in.split('_')
                command = file_part[3][:3].upper()
                if command == 'NEW':
                    return 'create'
                # todo not used:
                elif command == 'CAN':
                    return 'deleting'  # TODO delete?
                else:  # UPD
                    return 'change'
        except:
            return 'anomaly'

    # todo allign in correct new format for 10:
    def get_destination(self, facility, cost, site):
        """ Mask for code destination (only the last: site is used)
        """
        return "[H%s]" % cost

    # todo allign in correct new format for 10:
    def get_destination_id(self, cr, uid, facility, cost, site, context=None):
        """ Get 3 parameters for destination and return ID get from res.partner
            generated during importation
        """
        return self.pool.get('res.partner').search_supplier_destination(
            cr, uid, '', 'H' + cost, context=context)

    # todo allign in correct new format for 10:
    def get_priority(self, cr, uid, file_in):
        """ Always normal (no priority management)
        """
        return 'normal'

    # Format:
    # todo allign in correct new format for 10:
    def format_int(self, value):
        """ EDI integer format
        """
        return value

    # todo allign in correct new format for 10:
    def format_float(
            self, value, decimal=3, with_separator=False, separator='.'):
        """ EDI float format
        """
        return value

    # todo allign in correct new format for 10:
    def format_date(self, value, date_format='ISO'):
        """ EDI file date format YYYYMMDD
        """
        return "%s-%s-%s" % (value[:4], value[4:6], value[6:8])

    # todo allign in correct new format for 10:
    def format_string(self, value):
        """ EDI file string
        """
        return value.strip()
