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
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT,
    DEFAULT_SERVER_DATETIME_FORMAT, DATETIME_FORMATS_MAP, float_compare)
import openerp.addons.decimal_precision as dp
from openerp.tools.translate import _


_logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
#                                   Wizard
# -----------------------------------------------------------------------------
class trip_trip_change_wizard(osv.osv_memory):
    """ Change trip for selected order in existent trip
    """
    _name = "trip.trip.change.wizard"

    # -------------
    # Button event:
    # -------------
    def action_print(self, cr, uid, ids, context=None):
        """ Change new trip
        """
        if context is None:
           context = {}

        wizard_proxy = self.browse(cr, uid, ids, context=context)[0]

        order_id = context.get('active_id', 0)
        return self.pool.get('trip.order').write(cr, uid, order_id, {
            'trip_id': wizard_proxy.trip_id.id, }, context=context)

    _columns = {
        'trip_id': fields.many2one('trip.trip', 'Trip', required=True),
        }
