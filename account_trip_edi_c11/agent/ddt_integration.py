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


# -----------------------------------------------------------------------------
# Utility:
# -----------------------------------------------------------------------------
def clean_text(text, length, uppercase=False, error=None, truncate=False):
    """ Return clean text with limit cut
        Log in error if over length
    """
    if error is None:
        error = []

    text = text.strip()
    if len(text) > length:
        if truncate:
            text = text[:length]
        else:
            error.append('Text: %s > %s' % (text, length))
    if uppercase:
        return text.upper()
    return text


def clean_date(date):
    """ Current format: YYMMDD
    """
    # if len(company_date) == 6:
    #    return '20%s' % company_date.strip()
    # else:
    # return company_date.strip()
    date = date.strip()

    if len(date) == 6:
        res = '20%s%s%s' % (
            date[4:6],
            date[2:4],
            date[:2],
        )
    else:
        res = '%s%s%s' % (
            date[4:8],
            date[2:4],
            date[:2],
        )
    return res


def clean_float(
        value, length, decimal=3, multiple=1.0, separator='.', error=None):
    """ Clean float and return float format
    """
    value = value.strip()
    if not value:
        return 0.0

    if error is None:
        error = []
    try:
        value = value.replace(',', '.')
        float_value = float(value.strip())
    except:
        error.append('Not a float: %s' % value)
        float_value = 0.0
    float_value /= multiple
    mask = '%%%s.%sf' % (length, decimal)
    res = mask % float_value
    res = res.replace('.', separator)
    return res


# -----------------------------------------------------------------------------
# Read configuration parameter:
# -----------------------------------------------------------------------------
try:
    cfg_file = os.path.expanduser('./DUS.cfg')
except:
    print('Config file not found: DUS.cfg')
    sys.exit()

config = ConfigParser.ConfigParser()
config.read([cfg_file])

# In parameters:
in_check = os.path.expanduser(config.get('in', 'check'))
in_path = os.path.expanduser(config.get('in', 'path'))
in_history = os.path.expanduser(config.get('in', 'history'))
in_log = os.path.expanduser(config.get('in', 'log'))
in_schedule = os.path.expanduser(config.get('in', 'schedule'))
extension = 'txt'

# -----------------------------------------------------------------------------
# Read IN folder:
# -----------------------------------------------------------------------------
file_original = '/home/openerp/etl/edi/dussmann_check.log'
f_out = open(file_original, 'w')

conversion = {}

data = {}
for root, dirs, files in os.walk(in_history):
    for f in files:
        if not f.lower().endswith(extension):
            continue

        # Fullname needed:
        command = 'NEW'  # Only this!
        file_in = os.path.join(root, f)
        create_date = datetime.fromtimestamp(
            os.path.getctime(file_in)).strftime('%Y%m%d_%H%M%S')

        # ---------------------------------------------------------------------
        # Read input file:
        # ---------------------------------------------------------------------
        error = []
        f_in = open(file_in, 'r')

        counter = 0
        for line in f_in:
            # Clean base 64 data (clean start editor char):
            line = line.replace('\xff', '').replace('\xfe', '').replace(
                '\x00', '')
            if not line:
                continue  # Jump empty line

            # -----------------------------------------------------------------
            # Create file every code break:
            # -----------------------------------------------------------------
            order_year = line[3:7].strip()
            order_number = line[7:13].strip()

            # Generate filename for every order included:
            order_file = '%s_%s_%s_%s.%s' % (
                order_year,  # Year
                order_number,  # Number
                create_date,  # Date of file
                command,  # Mode
                extension,   # Extension same as original
            )

            if order_file not in data:
                data[order_file] = {
                    'counter': 0,
                    'line': [],
                    'header': {
                        'type': line[:2].strip(),  # AA
                        # 'sequence': line[2:7].strip(),
                        'order': '%s%s' % (order_year, order_number),
                        # 'date': line[13:21].strip(),
                        # 'deadline': line[644:652].strip(),

                        'stock_type': line[25:26].strip(),
                        'company_code': line[26:33].strip(),
                        'destination_code': line[21:25].strip(),
                        'destination_address_code': line[33:37].strip(),

                        # # 'document': line[67:69].strip(),
                        # # 'destination_facility': (26, 33),  # OK Stock code
                        # # 'destination_cost': (21, 25),  # OK CDC
                        # # 'destination_site': (33, 37),  # OK Address code
                        # 'destination_description': line[37:97].strip(),
                        # 'cig': line[719:744].strip(),
                    },
                }

            # Detail lines:
            detail = {
                # 'type': '',  # line[:2].strip(),
                'sequence': line[278:282].strip(),
                'code': line[614:644].strip(),
                # 'name': line[359:614].strip(),
                # 'uom': line[664:669].strip(),
                'quantity': line[652:664].strip(),
                # 'price': '',   # line[72:81].strip(),
                # 'vat': '',   # line[67:69].strip(),
                }

            # -----------------------------------------------------------------
            # Convert row input file:
            # -----------------------------------------------------------------
            data[order_file]['counter'] += 1
            counter = str(data[order_file]['counter'])
            # Only subtype
            text_line = '%-20s|%-1s|%-7s|%-4s|%-4s|%-30s|%-12s|%-4s|%4s|%-2s' \
                        '\r\n' % (
                clean_text(
                    data[order_file]['header']['order'],
                    20, error=error, truncate=True),
                clean_text(
                    data[order_file]['header']['stock_type'],
                    1, error=error, truncate=True),
                clean_text(
                    data[order_file]['header']['company_code'],
                    7, error=error, truncate=True),
                clean_text(
                    data[order_file]['header']['destination_code'],
                    4, error=error, truncate=True),
                clean_text(
                    data[order_file]['header']['destination_address_code'],
                    4, error=error, truncate=True),
                clean_text(
                    detail['code'],
                    30, error=error, truncate=True),
                clean_text(
                    detail['quantity'],
                    12, error=error, truncate=True),
                clean_text(
                    counter,
                    4, error=error, truncate=True),
                clean_text(
                    detail['sequence'],
                    4, error=error, truncate=True),

                clean_text(
                    data[order_file]['header']['type'],
                    2, error=error, truncate=True),
                # price: added in spooler procedure
                )

            order = data[order_file]['header']['order']
            code = detail['code']
            sequence = detail['sequence']
            if order not in conversion:
                conversion[order] = {}
            if code in conversion[order]:
                # log error
                pass
            else:
                conversion[order][code] = sequence

            f_out.write(text_line)
        f_in.close()
        if error:
            continue

# Integrate data:
print(conversion)
pdb.set_trace()

from_path = '/home/openerp/mexal/ddtdussmann'
to_path = '/home/openerp/mexal/ddtdussmann/rielaborati'

for root, folders, files in os.walk(from_path):
    for filename in files:
        if not filename.endswith('txt'):
            print('Jump %s' % filename)
            continue
        fullname = os.path.join(root, filename)
        integrate = os.path.join(to_path, filename)
        new_f = open(integrate, 'w')
        pdb.set_trace()
        for row in open(fullname, 'r'):
            row = row.replace('\x00', ' ')
            left_row = row[:385]
            right_row = row[388:]
            default_code = row[54:84].strip()
            order = row[364:374].strip()
            error = False
            if len(order) <= 4:  # no order present
                new_row = row  # same line
            else:
                sequence = conversion.get(order, {}).get(default_code)
                if not sequence:
                    new_row = row  # same line
                else:
                    new_row = '%s%s%s' % (
                        left_row,
                        sequence[1:],  # remove left 0
                        right_row,
                    )

            new_f.write(new_row)
        new_f.close()
        pdb.set_trace()
    break  # No subfolder
