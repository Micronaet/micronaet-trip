#!/usr/bin/python
###############################################################################
# Copyright (C) 2001-2015 Micronaet S.r.l. (<https://micronaet.com>)
# Developer: Nicola Riolini @thebrush
#            https://it.linkedin.com/in/thebrush
#            https://linktr.ee/nicolariolini
###############################################################################

import os
import hmac
import hashlib
import base64
import sys
import uuid
import pytz
import pdb
from flask import Flask, request
from datetime import datetime
from zeep import Client

try:
    import ConfigParser
except:
    try:
        import configparser as ConfigParser
    except:
        print('Errore importanto i parametri di avvio!')
        sys.exit()


# -----------------------------------------------------------------------------
#                                  Utility:
# -----------------------------------------------------------------------------
# LOG:
# -----------------------------------------------------------------------------
def write_log(log_f, message, mode='INFO', verbose=True):
    """ Write log file
    """
    complete_message = '%s [%s]: %s' % (
        str(datetime.now())[:19],
        mode,
        message,
    )
    if verbose:
        print(' * {}'.format(complete_message))
    log_f.write('{}\n'.format(complete_message))
    log_f.flush()

# -----------------------------------------------------------------------------
# SOAP:
# -----------------------------------------------------------------------------
def get_soap_service(wsdl_root=False, namespace=False):
    """ Get WSDL Service link
        if passed namespace and wsdl root use that, instead of read from
        parameters
    """
    client = Client(wsdl_root)
    return client.create_service(namespace, wsdl_root)


def get_datetime_tz():
        """ Change datetime removing gap from now and GMT 0
        """
        return pytz.utc.localize(datetime.now()).astimezone(
            pytz.timezone('Europe/Rome'))


# -----------------------------------------------------------------------------
# Read configuration parameter from external file:
# -----------------------------------------------------------------------------
current_path = os.path.dirname(__file__)
log_file = os.path.join(current_path, 'flask.log')
log_f = open(log_file, 'a')
write_log(log_f, 'Start ODOO-MSC Flask agent')
write_log(log_f, 'Flask log file: {}'.format(log_file))

config_files = [
    os.path.join(current_path, 'flask.cfg'),
]
for config_file in config_files:
    if not os.path.isfile(config_file):
        continue
    cfg_file = os.path.expanduser(config_file)

    config = ConfigParser.ConfigParser()
    config.read([cfg_file])
    host = config.get('flask', 'host')
    port = config.get('flask', 'port')
    write_log(log_f, 'Read config file: {}'.format(config_file))
    break
else:
    write_log(log_f, 'Read default parameter [0.0.0.0:5000]')
    host = '0.0.0.0'
    port = '5000'

# -----------------------------------------------------------------------------
# End point definition:
# -----------------------------------------------------------------------------
app = Flask(__name__)


@app.route('/API/v1.0/micronaet/laucher', methods=['POST'])
def ODOOCall():
    """ Master function for Micronaet Call

    """
    # -------------------------------------------------------------------------
    # Get parameters from call:
    # -------------------------------------------------------------------------
    params = request.get_json()
    rpc_call = params['params']
    command = rpc_call['command']
    parameter = rpc_call['parameters']

    # -------------------------------------------------------------------------
    #                             Execute call:
    # -------------------------------------------------------------------------
    # Start reply payload:
    payload = {
        'success': False,
        'reply': {

        },
    }
    # -------------------------------------------------------------------------
    #                       Import invoice procedure:
    # -------------------------------------------------------------------------
    if command == 'token':
        account_command = parameter.get('command')  # account command
        try:
            # -----------------------------------------------------------------
            # Read parameters:
            # -----------------------------------------------------------------
            soap_params = parameter.get('envelope')

            wsdl_root = soap_params.get('wsdl_root')
            namespace = soap_params.get('namespace')
            username = soap_params.get('username')
            timestamp = soap_params.get('timestamp')
            number = soap_params.get('number')
            hash_text = soap_params.get('hash_text')

            # -----------------------------------------------------------------
            # Call for token
            # -----------------------------------------------------------------
            try:
                # Call SOAP portal:
                service = get_soap_service(wsdl_root, namespace)
                res = service.login(
                    username=username, time=timestamp, number=number,
                    hash=hash_text)
                payload['reply']['res'] = res
            except:
                payload['reply'].update({
                    'error': 'Errore nella chiamata ad MSC portale: '
                             '{}'.format(account_command),
                })
                return payload

            # -----------------------------------------------------------------
            # Parse log file:
            # -----------------------------------------------------------------
            if os.path.isfile(invoice_log):
                log_f = open(invoice_log, 'r')
                log_error = log_f.readlines()
                log_f.close()
                payload['reply'].update({
                    'error': 'Errore gestionale [da log file batch]: '
                             '{}'.format(log_error),
                })
                return payload

                payload['reply'].update({
                    'error': error,
                })
                if len_reply >= 3 and reply_part[2]:
                    payload['reply'].update({
                        'sql_customer_code': reply_part[2],
                    })
                if len_reply >= 4 and reply_part[3]:
                    payload['reply'].update({
                        'sql_destination_code': reply_part[3],
                    })

            elif result_text.startswith('OK') and len(reply_part) == 5:
                # -------------------------------------------------------------
                # Print PDF command:
                # -------------------------------------------------------------
                invoice_number = reply_part[1]

                # Call PDF command (FT01_00001 (file) >> FT01/00001 (account)
                account_command_pdf = account_command_pdf.format(
                    invoice=invoice_number.replace('_', '/'))
                try:
                    os.system(account_command_pdf)
                    invoice_printed = True
                except:
                    invoice_printed = False

                # -------------------------------------------------------------
                # Result:
                # -------------------------------------------------------------
                payload['success'] = True  # Invoice generated (not sure print)
                payload['reply'].update({
                    'invoice_number': reply_part[1],
                    'invoice_date': reply_part[2],
                    'sql_customer_code': reply_part[3],
                    'sql_destination_code': reply_part[4],

                    # Print management:
                    'invoice_printed': invoice_printed,
                })
            else:
                payload['reply'].update({
                    'error': 'Errore non gestito o non correttamente '
                             'passato dal gestionale',
                })
        finally:
            # Write log for operation:
            '''
            if payload['success']:
                write_log(log_f, 'Call account: {} SUCCESS'.format(
                    account_command))
            else:
                write_log(log_f, 'Call account: {} NOT SUCCESS'.format(
                    account_command), mode='ERROR')
            '''

            # Clean sem file:
            os.remove(trafficlight)
    elif command == 'order':
        # ---------------------------------------------------------------------
        # Traffic-light management:
        # ---------------------------------------------------------------------
        trafficlight = parameter.get('trafficlight')

        # B. Create PID file:
        if os.path.isfile(trafficlight):
            payload['reply'].update({
                    'error': 'Esiste una importazione in esecuzione, '
                             'riprovare tra un '
                             'po\': {}'.format(trafficlight),
            })
            return payload

        # Traffic light file:
        pid_f = open(trafficlight, 'w')
        pid_f.write(str(datetime.now()))  # Write current date
        pid_f.close()

        account_command = parameter.get('command')  # account command
        account_command_pdf = parameter.get('command_pdf')  # PDF mask command
        # amount_total = parameter.get('amount_total')

        try:
            # -----------------------------------------------------------------
            # Read parameters:
            # -----------------------------------------------------------------
            invoice_file = parameter.get('invoice')
            invoice_result = parameter.get('result')
            invoice_log = parameter.get('log')
            content = parameter.get('content')
            # write_log(log_f, '[INFO] Call account: {}'.format(
            # account_command))

            # -----------------------------------------------------------------
            # Write invoice file
            # -----------------------------------------------------------------
            if invoice_file and content:
                invoice_f = open(invoice_file, 'w')
                invoice_f.write(content)
            else:
                payload['reply'].update({
                    'error': 'Impossibile salvare il file di interscambio: '
                             '{}'.format(invoice_file),
                })
                return payload
            invoice_f.close()

            # -----------------------------------------------------------------
            # Call Account for import:
            # -----------------------------------------------------------------
            try:
                # Kill result:
                if os.path.isfile(invoice_result):
                    os.remove(invoice_result)

                # Kill log file:
                if os.path.isfile(invoice_log):
                    os.remove(invoice_log)

                os.system(account_command)
            except:
                payload['reply'].update({
                    'error': 'Errore nella chiamata al gestionale: '
                             '{}'.format(account_command),
                })
                return payload

            # -----------------------------------------------------------------
            # Parse log file:
            # -----------------------------------------------------------------
            if os.path.isfile(invoice_log):
                log_f = open(invoice_log, 'r')
                log_error = log_f.readlines()
                log_f.close()
                payload['reply'].update({
                    'error': 'Errore gestionale [da log file batch]: '
                             '{}'.format(log_error),
                })
                os.remove(invoice_log)
                return payload

            # -----------------------------------------------------------------
            # Parse result file:
            # -----------------------------------------------------------------
            if not os.path.isfile(invoice_result):
                payload['reply'].update({
                    'error': 'Risposta non ricevuta dalla chiamata '
                        'al gestionale',
                })
                return payload

            result_f = open(invoice_result, 'r')
            result_text = result_f.read()
            reply_part = result_text.split(';')
            len_reply = len(reply_part)
            # Syntax: "KO; error; customer code; destination code"
            if result_text.startswith('KO'):
                if len_reply == 1:
                    error = 'Formato risposta gestionale non corretta'
                else:  # case >= 2
                    error = reply_part[1]  # Use 2nd item
                payload['reply'].update({
                    'error': error,
                })
                if len_reply >= 3 and reply_part[2]:
                    payload['reply'].update({
                        'sql_customer_code': reply_part[2],
                    })
                if len_reply >= 4 and reply_part[3]:
                    payload['reply'].update({
                        'sql_destination_code': reply_part[3],
                    })

            elif result_text.startswith('OK') and len(reply_part) == 5:
                # -------------------------------------------------------------
                # Print PDF command:
                # -------------------------------------------------------------
                invoice_number = reply_part[1]

                # Call PDF command (FT01_00001 (file) >> FT01/00001 (account)
                account_command_pdf = account_command_pdf.format(
                    invoice=invoice_number.replace('_', '/'))
                try:
                    os.system(account_command_pdf)
                    invoice_printed = True
                except:
                    invoice_printed = False

                # -------------------------------------------------------------
                # Result:
                # -------------------------------------------------------------
                payload['success'] = True  # Invoice generated (not sure print)
                payload['reply'].update({
                    'invoice_number': reply_part[1],
                    'invoice_date': reply_part[2],
                    'sql_customer_code': reply_part[3],
                    'sql_destination_code': reply_part[4],

                    # Print management:
                    'invoice_printed': invoice_printed,
                })
            else:
                payload['reply'].update({
                    'error': 'Errore non gestito o non correttamente '
                             'passato dal gestionale',
                })
        finally:
            # Write log for operation:
            '''
            if payload['success']:
                write_log(log_f, 'Call account: {} SUCCESS'.format(
                    account_command))
            else:
                write_log(log_f, 'Call account: {} NOT SUCCESS'.format(
                    account_command), mode='ERROR')
            '''

            # Clean sem file:
            os.remove(trafficlight)
    else:
        # ---------------------------------------------------------------------
        # Bad call:
        # ---------------------------------------------------------------------
        message = '[ERROR] ODOO is calling wrong command {}\n'.format(
            command)
        payload['reply'].update({
            'error': message.strip(),
        })

    # -------------------------------------------------------------------------
    # Prepare response
    # -------------------------------------------------------------------------
    return payload


app.run(debug=True, host=host, port=port)
write_log(log_f, 'End ODOO-Mexal Flask agent')
