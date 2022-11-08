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
def sort_line(row):
    """ Generate order depend on start code, the row is the string generated
        for ERP (code 4th field)
    """
    code = row.split('|')[11].upper()
    start_1 = code[:1]
    start_2 = code[:2]
    start_3 = code[:3]

    # -------------------------------------------------------------------------
    # 3 char test start:
    # -------------------------------------------------------------------------
    if start_3 == 'SPA':
        return 4, code  # pasta

    # -------------------------------------------------------------------------
    # 2 char test start:
    # -------------------------------------------------------------------------
    if start_2 in ('SP', 'SS'):
        return 1, code  # freeze

    # -------------------------------------------------------------------------
    # 1 char test start:
    # -------------------------------------------------------------------------
    if start_1 in 'CDFPSV':
        return 1, code  # freeze
    elif start_1 in 'BILT':
        return 2, code  # fresh
    elif start_1 in 'HO':
        return 3, code  # dry
    elif start_1 in 'G':
        return 4, code  # pasta
    else: # Error list
        f_error = open('./sort_error.log', 'w')
        f_error.write(
            'Char not found %s - %s -%s\n' % (start_1, start_2, start_3))
        print('Char not found %s - %s - %s' % (start_1, start_2, start_3))
        f_error.close()
        return 5, code


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


def clean_date(company_date):
    """ Current format: YYMMDD
    """
    company_date = company_date.strip()
    if len(company_date) == 6:
        return '20%s%s%s' % (
            company_date[:-2],
            company_date[2:4],
            company_date[:2],
        )
    else:
        return '%s%s%s' % (
            company_date[:-4],
            company_date[2:4],
            company_date[:2],
        )


def reformat_date(company_date):
    """ Current format: DDMMYYYY in YYYYMMDD
    """
    return company_date[:-4] + company_date[2:4] + company_date[:2]

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


def log_on_file(message, mode='INFO', file_list=None, verbose=True):
    """ Write message in file list passed
        mode: INFO WARNING ERROR
    """
    if file_list is None:
        return False

    message_log = '%s. [%s] %s\n' % (datetime.now(), mode, message)
    if verbose:
        print(message_log.strip())

    for f_log in file_list:
        if not f_log:
            continue
        f_log.write(message_log)
    return True

# -----------------------------------------------------------------------------
# Read configuration parameter:
# -----------------------------------------------------------------------------
try:
    company = sys.argv[1]
    if len(company) > 3:
        print('Run: python ./pre_process.py CMP (must be max 3 char length)')
        sys.exit()
except:
    print('Launch program as:\n\npython ./pre_process.py CMP')
    sys.exit()

try:
    cfg_file = os.path.expanduser('./%s.cfg' % company)
except:
    print('Config file not found: %s.cfg' % company)
    sys.exit()

config = ConfigParser.ConfigParser()
config.read([cfg_file])

# In parameters:
in_check = os.path.expanduser(config.get('in', 'check'))
in_path = os.path.expanduser(config.get('in', 'path'))
in_history = os.path.expanduser(config.get('in', 'history'))
in_log = os.path.expanduser(config.get('in', 'log'))
in_schedule = os.path.expanduser(config.get('in', 'schedule'))

# Out parameters:
out_check = os.path.expanduser(config.get('out', 'check'))
out_path = os.path.expanduser(config.get('out', 'path'))
out_log = os.path.expanduser(config.get('out', 'log'))
out_schedule = os.path.expanduser(config.get('out', 'schedule'))
out_original = os.path.expanduser(config.get('out', 'original'))

# Mail parameters:
mail_error = config.get('mail', 'error')
mail_info = config.get('mail', 'info')

# Calculated parameters:
f_in_schedule = open(in_schedule, 'a')
f_in_log = open(in_log, 'a')

f_out_schedule = open(out_schedule, 'a')
f_out_log = open(out_log, 'a')

extension = 'txt'

# -----------------------------------------------------------------------------
# Check mount folder:
# -----------------------------------------------------------------------------
if in_check:
    if not os.path.exists(in_check):
        log_on_file(
            'Cannot mount IN folder: %s' % in_path, mode='ERROR', file_list=[
                f_in_schedule, f_out_schedule])
        sys.exit()

if out_check:
    if not os.path.exists(out_check):
        log_on_file(
            'Cannot mount OUT folder: %s' % out_path, mode='ERROR', file_list=[
                f_in_schedule, f_out_schedule])
        sys.exit()

# -----------------------------------------------------------------------------
# Read IN folder:
# -----------------------------------------------------------------------------
log_on_file(
    'Start import order mode: %s' % company, mode='INFO', file_list=[
        f_in_schedule, f_out_schedule])

for root, dirs, files in os.walk(in_path):
    log_on_file(
        'Read root folder: %s [%s]' % (root, company),
        mode='INFO',
        file_list=[f_in_log, f_out_log])

    for f in files:
        if not f.lower().endswith(extension):
            log_on_file(
                'Jump file not managed: %s' % f, mode='WARNING',
                file_list=[
                    f_in_schedule, f_out_schedule])
            continue
        # file_part = f.split('_')
        command = 'NEW'  # Only this!

        # Fullname needed:
        file_in = os.path.join(root, f)
        file_history = os.path.join(in_history, f)
        file_original = os.path.join(out_original, f)

        create_date = datetime.fromtimestamp(
            os.path.getctime(file_in)
            ).strftime('%Y%m%d_%H%M%S')

        file_out = os.path.join(
            out_path, '%s' % (
                '%s_%s_%s.txt' % (  # todo change date creation?
                    create_date, f[:-4], command),
                ))  # TODO change name

        # ---------------------------------------------------------------------
        # Read input file:
        # ---------------------------------------------------------------------
        error = []
        f_in = open(file_in, 'r')
        row_out = []
        log_on_file(
            'Parsing file: %s [%s]' % (file_in, company),
            mode='INFO',
            file_list=[f_in_log, f_out_log])

        counter = 0
        for line in f_in:
            counter += 1
            line = line.strip()
            if line.startswith('01'):  # Header block:
                header = {
                    'type': line[:2].strip(),
                    'sequence': line[2:7].strip(),
                    'order': line[7:23].strip(),
                    'date': line[23:29].strip(),
                    'deadline': line[29:35].strip(),
                    'company_code': line[35:51].strip(),
                    'destination_code': line[51:67].strip(),
                    'document': line[67:69].strip(),
                }
                continue
            # Detail lines:
            detail = {
                'type': line[:2].strip(),
                'sequence': line[2:7].strip(),
                'code': line[7:23].strip(),
                'name': line[23:63].strip(),
                'uom': line[63:65].strip(),
                'quantity': line[65:72].strip(),
                'price': line[72:81].strip(),
                'vat': line[67:69].strip(),
            }

            # -----------------------------------------------------------------
            # Convert row input file:
            # -----------------------------------------------------------------
            row_out.append(
                '%-3s|%-10s|%-10s|%-10s|%-8s|'
                '%-13s|%4s|%-16s|%-60s|%-2s|%15s|'
                '%-16s|%-60s|%-2s|%15s|'
                '%-8s|%-40s|%-40s|%-15s\r\n' % (
                    # Header:
                    clean_text(company, 3, error=error, truncate=True),  # args

                    # Destination code:
                    '',
                    clean_text(
                        header['destination_code'], 10, error=error,
                        truncate=True),
                    '',

                    clean_date(header['deadline']),
                    clean_text(
                        header['order'], 13, error=error, truncate=True),

                    # Line:
                    counter - 1,  # remove header line
                    clean_text(detail['code'], 16, error=error, truncate=True,
                               uppercase=True),
                    clean_text(detail['name'], 60, error=error, truncate=True),
                    clean_text(detail['uom'], 2, error=error, truncate=True,
                               uppercase=True),
                    clean_float(
                        detail['quantity'], 15, 2, 100.0, error=error),

                    # Supplier reference (here is the same)
                    clean_text(detail['code'], 16, error=error, truncate=True,
                               uppercase=True),
                    clean_text(detail['name'], 60, error=error, truncate=True),
                    clean_text(detail['uom'], 2, error=error, truncate=True,
                               uppercase=True),
                    clean_float(
                        detail['quantity'], 15, 2, 100.0, error=error),

                    # Footer:
                    clean_date(header['date']),
                    '',  # header note
                    '',  # line note
                    '',  # CIG
                    # todo price?
                    ))
        f_in.close()

        if error:
            log_on_file(
                'Error reading file: %s [%s]' % (error, company),
                mode='ERROR', file_list=[f_in_log, f_out_log])
            continue

        # ---------------------------------------------------------------------
        # Save file out:
        # ---------------------------------------------------------------------
        error = []
        # Convert file:
        f_out = open(file_out, 'w')

        # for line in sorted(row_out, key=lambda x: sort_line(x)):  todo sort?
        for line in row_out:
            f_out.write(line)
        f_out.close()

        if error:
            log_on_file(
                'Error generating out file: %s [%s]' % (error, company),
                mode='ERROR', file_list=[f_in_log, f_out_log])
            continue
        else:
            log_on_file(
                'Created file: %s [%s]' % (file_out, company),
                mode='INFO', file_list=[f_in_log, f_out_log])

        # ---------------------------------------------------------------------
        # History the in file:
        # ---------------------------------------------------------------------
        error = ''
        try:
            os.remove(file_original)
        except:
            pass
        try:
            shutil.copy(file_in, file_original)
            log_on_file(
                'History company file: %s [%s]' % (file_original, company),
                mode='INFO', file_list=[f_in_log, f_out_log])
        except:
            error += 'Error copy original folder %s >> %s' % (
                file_in, file_original)
        try:
            os.remove(file_history)
        except:
            pass
        try:
            shutil.move(file_in, file_history)
            log_on_file(
                'History supplier file: %s [%s]' % (file_history, company),
                mode='INFO', file_list=[f_in_log, f_out_log])
        except:
            error += 'Error moving file %s >> %s' % (file_in, file_history)

        if error:
            log_on_file(
                error, mode='ERROR', file_list=[f_in_log, f_out_log])
            # XXX TODO delete OUT file
            continue
    break  # only root folder is read

log_on_file(
    'End import order mode: %s' % company, mode='INFO', file_list=[
        f_in_schedule, f_out_schedule])

# -----------------------------------------------------------------------------
# History the in file:
# -----------------------------------------------------------------------------
try:
    if f_out_log:
        f_out_log.close()
    if f_in_schedule:
        f_in_schedule.close()
    if f_in_log:
        f_in_log.close()
    if f_out_schedule:
        f_out_schedule.close()
except:
    print('Error closing log file')
