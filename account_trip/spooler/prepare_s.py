#!/usr/bin/python
# -*- coding: utf-8 -*-
import os
import pdb
import sys
import pickle
import shutil
from datetime import datetime, timedelta
from os import listdir
from os.path import isfile, join
import ConfigParser

# -----------------------------------------------------------------------------
#                                 Parameters:
# -----------------------------------------------------------------------------
cfg_file = 'openerp_s.cfg'
config = ConfigParser.ConfigParser()
config.read(cfg_file)

# -----------------------------------------------------------------------------
# A. SMTP parameter for log mail:
# -----------------------------------------------------------------------------
smtp_server = config.get('smtp', 'server')
smtp_user = config.get('smtp', 'user')
smtp_password = config.get('smtp', 'password')
smtp_port = int(config.get('smtp', 'port'))
smtp_SSL = eval(config.get('smtp', 'SSL'))
from_addr = config.get('smtp', 'from_addr')

# -----------------------------------------------------------------------------
# B. Mexal parameters:
# -----------------------------------------------------------------------------
# mexal_company = config.get('mexal', 'company')
mexal_user = config.get('mexal', 'user')
mexal_password = config.get('mexal', 'password')

# -----------------------------------------------------------------------------
# C. General Parameters:
# -----------------------------------------------------------------------------
price_path = config.get('general', 'price_path')

# -----------------------------------------------------------------------------
# D. Command line parameter:
# -----------------------------------------------------------------------------
try:
    # Setup depend on parameter passed (default SDX if not present)
    company = sys.argv[1]
except:
    company = 'SDX'  # default company

# -----------------------------------------------------------------------------
# E. Company parameter:
# -----------------------------------------------------------------------------
smtp_subject_mask = '%s > %s' % (company, config.get('smtp', 'subject_mask'))
try:
    # Read parameters depend on start up company:
    char_cr = eval(config.get(company, 'return'))  # Return format
    split_file = eval(config.get(company, 'split_file'))  # Split or copy
    post_action = config.get(company, 'post_action')  # Action after import
    update_order = eval(config.get(company, 'update_order'))  # Update order

    if post_action == 'False':
        post_action = False

    # Log file from mexal (empty = OK, else error)
    file_err = config.get(company, 'file_err')
    mexal_company = config.get(company, 'company')
    to_addr = config.get(company, 'to_addr')
    path_in = config.get(company, 'path_in')  # Folder: in files
    path_in_original = os.path.join(path_in, 'original')  # todo create before!
    path_out = config.get(company, 'path_out')  # Folder: destination
    path_history = config.get(company, 'path_history')  # Folder: history
    log_file_name = config.get(company, 'log_file_name')
    sprix_number = config.get(company, 'sprix_number')
    urgent_order = eval(config.get(company, 'urgent_order'))
    # Scheduler log file:
    log_scheduler = config.get(company, 'log_scheduler_name')

    # Jump order too new:
    jump_order_days = eval(config.get(company, 'jump_order_days'))
    left_date_on_file = eval(config.get(company, 'left_date_on_file'))
    left_start_date = int(config.get(company, 'left_start_date'))
    left_days = int(config.get(company, 'left_days'))
    force_file = config.get(company, 'force')
except:
    print(
        '[ERR] Chiamata a ditta non presente '
        '(scelte possibili: SDX o ELI o BIB)')
    sys.exit()  # wrong company!

# -----------------------------------------------------------------------------
# Log files used:
# -----------------------------------------------------------------------------
log_file = open(log_file_name, 'a')
log_schedulers_file = open(log_scheduler, 'a')

# -----------------------------------------------------------------------------
#                           Utility function:
# -----------------------------------------------------------------------------
# A. Price integration setup:
# -----------------------------------------------------------------------------
price_setup = {
    # From / To code = position of code in order file
    # Separator used
    # Partic loaded only once
    'FAB': {
        'from_code': 162,
        'to_code': 173,  # Load only first 11 char (parent code)
        'separator': '|',
        'partic': {},  # Partic on file
        'remove': 2,
    },
    'HOS': {
        'from_code': 162,
        'to_code': 173,  # Load only first 11 char (parent code)
        'separator': '|',
        'partic': {},  # Partic on file
        'remove': 2,
    },
    'MRK': {
        'from_code': 65,  # todo Wrong position?
        'to_code': 76,  # Load only first 11 char (parent code)
        'separator': '|',
        'partic': {},  # Partic on file
        'remove': 2,
    },
    'DUS': {
        'from_code': 162,
        'to_code': 173,  # Load only first 11 char (parent code)
        'separator': '|',
        'partic': {},  # Partic on file
        'remove': 1,
    },
}


def integrate_price(order, order_original, company):
    """ Add price particularity when not present in EDI order
    """
    mail_error = ''
    partic_filename = os.path.join(price_path, '%s.csv' % company)
    # Read particularity once before update:
    setup = price_setup.get(company)  # this company (if present)

    # Check if need integration for price, partic file or setup must be present
    if not setup or not os.path.isfile(partic_filename):
        print('No price integration for %s' % company)
        return mail_error

    # Load particularity file for this operations:
    try:
        if not setup['partic']:
            lines = []
            for line in open(partic_filename):
                lines.append(line)

            # Sort line (last is the new price)
            # log_used = open(partic_filename + '.used', 'w')
            for line in sorted(lines):
                # log_used.write(line)  # Log operation
                default_code = line[:11].strip()
                # Last 6 char from here:
                price = float(line[28:].strip().replace(',', '.'))

                # Take last price:
                setup['partic'][default_code] = price
                # print('{} >> {}'.format(default_code, price))

                # Take the first price:
                # if default_code not in setup['partic']:
                #    setup['partic'][default_code] = price
                # else old prices

    except:
        mail_error += 'Errore leggendo il file per ricavare il prezzo, fare' \
                      'un debug per capire se sono disallineati i dati letti' \
                      'su ordine originale'
        return mail_error

    # Price integration:
    # Save order in original:
    if os.path.isfile(order_original):
        print('Original yet present (no price integration): '
              '%s' % order_original)
    else:
        print('Keep original order in: %s' % order_original)
        shutil.copy(order_in, order_original)
    try:
        new_filename = '%s.price' % order
        old_f = open(order_original, 'r')
        new_f = open(new_filename, 'w')
        for line in old_f:
            default_code = line[setup['from_code']:setup['to_code']]
            price = setup['partic'].get(default_code, 0.0)
            price = '%10.3f' % price
            new_line = '%s%s%s%s' % (
                line[:-setup['remove']],  # -len(char_cr)],  # remove EOL CR
                setup['separator'],
                price,
                char_cr,
            )
            new_f.write(new_line)
        old_f.close()
        new_f.close()
    except:
        mail_error += 'Errore integrando i prezzi sul file, fare un debug' \
                      'per capire dove va in errore'
        return mail_error

    # -------------------------------------------------------------------------
    # Replace file operation:
    # -------------------------------------------------------------------------
    # todo manage errors?
    # Delete original:
    try:
        os.remove(order)
    except:
        mail_error += 'Errore cancellando ordine pre integrazione prezzo,' \
                      'intervenire manualmente per rinominare il file .price'
        return mail_error

    # Restore new created:
    try:
        shutil.move(new_filename, order)
    except:
        mail_error += 'Errore rinominando file ordine con aggiunta presso' \
                      'su file originale per essere importato (fare un debug' \
                      'per capire dove va in errore)'
        return mail_error
    return mail_error


# -----------------------------------------------------------------------------
# B. Pickle function:
# -----------------------------------------------------------------------------
def store_forced(filename, forced_list):
    """ Load pickle file in a list that is returned
    """
    try:
        pickle.dump(forced_list, open(filename, 'wb'))
        return True
    except:
        return False


def load_forced(filename):
    """ Load list of forced from file
    """
    try:
        res = pickle.load(open(filename, 'rb')) or []
        return res
    except:
        return []


# -----------------------------------------------------------------------------
# C. Log function:
# -----------------------------------------------------------------------------
def log_message(log_file, message, model='info'):
    """ Write log file and print log file
        log_file: handles of file
        message: text of message
        model: type of message, like: 'info', 'warning', 'error'
    """
    log_file.write('[%s] %s: %s\n' % (
        model.upper(),
        datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
        message, ))
    print(message)
    return


def log_scheduler_message(log_file, message):
    """ Log scheduler information (start stop)
    """
    log_file.write('%s: %s\n' % (
        datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
        message, ))
    print(message)
    return


# -----------------------------------------------------------------------------
# D. File function:
# -----------------------------------------------------------------------------
def get_timestamp_from_file(file_in, path_in, company='ELI'):
    """ Get timestamp value from file name
        File is: ELIORD20141103091707.ASC
                 ------YYYYMMGGhhmmss----
        Millisecond are
            00 for create order ELIORD
            10 for delete order ELICHG
    """
    if company == 'ELI':
        return '%s-%s-%s %s:%s:%s.%s' % (
            file_in[6:10],   # Year
            file_in[10:12],  # Month
            file_in[12:14],  # Day
            file_in[14:16],  # Hour
            file_in[16:18],  # Minute
            file_in[18:20],  # Second
            '00' if file_in.startswith('ELIORD') else '10'  # Millisecond
            )
    else:  # company == 'SDX':
        return datetime.fromtimestamp(
            os.path.getctime(join(path_in, file_in)))


# E. SMTP function:
def get_smtp(log_message):
    # Start session with SMTP server
    try:
        from smtplib import SMTP, SMTP_SSL
        if smtp_SSL:
            smtp = SMTP_SSL()
        else:
            smtp = SMTP()
        smtp.set_debuglevel(0)
        smtp.connect(smtp_server, smtp_port)
        smtp.login(smtp_user, smtp_password)
        log_message(
            log_file,
            'Connesso al server %s:%s User: %s Pwd: %s' % (
                smtp_server, smtp_port, smtp_user, smtp_password))
        return smtp
    except:
        log_message(
            log_file,
            'Impossibile collegarsi server %s:%s User: %s Pwd: %s' % (
                smtp_server, smtp_port, smtp_user, smtp_password),
            'error', )
        return False


# -----------------------------------------------------------------------------
#                    Program: (NO CHANGE OVER THIS LINE)
# -----------------------------------------------------------------------------
log_scheduler_message(
    log_schedulers_file, 'Start importation [EDI: %s]' % company)

# Mexal parameters:
mxdesk = r'C:\Passepartout\PassClient\mxdesk1297479000\prog\mxdesk.exe'
sprix_command = r'%s -command=mxrs.exe -a%s -t0 -x2 win32g -p%s -k%s:%s' % (
    mxdesk, mexal_company, sprix_number, mexal_user, mexal_password)

# todo (change depend on number of day left)
if datetime.today().weekday() in (3, 4, 5):
    left_days += 2
    log_message(log_file, 'Aggiunto due giorni extra alla data')

max_date = (datetime.today() + timedelta(days=left_days)).strftime('%Y%m%d')
log_message(log_file, 'Valutazione scadenza (salto se >= %s)' % max_date)

# Get list of files and sort before import
file_list = []

try:
    # Sort correctly the files:
    for file_in in [f for f in listdir(path_in) if isfile(join(path_in, f))]:
        file_list.append(
            (get_timestamp_from_file(file_in, path_in, company), file_in))
    file_list.sort()

    # Print list of sorted files for log the operation:
    for ts, file_in in file_list:
        log_message(
            log_file, 'ID: Date: %s\t File: %s' % (ts, file_in))
except:
    log_message(
        log_file,
        'Impossibile leggere i file da elaborare, script terminato',
        'error', )
    sys.exit()

# Import files sorted
order_imported = ''
for ts, file_in in file_list:
    # -------------------------------------------------------------------------
    #                    Controlli pre importazione:
    # -------------------------------------------------------------------------
    # A. Jump file to delivery in 'left_days' days (usually 3):
    if jump_order_days:
        if left_date_on_file:
            fin = open(join(path_in, file_in), 'r')
            test_date = fin.readline()[left_start_date:left_start_date + 8]
            fin.close()
        else:  # on filename
            test_date = file_in[left_start_date:left_start_date + 8]

        # B. Load every time the force list:
        force_list = load_forced(force_file)
        if file_in in force_list:
            force_list.remove(file_in)
            store_forced(force_file, force_list)  # todo if not imported??
            log_message(log_file, 'Importazione forzata: %s > %s' % (
                path_in, file_in))

        elif test_date >= max_date:
            # C. Urgent order:
            if urgent_order and urgent_order in file_in:
                log_message(
                    log_file, 'Importazione urgente: %s > %s' % (
                        path_in, file_in))
            else:
                log_message(
                    log_file,
                    'File saltato [%s] limite %s < data file %s' % (
                        file_in, max_date, test_date), 'warning')
                continue
    else:
        test_date = 'Data non letta'

    # -------------------------------------------------------------------------
    #                            File da importare:
    # -------------------------------------------------------------------------
    log_message(log_file, 'Divisione file: %s > %s' % (path_in, file_in))
    mail_error = ''  # reset for every file readed

    # -------------------------------------------------------------------------
    # A. Remove log file (if present):
    # -------------------------------------------------------------------------
    try:
        os.remove(file_err)
    except:
        pass

    # Input file (to be splitted):
    order_in = join(path_in, file_in)
    order_original = join(path_in_original, file_in)

    # todo integrate also order references here (company 8)?
    # -------------------------------------------------------------------------
    # B. Integrate price in file:
    # -------------------------------------------------------------------------
    integrate_error = integrate_price(order_in, order_original, company)
    if integrate_error:
        mail_error += integrate_error
    else:
        # ---------------------------------------------------------------------
        # C. Split procedure:
        # ---------------------------------------------------------------------
        order_1 = join(path_out, 'ordine.1.txt')
        order_2 = join(path_out, 'ordine.2.txt')

        # C1. File splitted
        if split_file:
            # Output file parameters
            # (open every loop because closed after import):
            file_out = {
                open(order_1, 'w'): [0, 2036],
                open(order_2, 'w'): [2036, 3507],  # 1561
                }
            fin = open(order_in, 'r')

            for line in fin:
                position = 0
                for f in file_out:
                    f.write('%s%s' % (
                        line[file_out[f][0]: file_out[f][1]],
                        char_cr,
                        ))

            # Close all file (input and 2 splitted)
            for f in file_out:
                try:
                    f.close()
                except:
                    mail_error += 'Errore chiudendo file split\n'
            try:
                fin.close()
            except:
                mail_error += 'Errore chiudendo il file di input\n'
        else:
            # C1. File not splitted, just renamed
            try:
                shutil.copy(order_in, order_1)
            except:
                mail_error += 'Errore copiando il file (no split)\n'

        # ---------------------------------------------------------------------
        # D. Mexal import:
        # ---------------------------------------------------------------------
        try:
            comment_err = 'Chiamata mexal client'
            os.system(sprix_command)

            # D1. Post action:
            if post_action:
                os.system(post_action)

            # D2. Read error file for returned error:
            comment_err = 'apertura file'
            f_err = open(file_err, 'r')
            comment_err = 'lettura file'
            test_err = f_err.read().strip()  # ok if work
            comment_err = 'test contenuto file'
            if test_err[:2] != 'ok':
                comment_err = 'test contenuto file ko'
                mail_error += test_err or 'Errore generico (non gestito)'
                # todo save order created reference here?
            else:
                comment_err = 'test contenuto file ok'
                result = test_err.split(';')
                order_imported += \
                    '\tCliente %s - Interno: %s (Scad.: %s)\n' % (
                        result[1], result[2], test_date)
                log_message(log_file, ' Ordine importato: %s' % (result, ))

                # D3. Update order in Oerp:
                if update_order:
                    try:
                        os.system(
                            r's:\script\update\update_order_s.cmd %s %s %s' % (
                                company,
                                result[1].strip(),
                                result[2].strip(),
                            ))
                    except:
                        pass  # Raise error?

            comment_err = 'chiusura file'
            f_err.close()

        except:
            mail_error += \
                'Errore generico di importazione (file log non trovato)' \
                '[%s]!' % comment_err

    # -------------------------------------------------------------------------
    # E. Final log via e-mail:
    # -------------------------------------------------------------------------
    if mail_error:
        log_message(
            log_file, 'Errore leggendo il file: %s' % mail_error, 'error')

        # Send mail for error (every file):
        smtp = get_smtp(log_message)
        if smtp:
            smtp.sendmail(
                from_addr, to_addr,
                'From: %s\nTo: %s\nSubject: %s\n\n%s' % (
                    from_addr, to_addr,
                    smtp_subject_mask % file_in,
                    mail_error,
                    ))
            smtp.quit()
            log_message(
                log_file, 'Invio mail errore importazione: da %s, a %s, \n'
                          '\t<<<%s\t>>>' % (
                              from_addr, to_addr, mail_error))
        else:
            log_message(
                log_file,
                'Mail errore importazione non inviata %s, a %s, \n'
                '\t<<<%s\t>>>' % (
                    from_addr, to_addr, mail_error), 'error')

    else:
        # ---------------------------------------------------------------------
        # F. History the file (only if no error)
        # ---------------------------------------------------------------------
        try:
            os.rename(join(path_in, file_in), join(path_history, file_in))
            log_message(
                log_file, 'Importato il file e storicizzato: %s' % file_in)
        except:
            log_message(
                log_file, 'Errore storicizzando il file: %s' % file_in,
                'error')

# -----------------------------------------------------------------------------
# Final log for all order imported in the session:
# -----------------------------------------------------------------------------
if order_imported:  # Comunicate importation
    smtp = get_smtp(log_message)
    if smtp:
        smtp.sendmail(
            from_addr, to_addr,
            'From: %s\nTo: %s\nSubject: %s\n\n%s' % (
                from_addr,
                to_addr,
                'Ordini importati',
                order_imported,
                ))
        smtp.quit()
        log_message(
            log_file, 'Mail ordini importati: da %s, a %s, \n\t<<<%s\t>>>' % (
                from_addr, to_addr, order_imported))
    else:
        log_message(
            log_file,
            'Mail ordini importati non inviata: da %s, a %s, \n'
            '\t<<<%s\t>>>' % (
                from_addr, to_addr, order_imported), 'error')

# -----------------------------------------------------------------------------
# Close operations:
# -----------------------------------------------------------------------------
# Scheduler log:
log_scheduler_message(
    log_schedulers_file, 'Stop importation [EDI: %s]' % company)

# Close open files
try:
    log_file.close()
except:
    pass
