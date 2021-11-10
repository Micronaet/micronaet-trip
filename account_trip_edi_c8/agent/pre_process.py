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

    # Test based on 1 or 2 start char:
    if start_1 in 'HO' or start_2 == 'SP': # XXX has S - SP problem so first
        return 3, code  # dry
    elif start_1 in 'CDFPSV':  # XXX has S - SP problem so second test
        return 1, code  # freeze
    elif start_1 in 'BILT':
        return 2, code  # fresh
    elif start_1 in 'G':
        return 4, code  # pasta
    else: # Error list
        # Log error:
        f_error = open('./sort_error.log', 'w')
        f_error.write('Char not found %s - %s\n' % (start_1, start_2))
        print('Char not found %s - %s' % (start_1, start_2))
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


def clean_date(date, error=None):
    """ Return clean text with limit cut
        Log in error if over length
    """
    if error is None:
        error = []
    date = date or ''
    if len(date) != 8:
        error.append('Error not date: %s' % date)
    return date


def clean_float(value, length, decimal=3, separator='.', error=None):
    """ Clean float and return float format
    """
    if error is None:
        error = []
    try:
        value = value.replace(',', '.')
        float_value = float(value.strip())
        float_value = float_value / (10 ^ decimal)
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
f_in_schedule = False # open(in_schedule, 'a')
f_in_log = False #open(in_log, 'a')

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
        if f[:2] == 'OF':
            command = 'NEW'
        elif f[:2] == 'CF':
            command = 'UPD'
        else:
            log_on_file(
                'File %s unmanaged [%s]' % (f, company),
                mode='ERROR',
                file_list=[f_in_log, f_out_log])
            continue

        command = (file_part[2][:3]).upper() # New, Upd, Can

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
        for line in f_in:
            row = line.split(separator)
            if line[:2] in ('TM', 'FM'):
                # Not used (start and end line)
                continue
            if len(row) != tot_col:
                log_on_file(
                    'Different number columns: %s [%s]' % (file_in, company),
                    mode='INFO', file_list=[f_in_log, f_out_log])
                break

            # -----------------------------------------------------------------
            # Read fields:
            # -----------------------------------------------------------------
            date = create_date[:8] # From create date
            deadline = clean_date(row[3], separator='', out_format='iso',
                error=error)

            # Char:
            code = clean_text(row[1], 9, error=error)
            cook_center = ('%s-%s' % (
                clean_text(row[1], 20, error=error),
                clean_text(row[2], 20, error=error),
                ))[:60]  # XXX Trunc
            address = ''  # clean_text(row[3], 60, error=error)
            cap = ''  # clean_text(row[4], 5, error=error) # XXX Check
            city = ''  # clean_text(row[5], 60, error=error) # XXX Check
            province = ''  # clean_text(row[6], 4, uppercase=True, error=error)
            order = clean_text(row[4], 15, error=error)  # TODO different
            default_code = clean_text(row[10], 16, uppercase=True, error=error)
            default_code_supplier = clean_text(
                row[6], 16, uppercase=True, error=error)
            name = clean_text(row[11], 60, error=error, truncate=True)
            um = clean_text(row[12], 2, uppercase=True, error=error)

            # Float:
            quantity = clean_float(row[13], 15, 3, error=error)
            price = ''  # clean_float(row[13], 15, 3, error=error)
            cost = ''  # clean_float(row[14], 15, 3, error=error)

            # -----------------------------------------------------------------
            # Convert row input file:
            # -----------------------------------------------------------------
            row_out.append(
                '%3s|%3s|%-8s|%-9s|%-60s|%-60s|%-5s|%-60s|%-4s|%-15s|%-16s|'
                '%-16s|%-60s|%-2s|%-15s|%-15s|%-15s|%-8s\r\n' % (
                    # Header:
                    company,  # depend on parameter
                    command,
                    deadline,
                    code,
                    cook_center,
                    address,
                    cap,
                    city,
                    province,
                    order,  # 15

                    # Row:
                    default_code,
                    default_code_supplier,
                    name,
                    um,
                    quantity,
                    price,
                    cost,
                    date,
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

        # sorted_row = sorted(row_out, key=lambda x: sort_line(x))  # TODO
        sorted_row = row_out

        for line in sorted_row:
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
