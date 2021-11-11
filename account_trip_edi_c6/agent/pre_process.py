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
        return (5, code)


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


def clean_date(italian_date, separator='', out_format='iso', error=None):
    """ Return clean text with limit cut
        Log in error if over length
    """
    if error is None:
        error = []
    italian_date = italian_date.split(' ')[0] # remove hour block
    if len(italian_date) != 10:
        error.append('Error not italian date: %s' % italian_date)
        # not stopped
    if out_format == 'iso':
        return '%s%s%s%s%s' % (
            italian_date[-4:],
            separator,
            italian_date[3:5],
            separator,
            italian_date[:2],
            )
    elif out_format == 'italian':
        return '%s%s%s%s%s' % (
            italian_date[:2],
            separator,
            italian_date[3:5],
            separator,
            italian_date[-4:],
            )
    elif out_format == 'english':
        return '%s%s%s%s%s' % (
            italian_date[3:5],
            separator,
            italian_date[:2],
            separator,
            italian_date[-4:],
            )
    else:  # incorrect format:
        return italian_date  # nothing todo


def clean_float(value, length, decimal=3, separator='.', error=None):
    """ Clean float and return float format
    """
    if error is None:
        error = []
    try:
        value = value.replace(',', '.')
        float_value = float(value.strip())
    except:
        error.append('Not a float: %s' % value)
        float_value = 0.0

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
pdb.set_trace()
try:
    company = sys.argv[1]
    if len(company) > 3:
        print('Run: python ./pre_process.py CMP (must be max 3 char length)')
        sys.exit()
except:
    print('Launch program as:\n\npython ./pre_process.py CMP')

try:
    cfg_file = os.path.expanduser('./%s.cfg' % company)
except:
    print('Config file not found: %s.cfg' % company)

config = ConfigParser.ConfigParser()
config.read([cfg_file])

# In parameters:
in_check = os.path.expanduser(config.get('in', 'check'))
in_path = os.path.expanduser(config.get('in', 'path'))
in_history = os.path.expanduser(config.get('in', 'history'))
in_log = os.path.expanduser(config.get('in', 'log'))
in_schedule = os.path.expanduser(config.get('in', 'schedule'))

# Outp arameters:
out_check = os.path.expanduser(config.get('out', 'check'))
out_path = os.path.expanduser(config.get('out', 'path'))
out_log = os.path.expanduser(config.get('out', 'log'))
out_schedule = os.path.expanduser(config.get('out', 'schedule'))
out_original = os.path.expanduser(config.get('out', 'original'))

# Mail parameters:
mail_error = config.get('mail', 'error')
mail_info = config.get('mail', 'info')

# TODO put in config file:
separator = config.get('file', 'separator')
tot_col = eval(config.get('file', 'tot_col'))

# Calculated parameters:
f_in_schedule = False  # open(in_schedule, 'a')
f_in_log = False  # open(in_log, 'a')

f_out_schedule = open(out_schedule, 'a')
f_out_log = open(out_log, 'a')

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
        file_part = f.split('_')
        command = (file_part[2][:3]).upper()  # New, Upd, Can

        # Fullname needed:
        file_in = os.path.join(root, f)
        file_history = os.path.join(in_history, f)
        file_original = os.path.join(out_original, f)

        create_date = datetime.fromtimestamp(
            os.path.getctime(file_in)
            ).strftime('%Y%m%d_%H%M%S')

        file_out = os.path.join(
            out_path, '%s' % (
                '%s_%s' % (create_date, f),
                )) # TODO change name

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
        for line in f_in:
            row = line.split(separator)
            if row[0] == 'TM':
                # Start header:
                print('Found header in %s file' % f)
                continue
            if row[0] == 'FM':
                # End order:
                # todo check total lines?
                print('Found end of line in %s file' % f)
                continue

            if len(row) != tot_col:
                log_on_file(
                    'Different number columns: %s [%s]' % (file_in, company),
                    mode='INFO', file_list=[f_in_log, f_out_log])
                break

            # -----------------------------------------------------------------
            # Read fields:
            # -----------------------------------------------------------------
            date = create_date[:8]  # From create date

            # Char:
            cdc = clean_text(row[0], 9, error=error)
            code = clean_text(row[1], 9, error=error)
            cook_center = clean_text(row[2], 9, error=error)
            deadline = clean_date(
                row[3], separator='', out_format='iso', error=error)
            order = clean_text(row[4], 10, error=error)
            sequence = clean_text(row[5], 4, error=error)
            default_code = clean_text(row[6], 16, uppercase=True, error=error)
            name = clean_text(row[7], 60, error=error, truncate=True)
            um = clean_text(row[8], 2, uppercase=True, error=error)
            quantity = clean_float(row[9], 15, 2, error=error)

            # Company fields:
            default_code_supplier = clean_text(
                row[10], 16, uppercase=True, error=error)
            name_supplier = clean_text(row[11], 60, error=error, truncate=True)
            um_supplier = clean_text(row[12], 2, uppercase=True, error=error)
            quantity_supplier = clean_float(row[13], 15, 2, error=error)

            order_note = clean_text(
                row[14], 40, error=error, truncate=True)
            line_note = clean_text(
                row[15], 40, error=error, truncate=True)
            cig = clean_text(
                row[16], 15, error=error)

            # -----------------------------------------------------------------
            # Convert row input file:
            # -----------------------------------------------------------------
            row_out.append(
                '%3s|%9s|%-9s|%-9s|%8s|%-10s|%4s|%16s|%60s|%2s|%-15s|'
                '%-16s|%60s|%2s|%15s|%8s|%40s|%40s|%15\r\n' % (
                    # Header:
                    company,  # depend on parameter
                    cdc,
                    code,
                    cook_center,
                    deadline,

                    order,
                    sequence,
                    default_code,
                    name,
                    um,
                    quantity,

                    default_code_supplier,
                    name_supplier,
                    um_supplier,
                    quantity_supplier,

                    date,

                    # New:
                    order_note,
                    line_note,
                    cig,
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

        for line in sorted(row_out, key=lambda x: sort_line(x)):
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
            error += 'Error copy orginal folder %s >> %s' % (
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
    break # only root folder is read

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
