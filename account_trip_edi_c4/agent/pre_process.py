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

# -----------------------------------------------------------------------------
# Read configuration parameter:
# -----------------------------------------------------------------------------
try:
    company = sys.argv[1]
    if len(company) >= 3:
        print 'Launch program as:\n\npython ./pre_process.py CMP\n'
            '(CMP must be max 3 char length)' 
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

# Mail parameters:
mail_error = config.get ('mail', 'error')
mail_info = config.get ('mail', 'info')

# TODO put in config file:
separator = ';'
tot_col = 15

# -----------------------------------------------------------------------------
# Read IN folder:
# -----------------------------------------------------------------------------
for root, dirs, files in os.walk(in_path):
    for f in files:
        # Fullname needed:
        file_in = os.path.join(root, f)
        file_historty = os.path.join(in_history, f)
        
        # TODO change destination filename
        file_out = os.path.join(out_path, f)
        
        # ---------------------------------------------------------------------
        # Read input file:
        # ---------------------------------------------------------------------
        error = []
        f_in = open(file_in, 'r')
        row_out = []
        for line in f_in:
            row = line.split(separator)
            if len(row) != tot_col:
                # TODO log error
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
            quantity = clean_float(row[12], 15, 3, error=error)
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
        # TODO error no 
        if error: 
            # TODO Log error
            continue
        
        # ---------------------------------------------------------------------
        # Save file out:
        # ---------------------------------------------------------------------
        # TODO error management:
        error = []
        # Convert file:
        f_out = open(file_out, 'w')
        for line in row_out:
            f_out.write(line)
        f_out.close()
        
        # ---------------------------------------------------------------------
        # History the in file:
        # ---------------------------------------------------------------------
        if error:
            # TODO Log error
            continue
        
        # TODO error management
        shutil.move(file_in, file_history)
            
    break # only root folder is read
