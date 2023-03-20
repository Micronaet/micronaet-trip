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
import pdb
import sys
import os
import shutil
import ConfigParser
from datetime import datetime


# Parameters:
extension = 'txt'
history_path = os.path.expanduser('~/etl/edi/dussmann/order/history')
to_path = os.path.expanduser('~/cron/dussmann/output')

# Export:
file_original = os.path.join(to_path, 'Controllo_destinazioni.csv')
f_out = open(file_original, 'w')
f_out.write('Numero;Anno;Codice dest.;Descrizione dest.;Data;Ora\n')
for root, dirs, files in os.walk(history_path):
    for filename in files:
        if not filename.lower().endswith(extension):
            print('No order file file: %s' % filename)
            continue

        filename_part = filename.split('_')
        if len(filename_part) != 5:
            print('No 5 part in filename: %s' % filename)
            continue
        year, number, date, hour, mode = filename_part

        fullname = os.path.join(root, filename)

        # Read input file:
        f_in = open(fullname, 'r')
        for line in f_in:
            # Clean base 64 data (clean start editor char):
            line = line.replace('\xff', '').replace('\xfe', '').replace(
                '\x00', '')
            code = line[15:25].strip()
            description = line[366:405].strip()

            f_out.write('%s;%s;%s;%s;%s;%s\n' % (
                number,
                year,
                code,
                description,
                date,
                hour,
            ))
            f_out.flush()
            break
        print('Extract data from filename: %s' % filename)
print('End extract')
