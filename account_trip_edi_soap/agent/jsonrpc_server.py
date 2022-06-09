#!/usr/bin/python
###############################################################################
# Copyright (C) 2001-2015 Micronaet S.r.l. (<https://micronaet.com>)
# Developer: Nicola Riolini @thebrush
#            https://it.linkedin.com/in/thebrush
#            https://linktr.ee/nicolariolini
###############################################################################

import os
import sys
import hmac
import hashlib
import base64
import json
import uuid
import pytz
import pdb
from datetime import datetime
from zeep import Client
from flask import Flask, request
from flask import Response

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
        if passed namespace and wsdl root use that, instead of
        read from
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


@app.route('/API/v1.0/micronaet/launcher', methods=['POST'])
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
        #try:

        # -----------------------------------------------------------------
        # Call for token
        # -----------------------------------------------------------------
        try:
            # -----------------------------------------------------------------
            # Read parameters:
            # -----------------------------------------------------------------
            wsdl_root = bytes(parameter.get('wsdl_root'))
            namespace = bytes(parameter.get('namespace'))
            username = bytes(parameter.get('username'))
            timestamp = parameter.get('timestamp')
            number = parameter.get('number')
            hash_text = parameter.get('hash_text')

            #message_mask = 'GET+/users/%s/account+%s+%s'
            #username = bytes('GENERALFOOD')  # bytes('GENERALFOOD')
            #secret = bytes('5BC478479AB65798A4420F3FB19EF68E96ECFEA8')
            #namespace = bytes('{it.niuma.mscsoapws.ws}MscWsPortSoap11')
            #wsdl_root = bytes('https://layer7prod.msccruises.com/pep/wsdl')
            #timestamp = get_datetime_tz().strftime('%d%m%Y%H%M%S')

            #number = str(uuid.uuid4())[-6:]
            #message = message_mask % (username, timestamp, number)

            #signature = hmac.new(secret, msg=message,
            #                     digestmod=hashlib.sha256).digest()

            #hash_text = base64.b64encode(signature)

            # Call SOAP portal:
            service = get_soap_service(wsdl_root, namespace)
            res = service.login(
                username=username, time=timestamp, number=number,
                hash=hash_text)

            payload['reply']['res'] = eval(str(res))
            payload['success'] = True
            return payload
        except:
            print('Errore: %s' % (sys.exc_info(), ))
            payload['reply'].update({
                'error': 'Errore nella chiamata ad MSC portale: '
                         '{}'.format(account_command),
            })
            return payload
        # finally:
        #    pass

    elif command == 'order':
         pass
    elif command == 'invoice':
         pass
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
write_log(log_f, 'End ODOO-MSC Flask agent')
