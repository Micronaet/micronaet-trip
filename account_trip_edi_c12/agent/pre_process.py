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
    else:  # Error list
        f_error = open('./sort_error.ser.log', 'w')
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


def clean_date(date):
    """ Current format: YYMMDD
    """
    return (date or '').strip()


def clean_float(
        value, length, decimal=3, multiple=1.0, separator='.', error=None):
    """ Clean float and return float format
        todo change?
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
        print('Run: python ./pre_process.py SER (must be max 3 char length)')
        sys.exit()
except:
    print('Launch program as:\n\npython ./pre_process.py SER')
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
out_history = os.path.expanduser(config.get('out', 'history'))

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

line_mask = '%-3s|%-10s|%-10s|%-10s|%-8s|' \
            '%-13s|%4s|%-16s|%-60s|%-2s|%15s|' \
            '%-16s|%-60s|%-2s|%15s|' \
            '%-8s|%-40s|%-40s|%-15s|%-40s|%-2s|%-11s\r\n'

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

        # Fullname needed:
        command = 'NEW'  # Only this!
        file_in = os.path.join(root, f)
        create_date = datetime.fromtimestamp(
            os.path.getctime(file_in)).strftime('%Y%m%d_%H%M%S')
        file_history = os.path.join(in_history, f)
        file_original = os.path.join(out_original, f)

        # ---------------------------------------------------------------------
        # Read input file:
        # ---------------------------------------------------------------------
        error = []
        data = {}  # Order split at the end of procedure

        f_in = open(file_in, 'r')
        log_on_file(
            'Parsing file: %s [%s]' % (file_in, company),
            mode='INFO', file_list=[f_in_log, f_out_log])

        counter = 0
        for line in f_in:
            # Parse mode:
            if not line or line.startswith('FTL'):  # FTL = end of detail line
                pass  # Jump empty line

            elif line.startswith('BGM'):
                # -------------------------------------------------------------
                # Header line 1 (start new order block!):
                # -------------------------------------------------------------
                order_year = line[150:154].strip()
                order_number = line[115:150].strip()

                if not order_number or not order_year:
                    log_on_file(
                        'Error cannot read order or year: %s [%s]' % (
                            file_in, company),
                        mode='ERROR', file_list=[f_in_log, f_out_log])

                # Create data block, generate filename for every order included
                order_file = '%s_%s_%s_%s.%s' % (
                    order_year,  # Year
                    order_number,  # Number
                    create_date,  # Date of file (not date order!)
                    command,  # Mode
                    extension,   # Extension same as original
                )

                # Not present in data so created here first time:
                data[order_file] = {
                    'counter': 0,
                    'line': [],
                    'file_out': os.path.join(
                        out_path, order_file),

                    'description': '',
                    'header': {
                        # todo clean list (will be updated every header line!)
                        'type': '',  # used?
                        'order': order_number,
                        # '%s-%s' % (order_year, order_number),
                        'date': line[150:159].strip(),  # YYYYMMDD format

                        # -----------------------------------------------------
                        # Destination:
                        # -----------------------------------------------------

                        # -----------------------------------------------------
                        # Compiled next lines:
                        # -----------------------------------------------------
                        # 'destination_code': '',  NAD line
                        # 'destination_description': '',  # NAD line
                        # 'deadline': '',  # DTM line

                        # -----------------------------------------------------
                        # Not used:
                        # -----------------------------------------------------
                        # 'stock_type': '',  # Tipo mag.:
                        # 'company_code': '',  # Codice mag.:
                        # Indirizzo del magazzino:
                        # 'destination_address_code': '',

                        # 'cig': '',
                        # 'sequence': line[2:7].strip(),
                        # 'document': line[67:69].strip(),
                        # 'destination_facility': (26, 33),  # OK Stock code
                        # 'destination_cost': (21, 25),  # OK CDC
                        # 'destination_site': (33, 37),  # OK Address code
                    },
                }

            elif line.startswith('NAS'):  # Header line 2:
                pass  # Destination (Company reference)

            elif line.startswith('NAB'):  # Header line 3:
                pass  # Sender (Edi Company reference)

            elif line.startswith('NAD'):  # Header line 4:
                data[order_file]['header'].update({
                    'destination_code': 'SER%s' % line[3:20].strip(),
                    'destination_description': line[23:69].strip(),
                    })

            elif line.startswith('DTM'):  # Header line 5:
                data[order_file]['header'].update({
                    'deadline': line[3:11].strip(),  # YYYYMMDD format
                    })

            elif line.startswith('FTX'):  # Header line 6:
                pass  # Currency

            elif line.startswith('LIN'):  # Detail line:
                # Detail lines:
                detail = {
                    'type': '',  # line[:2].strip(),
                    'sequence': line[3:9].strip(),
                    'code': line[82:117].strip(),
                    'name': line[152:187].strip(),
                    'uom': line[205:208].strip(),
                    'quantity': line[190:205].strip(),  # is x 1000!
                    'price': line[208:223].strip(),
                    'vat': '',   # line[67:69].strip(),
                    }

                # -------------------------------------------------------------
                # Convert row input file:
                # -------------------------------------------------------------
                data[order_file]['counter'] += 1

                # Update with SER + Code
                alternative_code = \
                    data[order_file]['header']['destination_code']

                # Append description for sale order (code and destination)
                if not data[order_file]['description']:
                    data[order_file]['description'] = '%s\n%s' % (
                        'Centro di costo: %s' % alternative_code,
                        data[order_file]['header'][
                            'destination_description'],
                    )

                data[order_file]['line'].append(
                    line_mask % (
                        # Header:
                        clean_text(company, 3, error=error, truncate=True),

                        # Destination code:
                        '',
                        clean_text(
                            alternative_code, 10, error=error, truncate=True),
                        '',

                        clean_date(data[order_file]['header']['deadline']),
                        clean_text(
                            data[order_file]['header']['order'], 13,
                            error=error, truncate=True),

                        # Line:
                        # data[order_file]['counter'],
                        clean_text(detail['sequence'], 4, error=error,
                                   truncate=True, uppercase=False),
                        clean_text(detail['code'], 16, error=error,
                                   truncate=True, uppercase=True),
                        clean_text(detail['name'], 60, error=error,
                                   truncate=True),
                        clean_text(detail['uom'], 2, error=error,
                                   truncate=True, uppercase=True),
                        clean_float(
                            detail['quantity'], 15, 2, 1000.0, error=error),

                        # Supplier reference (here is the same)
                        clean_text(detail['code'], 16, error=error,
                                   truncate=True, uppercase=True),
                        clean_text(detail['name'], 60, error=error,
                                   truncate=True),
                        clean_text(detail['uom'], 2, error=error,
                                   truncate=True, uppercase=True),
                        clean_float(
                            detail['quantity'], 15, 2, 1000.0, error=error),

                        # Footer:
                        clean_date(data[order_file]['header']['date']),
                        '',  # header note
                        '',  # line note
                        '',  # CIG,
                        clean_text(
                            data[order_file]['header'][
                                'destination_description'],
                            40, error=error, truncate=True),
                        '',   # Header type,
                        clean_float(
                            detail['price'], 11, 3, 1000.0, error=error),
                        ))
            else:
                print('Wrong syntax in this reference: %s' % line[:3])

        f_in.close()

        if error:
            log_on_file(
                'Error reading file: %s [%s]' % (error, company),
                mode='ERROR', file_list=[f_in_log, f_out_log])
            continue

        # ---------------------------------------------------------------------
        # Save file out:
        # ---------------------------------------------------------------------
        for order_name in data:
            check_history_file = os.path.join(out_history, order_name)
            if os.path.exists(check_history_file):
                log_on_file(
                    'Order yet present in history, jumped: %s [%s]' % (
                        order_name, company),
                    mode='ERROR', file_list=[f_in_log, f_out_log])
                continue

            # todo check also if in history present
            error = []  # Error when exporting one of this orders

            # Convert file:
            file_out = data[order_name]['file_out']
            f_out = open(file_out, 'w')  # if present override!

            # for line in sorted(data, key=lambda x: sort_line(x)):  todo sort?
            last_line = ''
            for line in data[order_name]['line']:
                f_out.write(line)
                last_line = line

            # -----------------------------------------------------------------
            # Append description:
            # -----------------------------------------------------------------
            if last_line:
                description_mask = '%s                |%%-60s%s' % (
                    last_line[:65],
                    # 16 code | 60 desciption
                    last_line[142:],
                    )
                for comment in data[order_name]['description'].split('\n'):
                    while comment:
                        description = comment[:60]  # left 60 char
                        comment = comment[60:]
                        f_out.write(description_mask % description)
            f_out.close()

            if error:
                log_on_file(
                    'Error generating out file: %s [%s]' % (error, company),
                    mode='ERROR', file_list=[f_in_log, f_out_log])
                # continue
            else:
                log_on_file(
                    'Created file: %s [%s]' % (file_out, company),
                    mode='INFO', file_list=[f_in_log, f_out_log])

        # ---------------------------------------------------------------------
        #           History the attachment file (after all):
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
            # XXX todo delete OUT file
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
