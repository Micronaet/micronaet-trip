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
# try:
#    cfg_file = os.path.expanduser('./DUS.cfg')
# except:
#    print('Config file not found: DUS.cfg')
#    sys.exit()

# config = ConfigParser.ConfigParser()
# config.read([cfg_file])

# In parameters:
# in_check = os.path.expanduser(config.get('in', 'check'))
# in_path = os.path.expanduser(config.get('in', 'path'))
# in_history = os.path.expanduser(config.get('in', 'history'))
# in_log = os.path.expanduser(config.get('in', 'log'))
# in_schedule = os.path.expanduser(config.get('in', 'schedule'))
extension = 'txt'

# -----------------------------------------------------------------------------
# Read IN folder:
# -----------------------------------------------------------------------------
history_path = os.path.expanduser('~/etl/edi/dussmann/order/history')
to_path = os.path.expanduser('~/cron/dussmann/output')

file_original = os.path.join(to_path, 'Controllo_destinazioni.csv')
f_out = open(file_original, 'w')
f_out.write('Numero|Anno|Codice dest.|Descrizione dest.|Data|Ora\n')
pdb.set_trace()
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
            code = line[15:25]
            description = line[365:406]

            f_out.write('%s%s%s%s%s%s\n' % (
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
