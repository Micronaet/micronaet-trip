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
from datetime import datetime
import pdb

path = '/home/openerp/etl/edi/elior/in'
extension = 'ASC'
deadline_max = '20220519'  # <=
pdb.set_trace()
log_f = open('./log_move.csv', 'w')

log_f.write('Cambio|Filename|File date|Numero|Scadenza|Cancellare\n')
for root, folders, files in os.walk(path):
    for filename in sorted(files):
        if not filename.endswith(extension):
            continue
        fullname = os.path.join(root, filename)

        create_date = datetime.fromtimestamp(
            os.path.getctime(fullname)
            ).strftime('%Y/%m/%d %H:%M:%S')
        number = ''
        if filename.startswith('ELICHG'):
            change = 'X'
        else:
            change = ''

        for line in open(fullname, 'r'):
            number = line[19:37].strip()
            deadline = line[45:53].strip()
            break

        if deadline > deadline_max:
            deadlined = ''
        else:
            deadlined = 'X'

        log_f.write('%s|%s|%s|%s|%s|%s\n' % (
            change,
            filename,
            create_date,
            number,
            deadline,
            deadlined,
        ))
    break
