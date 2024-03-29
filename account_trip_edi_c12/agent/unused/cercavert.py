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
# Procedura per controllare i documenti pre invio al cliente così da
# verificare che siano presenti tutti i numeri di riga per il collegamento
# tra ordine fatto e merce ricevuta
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
    cfg_file = os.path.expanduser('./SER.cfg')
except:
    print('Config file not found: SER.cfg')
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
from_path = os.path.expanduser('~/etl/edi/sercar/check')
to_path = os.path.expanduser('~/cron/sercar/output')

for mode in ('ddt', 'oc'):
    mexal_db = {}
    from_file = os.path.join(from_path, '%s.csv' % mode)
    for line in open(from_file, 'r'):
        line = line.strip()
        row = line.split(';')
        reference = row[0].strip()
        order = row[1].strip().replace('-', '')
        if not order:
            print('No order jump line')
            continue
        code = row[2].strip()
        key = (order, code)
        mexal_db[key] = reference  # reference  # Save all line

    file_original = os.path.join(to_path, 'Controllo_%s.csv' % mode)
    f_out = open(file_original, 'w')

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

            # -----------------------------------------------------------------
            # Read input file:
            # -----------------------------------------------------------------
            error = []
            f_in = open(file_in, 'r')

            counter = 0
            for line in f_in:
                # Clean base 64 data (clean start editor char):
                line = line.replace('\xff', '').replace('\xfe', '').replace(
                    '\x00', '')
                if not line:
                    continue  # Jump empty line

                # -------------------------------------------------------------
                # Create file every code break:
                # -------------------------------------------------------------
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

                key = (data[order_file]['header']['order'], detail['code'])
                mexal_line = mexal_db.get(key, '')
                if mexal_line:
                    text_line = '%-20s|%-20s|%-30s|%-12s|%-4s|%-4s\r\n' % (
                        # Mexal
                        clean_text(
                            mexal_line,
                            20, error=error, truncate=True),

                        clean_text(
                            data[order_file]['header']['order'],
                            20, error=error, truncate=True),
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
                        )
                    f_out.write(text_line)

                '''# Only subtype
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
                    '''
            f_in.close()
            if error:
                continue

