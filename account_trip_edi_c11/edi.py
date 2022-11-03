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


class edi_company_c11(orm.Model):
    """ Add model for parametrize function for Company 10
        Model has only function for a sort of abstract class
    """

    _name = 'edi.company.c11'
    _description = 'EDI Company 11'

    # -------------------------------------------------------------------------
    #                     Abstract function and property:
    # -------------------------------------------------------------------------
    # todo align in correct new format for 11:
    trace = {
        'number': (7, 13),  # OK
        'date': (13, 21),  # OK Insert with parser function
        'deadline': (644, 652),  # OK
        'customer': (0, 0),  # Not present
        'detail_code': (614, 644),  # OK
        'detail_description': (179, 239),
        'detail_um': (654, 669),  # OK
        'detail_quantity': (652, 664),  # OK
        'detail_price': (0, 0),  # Not present
        'detail_total': (0, 0),  # Not present

        # Destination blocks:
        # todo add also 25 char for type of stock?
        'destination_facility': (26, 33),  # OK Stock code
        'destination_cost': (21, 25),  # OK CDC
        'destination_site': (33, 37),  # OK Address code
        'destination_description': (359, 614),  # OK Company description
        }

    # todo align in correct new format for 11:
    def get_timestamp_from_file(self, file_in, path_in=None):
        """ Get timestamp value from file name
            File is: 20151231_120000_NAME.ASC
                     Date Time Filename
        """
        # todo better is manage data in file instead change name!!
        date_block = file_in[:15]
        return "%s/%s/%s %s:%s:%s" % (
            date_block[:4],
            date_block[4:6],
            date_block[6:8],

            date_block[9:11],
            date_block[11:13],
            date_block[13:15],
            )

    # todo allign in correct new format for 11:
    def is_an_invalid_row(self, row):
        """ Always valid
        """
        return False

    # todo allign in correct new format for 11:
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

    # todo allign in correct new format for 11:
    def get_destination(self, facility, cost, site):
        """ Mask for code destination (only the last: site is used)
        """
        return "[H%s]" % cost

    # todo allign in correct new format for 11:
    def get_destination_id(self, cr, uid, facility, cost, site, context=None):
        """ Get 3 parameters for destination and return ID get from res.partner
            generated during importation
        """
        return self.pool.get('res.partner').search_supplier_destination(
            cr, uid, '', 'H' + cost, context=context)

    # todo allign in correct new format for 11:
    def get_priority(self, cr, uid, file_in):
        """ Always normal (no priority management)
        """
        return 'normal'

    # Format:
    # todo allign in correct new format for 11:
    def format_int(self, value):
        """ EDI integer format
        """
        return value

    # todo allign in correct new format for 11:
    def format_float(
            self, value, decimal=3, with_separator=False, separator='.'):
        """ EDI float format
        """
        return value

    # todo allign in correct new format for 11:
    def format_date(self, value, date_format='ISO'):
        """ EDI file date format YYYYMMDD
        """
        return "%s-%s-%s" % (value[:4], value[4:6], value[6:8])

    # todo allign in correct new format for 11:
    def format_string(self, value):
        """ EDI file string
        """
        return value.strip()
