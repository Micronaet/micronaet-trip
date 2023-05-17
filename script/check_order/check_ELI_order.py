# -*- coding: utf-8 -*-
###############################################################################
#
# ODOO (ex OpenERP)
# Open Source Management Solution
# Copyright (C) 2001-2015 Micronaet S.r.l. (<http://www.micronaet.it>)
# Developer: Nicola Riolini @thebrush (<https://it.linkedin.com/in/thebrush>)
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
import os
import sys
import erppeek
from datetime import datetime, timedelta
import ConfigParser
import pdb

path = '/home/openerp/etl/edi/elior/in'
extension = 'ASC'

for root, folders, files in os.path.walk(path):
    for filename in files:
        if not filename.endswith(extension):
            continue
        fullname = os.path(root, filename)

        create_date = create_date = datetime.fromtimestamp(
            os.path.getctime(fullname)
            ).strftime('%Y%m%d_%H%M%S')
        number = ''
        print('%s|%s|%s\n' % (
            fullname,
            create_date,
            number,
        ))
    break
