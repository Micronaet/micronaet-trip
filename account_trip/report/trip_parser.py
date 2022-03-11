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
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT,
    DEFAULT_SERVER_DATETIME_FORMAT, DATETIME_FORMATS_MAP, float_compare)
import openerp.addons.decimal_precision as dp
from openerp.tools.translate import _
from openerp.report.report_sxw import rml_parse


_logger = logging.getLogger(__name__)


class Parser(rml_parse):
    """ Parser for report
    """
    # Private data:
    counters = {}

    def __init__(self, cr, uid, name, context):
        self.context = context
        super(Parser, self).__init__(cr, uid, name, context)
        self.localcontext.update({
            'get_order_list': self.get_order_list,
            'get_counter': self.get_counter,
            'set_counter': self.set_counter,
        })

    def get_order_list(self, trip):
        """ Pack same line
        """
        order_line = []
        if trip.report_line == 'packed':
            # Preload phase:
            preload = {}
            for order in trip.order_ids:
                key = (
                    order.partner_id,
                    order.destination_id,
                    order.order_mode,
                )
                if key in preload:
                    preload[key][1].append(order)
                else:
                    preload[key] = [order.sequence, order]

            # Prepare data phase:
            for key in sorted(preload):  # sequence is the sort key
                sequence, orders = preload[key]
                counter = len(orders)

                extra = {
                    'time': set(),
                    'deadline': set(),
                    'number': set(),
                }
                for order in orders:
                    extra['time'].add((order.time or '').strip())
                    extra['deadline'].add((order.deadline or '').strip())
                    extra['number'].add(order.name.split('-')[-1].strip())

                extra['time'] = ' '.join(extra['time'])
                extra['deadline'] = ' '.join(extra['deadline'])
                extra['number'] = ' '.join(extra['number'])

                # Add only first for collect data:
                order_line.append(
                    (counter, orders[0], extra)
                )
        else:  # detailed
            counter = 1
            extra = {}
            for order in trip.order_ids:
                order_line.append(
                    (counter, order, extra)
                )
        return order_line

    def get_counter(self, name):
        """ Get counter with name passed (else create an empty)
        """
        if name not in self.counters:
            self.counters[name] = False
        return self.counters[name]

    def set_counter(self, name, value):
        """ Set counter with name with value passed
        """
        self.counters[name] = value
        return ""  # empty so no write in module
