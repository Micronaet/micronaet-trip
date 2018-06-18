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
import pdb; pdb.set_trace()

# -----------------------------------------------------------------------------
# Utility:
# -----------------------------------------------------------------------------
def clean_text(text, length, uppercase=False, error=None):
    ''' Return clean text with limit cut
        Log in error if over length
    '''
    if error is None:
        error = []

    text = text.strip()
    if len(text) > length:
        error.append('Text: %s > %s' % (text, length))
    if uppercase:
        return text.upper()
    return text    

def clean_date(italian_date, separator='', out_format='iso', error=None):
    ''' Return clean text with limit cut
        Log in error if over length
    '''
    if error is None:
        error = []

    if len(italian_date) != 10:
        error.append('Error not italian date: %s' % italian_date)
        # not stopped

    if out_format == 'iso': 
        return '%s%s%s%s%s' % (
            italian_date[-4:],
            separator,
            italian_date[5:7],
            separator,        
            italian_date[:2],
            )
    elif out_format == 'italian': 
        return '%s%s%s%s%s' % (
            italian_date[:2],
            separator,
            italian_date[5:7],
            separator,        
            italian_date[-4:],
            )
    elif out_format == 'english': 
        return '%s%s%s%s%s' % (
            italian_date[5:7],
            separator,
            italian_date[:2],
            separator,        
            italian_date[-4:],
            )
    else: # incorrect format:        
        return italian_date # nothing todo

def clean_float(value, length, decimal=3, separator='.', error=None):
    ''' Clean float and return float format 
    '''
    if error is None:
        error = []
    try:    
        float_value = float(value.strip())
    except:
        error.append('Not a float: %s' % value)
    
    mask = '%%%s.%sf' % (length, decimal)
    res = mask % float_value
    res = res.replace('.', separator)
    return res

def log_on_file(message, mode='INFO', file_list=None):
    ''' Write message in file list passed
        mode: INFO WARNING ERROR
    '''
    if file_list is None:
        return False

    message_log = f_log.write('%s. [%s] %s' % (
        datetime.now(), mode, message))
        
    for f_log in file_list:
        f_log.write(message_log)
    return True
            
# -----------------------------------------------------------------------------
# Read configuration parameter:
# -----------------------------------------------------------------------------
try:
    company = sys.argv[1]
    if len(company) >= 3:
        print 'Run: python ./pre_process.py CMP (must be max 3 char length)'
        sys.exit()
except:
    print 'Launch program as:\n\npython ./pre_process.py CMP' 

try:
    cfg_file = os.path.expanduser('./%s.cfg' % company)
except:
    print 'Config file not found: %s.cfg' % company 

config = ConfigParser.ConfigParser()
config.read([cfg_file])

# In parameters:
in_check = os.expanduser(config.get('in', 'check'))
in_path = os.expanduser(config.get('in', 'path'))
in_history = os.expanduser(config.get('in', 'history'))
in_log = os.expanduser(config.get('in', 'log'))
in_schedule = os.expanduser(config.get('in', 'schedule'))

# Outp arameters:
out_check = os.expanduser(config.get('out', 'check'))
out_path = os.expanduser(config.get('out', 'path'))
out_log = os.expanduser(config.get('out', 'log'))
out_schedule = os.expanduser(config.get('out', 'schedule'))
out_original = os.expanduser(config.get('out', 'original'))

# Mail parameters:
mail_error = config.get('mail', 'error')
mail_info = config.get('mail', 'info')

# TODO put in config file:
separator = config.get('file', 'separator')
tot_col = eval(config.get('file', 'tot_col'))

# Calculated parameters:
f_out_log = open(in_log, 'a')
f_in_schedule = open(in_schedule, 'a')
f_in_log = open(out_log, 'a')
f_out_schedule = open(out_schedule, 'a')

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
        # Fullname needed:
        file_in = os.path.join(root, f)
        file_historty = os.path.join(in_history, f)        
        file_original = os.path.join(out_orignal, f)        
        file_out = os.path.join(out_path, '%s' % f) # TODO change name
        
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
            if len(row) != tot_col:
                log_on_file(
                    'Different number columns: %s [%s]' % (file_in, company),
                    mode='INFO',
                    file_list=[f_in_log, f_out_log])  
                break
            
            # -----------------------------------------------------------------
            # Read fields:
            # -----------------------------------------------------------------
            deadline = clean_date(row[0], 10, error)
            
            # Char:
            code = clean_text(row[1], 9, error)
            cook_center = clean_text(row[2], 10, error) # XXX check 
            address = clean_text(row[3], 60, error)
            cap = clean_text(row[4], 5, error) # XXX Check
            city = clean_text(row[5], 60, error) # XXX Check
            province = clean_text(row[6], 60, error, uppercase=True)
            order = clean_text(row[7], 10, error)
            default_code = clean_text(row[8], 16, error, uppercase=True)
            default_code_supplier = clean_text(
                row[9], 16, error, uppercase=True)
            name = clean_text(row[10], 60, error)
            um = clean_text(row[11], 2, error, uppercase=True)
            
            # Float:
            quantity = clean_float(row[12], 15, 2, error=error)
            price = clean_float(row[13], 15, 3, error=error)
            cost = clean_float(row[14], 15, 3, error=error)

            # -----------------------------------------------------------------
            # Convert row input file:
            # -----------------------------------------------------------------
            row_out.append(            
                '%3s|%-10s|%-9s|%-10s|%-60s|%-5s|%-60s|%-60s|%-10s|%-16s|%-16s|'
                '%-60s|%-2s|%-15s|%-15s|%-15s\r\n' % (
                    company, # depend on parameter
                    deadline,
                    code,
                    cook_center,
                    address,
                    cap,
                    city,
                    province,
                    order,
                    default_code,
                    default_code_supplier,
                    name,
                    um,
                    quantity,
                    price,
                    cost,
                    ))
        f_in.close()
        
        if error:
            log_on_file(
                'Error reading file: %s [%s]' % (error, company), 
                mode='ERROR', 
                file_list=[f_in_log, f_out_log])
            continue
        
        # ---------------------------------------------------------------------
        # Save file out:
        # ---------------------------------------------------------------------
        error = []
        # Convert file:
        f_out = open(file_out, 'w')
        for line in row_out:
            f_out.write(line)
        f_out.close()
        if error:
            log_on_file(
                'Error generating out file: %s [%s]' % (error, company), 
                mode='ERROR', 
                file_list=[f_in_log, f_out_log])
            continue
        
        # ---------------------------------------------------------------------
        # History the in file:
        # ---------------------------------------------------------------------        
        error = ''
        try:
            shutil.copy(file_in, file_original)
        except:
            error += 'Error copy orginal folder %s >> %s' % (
                file_in, file_original)
        try:
            shutil.move(file_in, file_history)
        except:
            error += 'Error moving file %s >> %s' % (file_in, file_history)

        if error:
            log_on_file(
                error,
                mode='ERROR', 
                file_list=[f_in_log, f_out_log])
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
    f_out_log.close()
    f_in_schedule.close()
    f_in_log.close()
    f_out_schedule.close()
except:
    print 'Error closing log file'
