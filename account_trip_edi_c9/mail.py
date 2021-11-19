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


class edi_company_c9(orm.Model):
    """ Add model for parametrize function for Company 9
        Model has only function for a sort of abstract class
    """

    _inherit = 'edi.company.c9'

    # -------------------------------------------------------------------------
    #                     Abstract function for mail:
    # -------------------------------------------------------------------------
    def email_subject_validate(self, edi_company, subject):
        """ EDI mail: Validate email (subject syntax check)
        """
        return True

    def email_extract_order_file(self, edi_company, email):
        """ EDI mail: Extract data file from email
        """
        return True

    def email_parse_order_file(self, edi_company, order_file):
        """ EDI mail: Extract data file from email
        """
        return True
