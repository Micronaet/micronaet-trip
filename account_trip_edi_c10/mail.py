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
import pdb
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
    _inherit = 'edi.company.c10'

    # -------------------------------------------------------------------------
    #                     Abstract function for mail:
    # -------------------------------------------------------------------------
    def is_order_attachment(
            self, part, content_type, attach_filename, verbose=True):
        """ Check if the attachment is in correct format
        """
        # attachment_content = part.get_content_type()
        # attachment_content == content_type and \
        filename = part.get_filename()
        if filename and filename.endswith('_v2.txt'):
            if verbose:
                _logger.warning('Found order, attach: %s' % filename)
            return True

        if verbose:
            _logger.warning('Not Found order, attach: %s' % filename)
        return False

    def get_order_number(self, record):
        """ EDI mail: Extract order number
            Format: 'Ordine n.30451/21 - VETROPACK - RISTORAZIONE - 29/11/2021'
        """
        subject = record['Subject']
        return subject.split('-')[0].split('.')[-1].strip().replace('/', '_')

