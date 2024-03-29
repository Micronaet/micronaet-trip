# -*- coding: utf-8 -*-
###############################################################################
#
# OpenERP, Open Source Management Solution
# Copyright (C) 2001-2015 Micronaet S.r.l. (<http://www.micronaet.it>)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################

import os
import pdb
import sys
import logging
import openerp
import shutil
import re
import openerp.netsvc as netsvc
import openerp.addons.decimal_precision as dp
from openerp.osv import fields, osv, expression, orm
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from openerp import SUPERUSER_ID
from openerp import tools
from openerp.tools.translate import _
from openerp.tools.float_utils import float_round as round
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT,
    DEFAULT_SERVER_DATETIME_FORMAT,
    DATETIME_FORMATS_MAP,
    float_compare)

_logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# SOAP:
# -----------------------------------------------------------------------------
import hmac
import hashlib
import base64
import uuid
import pytz
import requests
import json

#try:
from zeep import Client
#except:
#    _logger.error('Install zeep dept.: pip install zeep')


class EdiSoapConnection(orm.Model):
    """ Soap Parameter for connection
    """
    _name = 'edi.soap.connection'
    _description = 'EDI Soap Connection'
    _rec_name = 'name'
    _order = 'name'

    # -------------------------------------------------------------------------
    # Custom parameter
    # -------------------------------------------------------------------------
    _response_status = {
        0: u'Nessun Errore',
        1: u'Credenziali non valide',
        2: u'Dati non disponibili',
        3: u'Dati errati',  # Campi con i dati errati
        4: u'PON non esistente',
        5: u'Numero Ordine non ammesso per il fornitore',
        6: u'Dati acquisti - Ordine incompleto',
        7: u'Dati acquisti - Righe non presenti in ordine',  # Righe in più
        8: u'Ordine non necessita di logistica',
        9: u'Logistica già inviata a click',
        10: u'Limite temporale superato',
        11: u'File supera dimensione massima',
        12: u'Errore nel salvataggio del file',
        13: u'Token di accesso errato',
        14: u'Token di accesso non più valido',
        99: u'Internal Server Error',
        }

    # -------------------------------------------------------------------------
    # Utility function:
    # -------------------------------------------------------------------------
    def _get_datetime_tz(self, ):
        """ Change datetime removing gap from now and GMT 0
        """
        return pytz.utc.localize(datetime.now()).astimezone(
            pytz.timezone('Europe/Rome'))

    def _get_error_status(self, status_code):
        """ Return error comment:
        """
        return self._response_status.get(
            status_code, 'Errore non gestito: %s' % status_code)

    def _get_soap_service(
            self, cr, uid, ids, wsdl_root=False, namespace=False,
            context=None):
        """ Get WSDL Service link
            if passed namespace and wsdl root use that, instead of read from
            parameters
        """
        if not wsdl_root:  # Read from parameters
            parameter = self.browse(cr, uid, ids, context=context)[0]
            namespace = parameter.namespace
            wsdl_root = parameter.wsdl_root

        client = Client(wsdl_root)
        return client.create_service(
            namespace,
            wsdl_root,
            )

    def check_return_status(self, res, comment):
        """ Check returned status error
        """
        # client.settings(force_https=False)

        # Parameters
        header = _('SOAP Error')
        error_mask = _('Cannot connect with SOAP [%s]: %s')

        # XXX Status code 14 > New login!
        try:
            status_code = res['operationOutcome']['statusCode']
        except:
            raise osv.except_osv(
                header,
                error_mask % (comment, 'Unmanaged error!'),
                )

        if status_code: # if present means error!
            raise osv.except_osv(
                header,
                error_mask % (comment, self._get_error_status(status_code))
                )

        _logger.info('Server response OK')

    def _soap_login(self, cr, uid, ids, context=None):
        """ Login and get token from WSDL
        """
        if context is None:
            context = {}
        force_reload = context.get('force_reload', True)
        parameter = self.browse(cr, uid, ids, context=context)[0]

        # Get all parameters:
        message_mask = 'GET+/users/%s/account+%s+%s'
        username = bytes(parameter.username)
        secret = bytes(parameter.secret)
        namespace = bytes(parameter.namespace)
        # Ex.: '{it.niuma.mscsoapws.ws}MscWsPortSoap11'
        wsdl_root = bytes(parameter.wsdl_root)
        # Ex.: 'https://layer7test.msccruises.com/pep/wsdl'  DEMO
        # Ex.: 'https://layer7prod.msccruises.com/pep/wsdl'  PRODUCTION
        token = parameter.token
        # Flask agent present:
        flask_host = parameter.flask_host
        flask_port = parameter.flask_port

        # ---------------------------------------------------------------------
        # Check if present last token saved:
        # ---------------------------------------------------------------------
        if not force_reload and token:
            _logger.warning('Token yet present, use that')
            return token

        # ---------------------------------------------------------------------
        #                                 LOGIN:
        # ---------------------------------------------------------------------
        # Parameter for call:
        timestamp = self._get_datetime_tz().strftime('%d%m%Y%H%M%S')

        number = str(uuid.uuid4())[-6:]
        message = message_mask % (username, timestamp, number)

        # HMAC encrypt:
        signature = hmac.new(
            secret,
            msg=message,
            digestmod=hashlib.sha256,
            ).digest()
        hash_text = base64.b64encode(signature)

        # ---------------------------------------------------------------------
        #                           CALL MODE:
        # ---------------------------------------------------------------------
        # Flask Agent:
        # ---------------------------------------------------------------------
        if flask_host:
            # Authenticate to get Session ID:
            url = 'http://%s:%s/API/v1.0/micronaet/launcher' % (
                flask_host, flask_port)
            headers = {
                'content-type': 'application/json',
            }
            payload = {
                'jsonrpc': '2.0',
                'params': {
                    'command': 'token',
                    'parameters': {
                        'wsdl_root': wsdl_root,
                        'namespace': namespace,
                        'username': username,
                        'timestamp': timestamp,
                        'number': number,
                        'hash_text': hash_text,
                    },
                }
            }
            response = requests.post(
                url, headers=headers, data=json.dumps(payload))
            response_json = response.json()
            if response_json['success']:
                res = response_json.get('reply', {}).get('res')
            else:
                res = {}  # No reply

        # ---------------------------------------------------------------------
        # Direct:
        # ---------------------------------------------------------------------
        else:  # todo this part raise error:
            service = self._get_soap_service(
                cr, uid, ids, wsdl_root, namespace, context=context)

            res = service.login(
                username=username, time=timestamp, number=number,
                hash=hash_text)

        self.check_return_status(res, 'Login')

        # Get new token and save for next calls:
        token = res['accessToken']
        self.write(cr, uid, ids, {
            'token': token,
            }, context=context)
        _logger.warning('Token reloaded')
        return token

    # -------------------------------------------------------------------------
    # Scheduled events:
    # -------------------------------------------------------------------------
    def scheduled_load_new_invoice(self, cr, uid, context=None):
        """ Scheduled new invoice
        """
        _logger.info('Start import load invoice for logistic order')
        for connection_id in self.search(cr, uid, [], context=context):
            self.load_new_invoice(cr, uid, [connection_id], context=context)
        return True

    # -------------------------------------------------------------------------
    # Button events:
    # -------------------------------------------------------------------------
    # Server:
    def load_new_invoice(self, cr, uid, ids, context=None):
        """ Load invoice from file
        """
        # ---------------------------------------------------------------------
        # Function
        # ---------------------------------------------------------------------
        def log_data(log_f, comment, mode='INFO', newline='\r\n'):
            """ Write comment on log file:
            """
            return log_f.write('%s [%s] %s%s' % (
                datetime.now(),
                mode,
                comment,
                cr,
                ))

        def clean_line(line):
            """ Clean line
            """
            remove_list = [('\xb0\xb0', '.'), ('\xc2\xb0', '.')]

            line = line.strip()
            for item1, item2 in remove_list:
                line = line.replace(item1, item2)
            return line

        def get_float(value):
            """ Clean weight text:
            """
            value = value.strip().replace('.', ' ')
            try:
                return float(value.split()[-1].replace(',', '.'))
            except:
                _logger.error('Cannot parse float: %s' % value)
                return 0.0  # TODO raise error

        def get_last_day(month):
            """ Last day of the month
            """
            if month in ('02', 2):
                return '28'
            elif month in ('01', '03', '05', '07', '08', '10', '12',
                           1, 3, 5, 7, 8, 10, 12):
                return '31'
            else:
                return '30'

        def get_lot_date(value):
            """ Extract lot data
                Format present: 4-22 04-22 5/22 05/22
            """
            if not value:
                return False
            value = value.replace('-', '/')
            part = value.split('/')
            try:
                month, year = part
                day = get_last_day(month)
                date = '20%02d-%02d-%s' % (int(year), int(month), day)
                datetime.strptime(date, '%Y-%m-%d')  # test
                _logger.info('Date: %s >> %s' % (value, date))
                return date
            except:
                _logger.error('Not a Lot date: %s' % value)
                return False

        def get_date(value):
            """ Clean weight text:
            """
            value = value.strip()
            try:
                if len(value) == 10:
                    year = value[-4:]
                    month = value[3:5]
                elif len(value) == 8:
                    if '/' in value:  # 01/12/22
                        month = value[3:5]
                        year = '20' + value[-2:]
                    else:  # 01122022
                        month = value[2:4]
                        year = value[-4:]
                else:
                    _logger.error('Cannot parse date: %s' % value)
                    return False
                res = '%s-%s-%s' % (year, month, value[:2])
                return res

            except:
                _logger.error('Cannot parse date: %s' % value)
                return False

        def get_int(value):
            """ Clean weight text:
            """
            value = value.strip()
            try:
                return int(value.replace(',', '.'))
            except:
                _logger.error('Cannot parse int: %s' % value)
                return 0  # TODO raise error

        def check_startwith(text, start, key):
            """ Check if element passed start with key of start DB
                (could be a list)
                @return extra part on the right
            """
            if key not in start:
                _logger.error('Key %s not in Start %s' % (key, start))
                return False

            key = start[key]  # Read list of keys form start
            text = text.strip()
            if type(key) in (tuple, list):  # multiple
                for item in key:
                    if text.startswith(item):
                        return text[len(item):].strip()
                return False  # not found
            else:  # single
                if text.startswith(key):
                    return text[len(key):].strip()

        # ---------------------------------------------------------------------
        # Pool used:
        # ---------------------------------------------------------------------
        logistic_pool = self.pool.get('edi.soap.logistic')
        line_pool = self.pool.get('edi.soap.logistic.line')
        pallet_pool = self.pool.get('edi.soap.logistic.pallet')
        order_pool = self.pool.get('edi.soap.order')
        product_pool = self.pool.get('product.product')
        mapping_pool = self.pool.get('edi.soap.mapping')

        # ---------------------------------------------------------------------
        # Parameters:
        # ---------------------------------------------------------------------
        newline = '\r\n'
        html_newline = '<br />'
        start = {
            # Row number:
            'customer_order': 2,
            'invoice': 3,
            'invoice_date': 4,

            # Start text:
            'header': 'HEADER',
            'detail': 'DETAIL',
            'weight': 'PESO LORDO',

            # 'order': ('P.O.N.', 'N.ORDINE', 'PON'),
            # 'lord': ('PESO LORDO KG:', 'PESO LORDO'),
            # 'total': ('PESO LORDO KG:', 'PESO TOTALE'),
            'pallet': ('BANCALI NR:', 'BANCALI N.', 'BANCALI PVC NR:'),
            'delivery_date': 'CONSEGNA DEL',
            }

        # Load parameters:
        parameter = self.browse(cr, uid, ids, context=context)[0]
        separator = parameter.detail_separator
        invoice_path = os.path.expanduser(parameter.server_root)
        partner_start = parameter.server_account_code.split('|')
        pon_code = parameter.server_pon_code

        if not partner_start or not invoice_path or not pon_code:
            raise osv.except_osv(
                _('Error'),
                _('Check parameter on SOAP Configuration!'),
                )
        partner_len = len(partner_start[0])

        # ---------------------------------------------------------------------
        # Extra path:
        # ---------------------------------------------------------------------
        # Path used:
        pdf_path = os.path.join(invoice_path, 'pdf')
        path = os.path.join(invoice_path, 'csv')
        # Also SSCC but not generated here!

        history_path = os.path.join(path, 'history')
        unsed_path = os.path.join(path, 'unsed')
        log_path = os.path.join(path, 'log')

        # Create process (path not included!):
        for folder in (history_path, unsed_path, log_path, pdf_path):
            os.system('mkdir -p %s' % folder)

        # ---------------------------------------------------------------------
        # Clean operation (unused files):
        # ---------------------------------------------------------------------
        for check_path in (path, pdf_path):
            for root, folders, files in os.walk(check_path):
                for filename in files:
                    if filename[:partner_len] not in partner_start:
                        os.remove(os.path.join(root, filename))
                        _logger.warning('Remove file not used: %s' % filename)
                break  # No subfolder check

        # ---------------------------------------------------------------------
        # Check folder for files:
        # ---------------------------------------------------------------------
        log_f = open(os.path.join(log_path, 'invoice.log'), 'w')
        history_list = []

        for root, folders, files in os.walk(path):
            for filename in files:
                try:
                    if not filename.lower().endswith('csv'):
                        _logger.error('File not used: %s' % filename)
                        continue

                    fullname = os.path.join(root, filename)
                    if filename[:partner_len] not in partner_start:
                        continue  # jump unused files

                    history_list.append(
                        (fullname, os.path.join(history_path, filename)))

                    log_data(log_f, 'File checked: %s' % filename)

                    # Read file (last part)
                    data = {  # Collect order data
                        'i': 0,
                        'text': '',
                        'detail_status': 'off',
                        'product_insert': False,  # for double weight
                        'detail_text': '',
                        'error': False,
                        'error_comment': '',

                        'pallet': 1,
                        'delivery_date': False,

                        # 'header': '',
                        # 'detail': [],
                        # 'footer': {},
                        }

                    # ---------------------------------------------------------
                    # Read all file and save always from header
                    # ---------------------------------------------------------
                    file_rows = []
                    for line in open(fullname):
                        if line.startswith(start['header']):
                            file_rows = []  # reset when find header!
                        file_rows.append(clean_line(line))

                    for line in file_rows:
                        data['i'] += 1
                        line = line.strip()

                        # -----------------------------------------------------
                        # Check part of document:
                        # -----------------------------------------------------
                        line_mode = 'normal'
                        if line.startswith(start['header']):
                            data.update({
                                'header': line,
                                'i': 1,  # Restart from 1
                                'text': '',
                                # line + newline, # Restart from here

                                'detail': [],
                                'footer': {},
                                })
                        elif line.startswith(start['detail']):
                            data['detail_status'] = 'on'

                        # -----------------------------------------------------
                        #                         Header data:
                        # -----------------------------------------------------
                        elif data['i'] == start['customer_order']:
                            # Custom. order
                            data['customer_order'] = line
                        elif data['i'] == start['invoice']:
                            # Invoice number
                            data['invoice'] = line
                        elif data['i'] == start['invoice_date']:
                            # Invoice date
                            data['invoice_date'] = line

                        # -----------------------------------------------------
                        #                         Detail data:
                        # -----------------------------------------------------
                        elif data['detail_status'] == 'on':  # Start details
                            if line.startswith(separator):  # Detail line
                                # 1. Article line:
                                data['detail_text'] = line
                                data['product_insert'] = False
                            elif not data['product_insert'] and \
                                    start['weight'] in line:  # weight line (2)
                                # 2A. Error: Weight double
                                data['detail'].append((
                                    data['detail_text'],
                                    get_float(line),
                                    line.split()[0],  # customer code
                                    ))
                                data['product_insert'] = True

                            elif data['product_insert'] and \
                                    start['weight'] in line:  # weight line (2)
                                # 2B. Check error (ex. 2 PESO LORDO line)
                                _logger.warning('Extra line: %s' % line)
                                line_mode = 'error'

                            else:
                                # 3. Comment line:
                                data['detail_status'] = 'end'
                            # else:
                            #    data['error'] = True
                            #    data['error_comment'] += \
                            #        '%s Detail without correct schema' %
                            #        data['i']

                        # -----------------------------------------------------
                        #         End of document part (always done):
                        # -----------------------------------------------------
                        if data['detail_status'] == 'end':  # Start details
                            # CONSEGNA DEL:

                            # DESTINAZIONE:

                            # -------------------------------------------------
                            # Extract remain line:
                            # -------------------------------------------------
                            # order_line =
                            # check_startswith(line, start, 'order')
                            delivery_line = check_startwith(
                                line, start, 'delivery_date')
                            # lord_line =
                            # check_startswith(line, start, 'lord')
                            # total_line =
                            # check_startswith(line, start, 'total')

                            pallet_line = check_startwith(
                                line, start, 'pallet')

                            # -------------------------------------------------
                            # Extract needed data:
                            # -------------------------------------------------
                            # if order_line:
                            #    pass # XXX get in first line of file no needed

                            if delivery_line:
                                data['delivery_date'] = get_date(
                                    delivery_line.split()[-1])

                            # elif lord_line:
                            #    pass # XXX needed?

                            # elif total_line:
                            #    pass # XXX needed?

                            elif pallet_line:
                                try:
                                    data['pallet'] = int(pallet_line)
                                except:
                                    data['pallet'] = 0
                                    _logger.error(
                                        'Cannot decode pallet: %s' % line)

                        # -----------------------------------------------------
                        # Keep only last part of the file:
                        # -----------------------------------------------------
                        if line_mode == 'error':
                            data['text'] += \
                                '<font color="red">%s</font><br/>' % (line, )
                        else:
                            data['text'] += '%s<br />' % line

                    # ---------------------------------------------------------
                    # Create ODOO Record:
                    # ---------------------------------------------------------
                    name = '%s del %s' % (
                        data['invoice'], data['invoice_date'])
                    logistic_ids = logistic_pool.search(cr, uid, [
                        ('name', '=', name),
                        ], context=context)
                    if logistic_ids:
                        # No unlink admitted!
                        logistic = logistic_pool.browse(
                            cr, uid, logistic_ids, context=context)[0]

                        if logistic.state != 'draft':
                            # Yet load cannot override:
                            # TODO move in after folder (unused)
                            _logger.error(
                                'Order yet present, cannot be deleted: %s' %
                                name)
                            continue
                        else:
                            _logger.error(
                                'Order yet present, deleted: %s' % name)

                        # Delete and override:
                        logistic_pool.unlink(
                            cr, uid, logistic_ids, context=context)

                    # Bug management:
                    text = data['text'].replace('\xb0', ' ')

                    # ---------------------------------------------------------
                    # Link to order
                    # ---------------------------------------------------------
                    customer_order = data['customer_order']

                    # Update order if is full name or partial:
                    if customer_order.split('-')[-1] != pon_code:
                        customer_order = '%s-%s' % (
                            customer_order,
                            pon_code,
                            )

                    order_ids = order_pool.search(cr, uid, [
                        ('name', '=', customer_order),
                        ], context=context)
                    if order_ids:
                        order_id = order_ids[0]
                    else:
                        _logger.error(
                            'Cannot link logistic to generator order!')
                        order_id = False

                    # A. Import order:
                    logistic_id = logistic_pool.create(cr, uid, {
                        'name': name,
                        'order_id': order_id,
                        'connection_id': ids[0],
                        'text': text,
                        'pallet': data['pallet'],
                        'delivery_date': data['delivery_date'],
                        'customer_order': customer_order,
                        # 'filename':
                        }, context=context)

                    # B. Link pallet:
                    default_pallet_id = False
                    default_pallet = False
                    if order_id:
                        pallet_ids = pallet_pool.search(cr, uid, [
                            ('order_id', '=', order_id),
                            ], context=context)
                        pallet_pool.write(cr, uid, pallet_ids, {
                            'logistic_id': logistic_id,
                            }, context=context)
                        if len(pallet_ids):
                            # todo Check if 1st
                            default_pallet_id = pallet_ids[0]
                            default_pallet = pallet_pool.browse(
                                cr, uid, default_pallet_id,
                                context=context).name
                        else:
                            default_pallet_id = False
                            default_pallet = False

                    # C. Import order line:
                    sequence = 0
                    invoice_date = get_date(data['invoice_date'])

                    for row, lord_qty, customer_code in data['detail']:
                        sequence += 1
                        line_part = row.split(separator)

                        mapping_id = False
                        if customer_code.startswith('F'):
                            # Link mapping data:
                            mapping_ids = mapping_pool.search(cr, uid, [
                                ('name', '=', customer_code),
                                ], context=context)

                            if mapping_ids:
                                mapping_id = mapping_ids[0]
                        else:  # Wrong code:
                            _logger.error('Wrong code %s' % customer_code)
                            customer_code = ''

                        deadline = get_lot_date(line_part[12])

                        default_code = line_part[4]
                        product_ids = product_pool.search(cr, uid, [
                            ('default_code', '=', default_code[:11]),
                            ], context=context)
                        if product_ids:
                            product_id = product_ids[0]
                        else:
                            _logger.error('Not found: %s' % default_code)
                            product_id = False
                        line_data = {
                            'logistic_id': logistic_id,
                            'pallet_id': default_pallet_id,  # one2many
                            'pallet': default_pallet,  # code
                            'product_id': product_id,
                            'mapping_id': mapping_id,  # Mapping reference

                            'sequence': sequence,
                            'name': default_code,
                            'customer_code': customer_code,

                            'variable_weight': line_part[5],
                            'lot': line_part[6],
                            'confirmed_qty': get_float(line_part[7]),
                            'net_qty': get_float(line_part[8]),
                            'lord_qty': lord_qty,
                            'parcel': get_int(line_part[10]),
                            'piece': get_int(line_part[11]),  # XXX not used!
                            'deadline': deadline,
                            'origin_country': line_part[13],
                            'provenance_country': line_part[14],

                            # Header data:
                            'invoice': data['invoice'],
                            'invoice_date': invoice_date,

                            # Not mandatory:
                            'dvce': '',
                            'dvce_date': False,
                            'animo': '',
                            'sif': '',
                            'duty': '',
                            'mrn': '',
                            }
                        line_pool.create(cr, uid, line_data, context=context)
                except:
                    raise osv.except_osv(
                        _('Errore'),
                        _('Errore importando il file: %s\n\n%s') % (
                            filename,
                            sys.exc_info(),
                        )
                    )
            break  # only path folder

        # ---------------------------------------------------------------------
        # History used files:
        # ---------------------------------------------------------------------
        for filename, history in history_list:
            shutil.move(filename, history)
            log_data(log_f, 'File history: %s > %s' % (filename, history))
        log_f.close()
        return True

    # SOAP:
    def get_token(self, cr, uid, ids, context=None):
        """ Try to use previous token or get new one for period
        """
        return self._soap_login(cr, uid, ids, context=context)

    def scheduled_load_new_order(self, cr, uid, context=None):
        """ Scheduled action for import all orders
        """
        _logger.info('Scheduled action: import all SOAP order')
        for item_id in self.search(cr, uid, [], context=context):
            self.load_new_order(cr, uid, [item_id], context=context)
        return True

    def load_new_order(self, cr, uid, ids, context=None):
        """ Load order from WSDL Soap Connection
        """
        parameter = self.browse(cr, uid, ids, context=context)[0]
        order_pool = self.pool.get('edi.soap.order')

        flask_host = parameter.flask_host
        flask_port = parameter.flask_port
        if flask_host:
            # Authenticate to get Session ID:
            url = 'http://%s:%s/API/v1.0/micronaet/launcher' % (
                flask_host, flask_port)
            headers = {
                'content-type': 'application/json',
            }
            payload = {
                'jsonrpc': '2.0',
                'params': {
                    'command': 'order',
                    'parameters': {
                        # 'wsdl_root': wsdl_root,
                        # 'namespace': namespace,
                        # 'username': username,
                        # 'timestamp': timestamp,
                        # 'number': number,
                        # 'hash_text': hash_text,
                    },
                }
            }
            response = requests.post(
                url, headers=headers, data=json.dumps(payload))
            try:
                response_json = response.json()
            except:
                raise osv.except_osv(
                    _('Errore di connessione con MSC'),
                    _('Verificare se il portale MCS è operativo o se è ' 
                      'scaduto il codice "secret", richiedere a MSC o Niuma!'),
                )
            if response_json['success']:
                res = response_json.get('reply', {}).get('res')
            else:
                res = {}  # No reply

        else:
            service = self._get_soap_service(cr, uid, ids, context=context)
            res = service.getOngoingPOrders(
                accessToken=self.get_token(cr, uid, ids, context=context))

        self.check_return_status(res, 'Load new order')

        # todo Manage token problem
        for order in res['orders']:
            order_pool.create_new_order(
                cr, uid, ids[0], order, force=False, context=context)
        return True

    _columns = {
        'name': fields.char('Soap Connection', size=64, required=True),
        'token': fields.char(
            'Soap token', size=180,
            help='Token assigned and saved when updated'),

        # ---------------------------------------------------------------------
        # Soap connection:
        # ---------------------------------------------------------------------
        'username': fields.char('Username', size=40, required=True),
        'secret': fields.char('Secret', size=180, required=True),
        'wsdl_root': fields.char(
            'WSDL Root', size=180, required=True,
            help='Example: https://example.com/pep/wsdl'),
        'namespace': fields.char(
            'Namespace', size=40, required=True,
            help='Example: {it.example.soapws.ws}WsPortSoap11'),

        # ---------------------------------------------------------------------
        # Server connection:
        # ---------------------------------------------------------------------
        # Invoice:
        'server_root': fields.char(
            'Invoice Root', size=180, required=True,
            help='Example: ~/account/invoice'),
        'detail_separator': fields.char(
            'Detail separator', size=5,
            required=True, help='Separator used for detail columns'),

        # Order:
        'order_root': fields.char(
            'Order Root', size=180, required=True,
            help='Example: ~/account/order/in'),
        'order_separator': fields.char(
            'Detail separator', size=5,
            required=True, help='Separator used for detail columns'),
        'csv_code': fields.char(
            'Company code', size=5,
            required=True, help='Used for first field in CSV file'),

        # Pallet:
        'uom_code': fields.char(
            'UOM code', size=5,
            help='Used for pallet total calc'),
        'pallet_capability': fields.integer(
            'Pallet capability',
            help='Used for pallet total calc'),
        'pallet_extra': fields.integer(
            'Pallet extra',
            help='Used to print extra label if needed'),
        # Account:
        'server_account_code': fields.char(
            'Account code', size=180,
            required=True,
            help='Account ref. for partners, ex: 02.00001|02.00002'),
        'server_pon_code': fields.char(
            'PON partner code', size=15,
            required=True,
            help='Right part of the order: ORDER-PONCODE >> PONCODE'),

        # Account:
        'flask_host': fields.char('Host agente', size=80,
            help='Indirizzo server dove è installato l\'agente del gestionale'
            ),
        'flask_port': fields.integer(
            'Porta agente', default=5000,
            help='Porta di connessione agente di passaggio dati'),
        }

    _defaults = {
        'detail_separator': lambda *x: '|*|',
        'order_separator': lambda *x: '|',
        'uom_code': lambda *x: 'KG',
        'pallet_capability': lambda *x: 550,
        }


class EdiSoapMapping(orm.Model):
    """ Soap Parameter for connection
    """
    _name = 'edi.soap.mapping'
    _description = 'EDI Soap Mapping'
    _rec_name = 'name'
    _order = 'connection_id,default_code'

    def onchange_product_id(self, cr, uid, ids, product_id, context=None):
        """ Onchange product check chunk data:
        """
        if not product_id:
            return False  # {'value': {'chunk': False}}
        # Update chunk if not present:
        product_pool = self.pool.get('product.product')
        product = product_pool.browse(cr, uid, product_id, context=context)
        if product.chunk:
            chunk = product.chunk
        else:
            chunk = product_pool.get_chunk(product)
            product_pool.write(cr, uid, [product_id], {
                'chunk': chunk,
                }, context=context)
        return False

    def onchange_default_code(self, cr, uid, ids, default_code, context=None):
        """ Update product from default_code
        """
        res = {}
        product_pool = self.pool.get('product.product')
        product_ids = product_pool.search(cr, uid, [
            ('default_code', 'ilike', default_code),
            ], context=context)
        if not product_ids:
            return res

        if len(product_ids) == 1:
            res['value'] = {
                'product_id': product_ids[0],
                }
            res['domain'] = {
                'product_id': [],
                }
            # Call for update chunk:
            self.onchange_product_id(
                cr, uid, ids, product_ids[0], context=context)
        else:
            res['domain'] = {
                'product_id': [('id', 'in', product_ids)],
                }
        return res

    _columns = {
        'name': fields.char('Customer code', size=64, required=True),
        'variable_weight': fields.boolean('Variable weight'),
        'default_code': fields.char('Company code', size=64),
        'product_id': fields.many2one(
            'product.product', 'Product', required=True),

        'connection_id': fields.many2one(
            'edi.soap.connection', 'Connection', required=True),
        'duty_code': fields.related(
            'product_id', 'duty_code', type='char', string='Duty code'),
        'chunk': fields.related(
            'product_id', 'chunk', type='integer', string='Chunk per pack'),
        }


class ProductProduct(orm.Model):
    """ Model name: ProductProduct
    """

    _inherit = 'product.product'

    # -------------------------------------------------------------------------
    # Utility:
    # -------------------------------------------------------------------------
    def get_chunk(self, product):
        """ Extract chunk from name
        """
        try:
            return re.findall(r'\d*[xX]', product.name)[0][:-1] or 1
        except:
            return 1

    _columns = {
        'duty_code': fields.char('Duty code', size=20),
        'chunk': fields.char('Chunk per pack', size=20),
    }


class EdiSoapOrder(orm.Model):
    """ Soap Soap Order
    """
    _name = 'edi.soap.order'
    _description = 'EDI Soap Order'
    _rec_name = 'name'
    _order = 'delivery_date,name'

    # -------------------------------------------------------------------------
    # Utility:
    # -------------------------------------------------------------------------
    def _safe_get(self, item, field, default=False):
        """ Safe eval the field data
        """
        try:
            return eval('item[field] or default')
        except:
            _logger.error('Cannot eval: field %s' % field)
            return default

    # -------------------------------------------------------------------------
    #                                    BUTTON:
    # -------------------------------------------------------------------------
    def print_all_label(self, cr, uid, ids, context=None):
        """ Print all label
        """
        line_pool = self.pool.get('edi.soap.logistic.pallet')
        if context is None:
            context = {}
        context['order_id'] = ids[0]
        return line_pool.print_label(cr, uid, False, context=context)

    def generate_pallet_list(self, cr, uid, ids, context=None):
        """ Generate list of pallet from order weight
        """
        extra_pallet = 0  # TODO Param for print more labels

        # Pool used:
        pallet_pool = self.pool.get('edi.soap.logistic.pallet')
        current_proxy = self.browse(cr, uid, ids, context=context)[0]
        pallet = current_proxy.total_pallet
        current_pallet = len(current_proxy.pallet_ids)
        if current_pallet and pallet == current_pallet:
            raise osv.except_osv(
                _('Warning'),
                _('The %s pallet is yet created!') % pallet,
                )
        elif pallet < current_pallet and current_pallet:
            raise osv.except_osv(
                _('Warning'),
                _('Cannot remove, dont\'t use the wrong created!'),
                )
        try:
            last = max([item.name for item in current_proxy.pallet_ids])
        except:
            last = 0

        # ---------------------------------------------------------------------
        # If is only one assign to all
        # ---------------------------------------------------------------------
        # Create remain pallet:
        remain = pallet - current_pallet
        pallet_id = 0
        pallet_ids = []
        for i in range(0, remain):
            pallet_ids.append(pallet_pool.create(cr, uid, {
                'name': last + i + 1,
                'sscc': pallet_pool._generate_sscc_code(
                    cr, uid, context=context),
                'order_id': ids[0]
                }, context=context))
        return True

    def create_new_order(
            self, cr, uid, connection_id, order, force=False, context=None):
        """ Create new order from order object
        """
        # Pool used:
        connection_pool = self.pool.get('edi.soap.connection')
        mapping_pool = self.pool.get('edi.soap.mapping')
        line_pool = self.pool.get('edi.soap.order.line')
        pallet_pool = self.pool.get('edi.soap.logistic.pallet')

        # ---------------------------------------------------------------------
        # Parameter:
        # ---------------------------------------------------------------------
        connection = connection_pool.browse(
            cr, uid, connection_id, context=context)
        pallet_weight = connection.pallet_capability
        pallet_uom = connection.uom_code
        pallet_extra = connection.pallet_extra

        entity_name = self._safe_get(order, 'entityName')
        po_number = self._safe_get(order, 'poNumber')
        if entity_name.upper().startswith('WH'):
            mode = 'WH'
        else:
            mode = 'SH'

        order_ids = self.search(cr, uid, [
            ('name', '=', po_number),
            ], context=context)

        pallet_ids = destination_id = False
        if order_ids:
            if force:
                # Save previous pallet list:
                current_order = self.browse(
                    cr, uid, order_ids, context=context)[0]
                pallet_ids = [pallet.id for pallet in current_order.pallet_ids]
                destination_id = current_order.destination_id.id

                # Delete order before (so recreate)
                _logger.warning('Order deleted for recreation: %s' % (
                    po_number,
                    ))
                self.unlink(cr, uid, order_ids, context=context)
            else:
                # Update only state:
                _logger.warning('%s yet present (update status)' % po_number)
                return self.write(cr, uid, order_ids, {
                    'status': self._safe_get(order, 'status'),
                    }, context=context)

        header = {
            'connection_id': connection_id,
            'name': self._safe_get(
                order, 'poNumber'),  # '2110479-FB04023'
            'delivery_date': self._safe_get(
                order, 'deliveryDate'),  # None,
            'entity_name': entity_name,  # 'MV Poesia',
            'mode': mode,
            'delivery_port_nam': self._safe_get(
                order, 'deliveryPortName'),  # u'Wa\xfcnde',
            'status': self._safe_get(
                order, 'status'),  # 'Emitted',
            'po_create_date': self._safe_get(
                order, 'createDate'),  # None,
            'currency': self._safe_get(
                order, 'currency'),  # 'EUR',
            'fullname': self._safe_get(
                order, 'fullName'),  # 'xxx yyy',
            'document_value': self._safe_get(
                order, 'documentValue'),  #: Decimal('234.20000')
            'buyer_group': self._safe_get(
                order, 'buyerGroup'),  #: 'Buyers',
            'delivery_terms': self._safe_get(
                order, 'deliveryTerms'),  #: None,
            'info_container': self._safe_get(
                order, 'infoContainer'),  #: None,
            'document_comment': self._safe_get(
                order, 'documentComment'),  #: None,
            'invoice_holder': self._safe_get(
                order, 'invoiceHolder'),  #: 'Cruises',
            'invoice_address': self._safe_get(
                order, 'invoiceAddress'),  #: u'Eug\xe8ne 40 120 GENEVA (CH)'
            'invoice_vatcode': self._safe_get(
                order, 'invoiceVatcode'),  #: 'CHE-123.808.357 TVA',
            'delivery_at': self._safe_get(
                order, 'deliveryAt'),  # 'Comando nave',
            'delivery_address': self._safe_get(
                order, 'deliveryAddress'),  # 'Via X 91 Genova 16162 Italy',
            'delivery_ship': self._safe_get(
                order, 'deliveryShip'),  #: None,
            'logistic': self._safe_get(
                order, 'logistic'),  # False,
            'requires_logistic': self._safe_get(
                order, 'requiresLogistic'),  # None,
            }

        # Create order not present:
        order_id = self.create(cr, uid, header, context=context)
        _logger.info('New Order %s' % po_number)

        # todo load also file for ERP Management
        weight = {}
        for line in order['orderLines']:
            # -----------------------------------------------------------------
            # Detail data:
            # -----------------------------------------------------------------
            uom = self._safe_get(line, 'itemReceivingUnit')  # 'KG'
            confirmed_qty = float(self._safe_get(
                    line, 'quantityConfirmed', 0.0))  # Decimal('230.00000'),
            name = self._safe_get(line, 'itemCode')  # 'F0000801'

            # Update total for pallet label calc:
            if uom in weight:
                weight[uom] += confirmed_qty
            else:
                weight[uom] = confirmed_qty

            # Search product mapping:
            mapping_ids = mapping_pool.search(cr, uid, [
                ('name', '=', name),
                ], context=context)
            if mapping_ids:
                mapping_proxy = mapping_pool.browse(
                    cr, uid, mapping_ids, context=context)[0]
                product_id = mapping_proxy.product_id.id
            else:
                product_id = False

            line = {
                'order_id': order_id,
                'name': name,
                'product_id': product_id,
                'description': self._safe_get(
                    line, 'itemDescription'),  # 'CORN KERNEL WHOLE FRZ',
                'item_price': self._safe_get(
                    line, 'itemPrice'),  # Decimal('0.93000'),
                'uom': uom,
                'ordered_qty': float(self._safe_get(
                    line, 'quantityOrdered', 0.0)),  # Decimal('230.00000'),
                'confirmed_qty': confirmed_qty,
                'logistic_qty': float(self._safe_get(
                    line, 'quantityLogistic', 0.0)),  # None,

                'cd_gtin': self._safe_get(
                    line, 'cdGtin'),  # None,
                'cd_voce_doganale': self._safe_get(
                    line, 'cdVoceDoganale'),  # None,
                'nr_pz_conf': self._safe_get(
                    line, 'nrPzConf'),  # None,
                'cd_paese_origine': self._safe_get(
                    line, 'cdPaeseOrigine'),  # None,
                'cd_paese_provenienza': self._safe_get(
                    line, 'cdPaeseProvenienza'),  # None,
                'fl_dogana': self._safe_get(
                    line, 'flDogana'),  # None
                }
            line_pool.create(cr, uid, line, context=context)

        weight = weight.get(pallet_uom, 0.0)
        if weight:
            self.write(cr, uid, [order_id], {
                'total_weight': weight,
                'total_pallet':
                    pallet_extra + (weight / pallet_weight) +
                    1 if weight % pallet_weight > 0 else 0
                }, context=context)

        if destination_id:
            self.write(cr, uid, [order_id], {
                'destination_id': destination_id,
                }, context=context)

        # Pallet relinked to new order:
        if pallet_ids:
            _logger.warning('Pallet relinked to logistic order # %s' % len(
                pallet_ids))
            pallet_pool.write(cr, uid, pallet_ids, {
                'order_id': order_id,
                }, context=context)

        # todo generate pallet list if empty?
        return order_id

    def extract_order_csv_file(self, cr, uid, ids, context=None):
        """ Generate all pallet label from here
        """
        # ---------------------------------------------------------------------
        # Utility:
        # ---------------------------------------------------------------------
        def clean_text(
                text, length, uppercase=False, error=None, truncate=False):
            """ Return clean text with limit cut
                Log in error if over length
            """
            if error is None:
                error = []

            text = (text or '').strip()
            if len(text) > length:
                if truncate:
                    text = text[:length]
                else:
                    error.append('Text: %s > %s' % (text, length))
            if uppercase:
                return text.upper()
            return text

        def clean_date(
                italian_date, separator='', out_format='iso', error=None):
            """ Return clean text with limit cut
                Log in error if over length
            """
            if error is None:
                error = []
            italian_date = italian_date.split(' ')[0]  # remove hour block
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
            else: # incorrect format:
                return italian_date  # nothing todo

        def clean_float(value, length, decimal=3, separator='.', error=None):
            """ Clean float and return float format
            """
            if error is None:
                error = []
            try:
                if type(value) == str:
                    value = value.replace(',', '.')
                    float_value = float(value.strip())
                else: # float
                    float_value = value
            except:
                error.append('Not a float: %s' % value)
                float_value = 0.0

            mask = '%%%s.%sf' % (length, decimal)
            res = mask % float_value
            res = res.replace('.', separator)
            return res

        # ---------------------------------------------------------------------
        #                           Export procedure:
        # ---------------------------------------------------------------------
        order = self.browse(cr, uid, ids, context=context)[0]

        # Parameters:
        mask = '%3s|%-8s|%-8s|%-25s|%-16s|' + \
            '%-16s|%-60s|%-2s|%-15s|%-15s|%-15s|%-8s|%-8s|%-40s\r\n'

        connection = order.connection_id
        separator = connection.order_separator
        csv_code = connection.csv_code
        path = os.path.expanduser(connection.order_root)
        filename = '%s.csv' % order.name
        fullname = os.path.join(path, filename)

        # Update separator
        if separator != '|':
            mask = mask.replace('|', separator)

        # Header data:
        date = order.po_create_date.replace('-', '')
        deadline = order.delivery_date.replace('-', '')
        today = datetime.now().strftime(
            DEFAULT_SERVER_DATE_FORMAT).replace('-', '')
        destination_code = order.destination_id.sql_destination_code or ''

        entity_name = order.entity_name or ''
        if entity_name.upper().startswith('WH'):
            entity_name = order.document_comment

        file_csv = open(fullname, 'w')
        error = []
        for line in order.line_ids:
            # Readability:
            product = line.product_id
            subtotal = line.confirmed_qty * line.item_price

            row = mask % (
                csv_code,  # 3 Company
                deadline,
                clean_text(
                    destination_code, 8, error=error),
                clean_text(
                    order.name, 25, error=error),
                clean_text(
                    line.name, 16, uppercase=True, error=error),
                clean_text(
                    product.default_code, 16, uppercase=True, error=error),
                clean_text(
                    product.name, 60, error=error, truncate=True),
                clean_text(
                    line.uom, 2, uppercase=True, error=error),
                clean_float(  # quantity
                    line.confirmed_qty, 15, 2, error=error),
                clean_float(  # price
                    line.item_price, 15, 3, error=error),
                clean_float(  # subtotal
                    subtotal, 15, 3, error=error),
                date,
                today,
                clean_text(
                    entity_name, 40, error=error),
                )
            file_csv.write(row)
        file_csv.close()

        # Save file name (hide button):
        self.write(cr, uid, [order.id], {
            'filename': filename,
            }, context=context)
        _logger.warning('Files %s exported!' % fullname)
        return True

    def reload_this_order(self, cr, uid, ids, context=None):
        """ Reload this order
        """
        connection_pool = self.pool.get('edi.soap.connection')
        current_proxy = self.browse(cr, uid, ids, context=context)[0]
        connection_id = current_proxy.connection_id.id

        service = connection_pool._get_soap_service(
            cr, uid, [connection_id], context=context)

        res = service.getPOrder(
            accessToken=connection_pool.get_token(
                cr, uid, [connection_id], context=context),
            poNumber=current_proxy.name,
            )
        connection_pool.check_return_status(
            res, 'Reload order: %s' % current_proxy.name)
        order = res['pOrder']

        # Force recreation of order:
        order_id = self.create_new_order(
            cr, uid, connection_id, order, force=True,
            context=context)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reload order'),
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_id': order_id,
            'res_model': 'edi.soap.order',
            'view_id': False,
            'views': [(False, 'form'), (False, 'tree')],
            'domain': [],
            'context': context,
            'target': 'current',  # 'new'
            'nodestroy': False,
            }

    def _get_check_pre_export(self, cr, uid, ids, fields, args, context=None):
        """ Fields function for calculate export OK
        """
        res = {}
        for order in self.browse(cr, uid, ids, context=context):
            res[order.id] = True
            for line in order.line_ids:
                if not (line.product_id and line.duty_code and line.chunk):
                    res[order.id] = False
                    break
        return res

    _columns = {
        'name': fields.char(
            'PO Number', size=40, required=True),
        'connection_id': fields.many2one(
            'edi.soap.connection', 'Connection', required=True),
        'destination_id': fields.many2one(
            'res.partner', 'Destination',
            # domain='[("sql_destination_code", "!=", False)]'
            ),
        'mode': fields.selection([
            ('WH', 'Warehouse'),
            ('SH', 'Ship'),
            ], 'Mode'),

        'company_order': fields.char('Company order', size=20),
        'delivery_date': fields.date('Delivery date'),  # required=True
        'po_create_date': fields.date('PO Create date'),  # required=True
        'entity_name': fields.char('Entity name', size=40),
        'delivery_port_nam': fields.char('Delivery Port Nam', size=40),
        'status': fields.char('Status', size=40),
        'currency': fields.char('currency', size=10),
        'fullname': fields.char('Full name', size=40),
        'buyer_group': fields.char('Buyer Group', size=30),

        'document_value': fields.float('Document value', digits=(16, 3)),
        'delivery_terms': fields.char('Delivery Terms', size=30),
        'info_container': fields.char('Info container', size=40),
        'document_comment': fields.char('Document Comment', size=30),

        'invoice_holder': fields.char('Invoice Holder', size=40),
        'invoice_address': fields.char('Invoice Address', size=60),
        'invoice_vatcode': fields.char('Invoice VAT code', size=40),
        'delivery_at': fields.char('Delivery at', size=40),
        'delivery_address': fields.char('Delivery Address', size=40),

        'delivery_ship': fields.char('Delivery ship', size=50),
        'logistic': fields.boolean('Invoice VAT code'),
        'requires_logistic': fields.char('Requires logistic', size=50),

        'total_weight': fields.integer('Total weight'),
        'total_pallet': fields.integer('Total pallet'),
        'note': fields.text('Note'),

        'filename': fields.char('Filename CSV', size=40),
        'check_pre_export': fields.function(
            _get_check_pre_export, method=True,
            type='boolean', string='Check pre export',
            store=False),

        }


class EdiSoapOrderLine(orm.Model):
    """ Soap order line
    """
    _name = 'edi.soap.order.line'
    _description = 'EDI Soap Order line'
    _rec_name = 'name'
    _order = 'name'

    def order_line_detail(self, cr, uid, ids, context=None):
        """ Open detail line
        """
        model_pool = self.pool.get('ir.model.data')
        view_id = model_pool.get_object_reference(
            cr, uid,
            'account_trip_edi_soap', 'view_edi_soap_order_line_form')[1]

        return {
            'type': 'ir.actions.act_window',
            'name': _('Line detail'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': ids[0],
            'res_model': 'edi.soap.order.line',
            'view_id': view_id,
            'views': [(view_id, 'form')],
            'domain': [],
            'context': context,
            'target': 'new',
            'nodestroy': False,
            }

    def extract_chunk_from_name(self, cr, uid, product_id, context=None):
        """ Extract left part of X if decimal
        """
        product_pool = self.pool.get('product.product')
        product = product_pool.browse(cr, uid, product_id, context=context)
        if not product.chunk:
            chunk = product_pool.get_chunk(product)
            product_pool.write(cr, uid, [product_id], {
                'chunk': chunk,
                }, context=context)
        return

    # -------------------------------------------------------------------------
    # Oncange:
    # -------------------------------------------------------------------------
    def onchange_company_product_id(
            self, cr, uid, ids, order_id, name, product_id, context=None):
        """ Update mapped product
        """
        res = {}
        if not order_id or not product_id or not name:
            return res

        order_pool = self.pool.get('edi.soap.order')
        mapping_pool = self.pool.get('edi.soap.mapping')

        order_proxy = order_pool.browse(cr, uid, order_id, context=context)
        connection_id = order_proxy.connection_id.id

        # Chunk setup:
        self.extract_chunk_from_name(cr, uid, product_id, context=context)

        # ---------------------------------------------------------------------
        # Search mapping
        # ---------------------------------------------------------------------
        mapping_ids = mapping_pool.search(cr, uid, [
            ('connection_id', '=', connection_id),
            ('name', '=', name),
            ], context=context)

        if len(mapping_ids) > 1:
            _logger.error('More than one mapping: %s' % name)

        # ---------------------------------------------------------------------
        # Mapping operation:
        # ---------------------------------------------------------------------
        data = {
            'connection_id': connection_id,
            'name': name,
            'product_id': product_id,
            }
        if mapping_ids:
            mapping_pool.write(cr, uid, mapping_ids, data, context=context)
        else:
            mapping_pool.create(cr, uid, data, context=context)
        return res

    _columns = {
        'name': fields.char('Code', size=40, required=True),
        'order_id': fields.many2one(
            'edi.soap.order', 'Order', ondelete='cascade'),
        'product_id': fields.many2one('product.product', 'Company product'),

        'duty_code': fields.related(
            'product_id', 'duty_code', type='char', string='Duty code'),
        'chunk': fields.related(
            'product_id', 'chunk', type='integer', string='Chunk per pack'),

        'description': fields.char('Description', size=40), # itemDescription
        'uom': fields.char('UOM', size=10),
        'ordered_qty': fields.float('Ordered', digits=(16, 3)),
        'confirmed_qty': fields.float('Confirmed', digits=(16, 3)),
        'logistic_qty': fields.float('Logistic', digits=(16, 3)),

        'item_price': fields.float('Price', digits=(16, 5)),

        'cd_gtin': fields.char('GTIN', size=40), # cdGtin
        'cd_voce_doganale': fields.char('Duty code', size=40), # cdVoceDoganale
        'nr_pz_conf': fields.char('Q. x pack', size=5),  # nrPxConf
        'cd_paese_origine': fields.char('Origin', size=40),  # cdPaeseOrigine
        'cd_paese_provenienza': fields.char('Derived', size=40),  # cdPaeseProvenienza
        'fl_dogana': fields.char('Duty', size=20),  # Duty code
        }


# -----------------------------------------------------------------------------
#                              LOGISTIC ORDER:
# -----------------------------------------------------------------------------
class EdiSoapLogistic(orm.Model):
    """ Soap logistic order
    """
    _name = 'edi.soap.logistic'
    _description = 'EDI Soap Logistic'
    _rec_name = 'name'
    _order = 'name desc'

    def send_logistic_not_send(self, cr, uid, ids, context=None):
        """ Not sent button
        """
        return self.write(cr, uid, ids, {
            'soap_not_sent': True,
            }, context=context)

    def open_logistic_lines(self, cr, uid, ids, context=None):
        """ Logistic line details
        """
        model_pool = self.pool.get('ir.model.data')
        view_id = model_pool.get_object_reference(
            cr, uid,
            'account_trip_edi_soap',
            'view_edi_soap_logistic_line_tree')[1]

        line_pool = self.pool.get('edi.soap.logistic.line')
        line_ids = line_pool.search(cr, uid, [
            ('logistic_id', '=', ids[0]),
            ], context=context)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Detail lines'),
            'view_type': 'form',
            'view_mode': 'tree',
            # 'res_id': 1,
            'res_model': 'edi.soap.logistic.line',
            'view_id': view_id,  # False
            'views': [(False, 'tree'), ],
            'domain': [('id', 'in', line_ids)],
            'context': context,
            'target': 'current',
            'nodestroy': False,
            }

    def send_logistic_2_soap(self, cr, uid, ids, context=None):
        """ Send to SOAP platform logistic order
        """
        connection_pool = self.pool.get('edi.soap.connection')
        mapping_pool = self.pool.get('edi.soap.mapping')

        # ---------------------------------------------------------------------
        # Send logistic order:
        # ---------------------------------------------------------------------
        logistic = self.browse(cr, uid, ids, context=context)[0]
        parameter = logistic.connection_id
        flask_host = parameter.flask_host
        flask_port = parameter.flask_port

        # Header:
        try:
            first_line = logistic.line_ids[0]
        except:
            raise osv.except_osv(
                _('Error'),
                _('No lines!'),
                )

        plotToCreate = {
            'ponumber': logistic.order_id.name or logistic.customer_order,
            'dfDocIngresso': first_line.invoice,
            'dtEmissione': first_line.invoice_date,
            'dtIngresso': logistic.delivery_date,

            'pLotLinesData': [],
            }

        # Lines:
        plot_lines_data = plotToCreate['pLotLinesData']
        for line in logistic.line_ids:
            product = line.product_id
            customer_code = line.customer_code
            if not customer_code:
                mapping_ids = mapping_pool.search(cr, uid, [
                    ('product_id', '=', product.id),
                    ], context=context)
                if mapping_ids:
                    mapping = mapping_pool.browse(
                        cr, uid, mapping_ids, context=context)[0]
                    customer_code = mapping.name
                else:
                    _logger.error(
                        'No mapping code for %s' % product.default_code)
            # -----------------------------------------------------------------
            # XXX No more used chunk:
            # chunk = product.chunk
            # if not chunk:
            #    chunk = product_pool.get_chunk(product)
            #    # not saved only for this send!
            # -----------------------------------------------------------------
            parcel = line.parcel or 1
            chunk = int(round(line.net_qty / parcel, 0))
            if line.variable_weight:
                variable_weight = '1'
                chunk = 1
            else:
                variable_weight = '0'

            plot_lines_data.append({
                'cdArticolo': customer_code or '',  # MSC code
                'cdVoceDoganale': product.duty_code or '',
                'cdCollo': line.pallet_id.sscc or '',  # SSCC
                'cdGtin': product.default_code,  # Company code or EAN
                'flPesoVariabile': variable_weight,  # 1 or 0
                'nrLotto': line.lot or '',
                'qtPrevista': line.confirmed_qty,  # Company confirmed

                'cdMisura': '',  # TODO
                'nrRiga': line.sequence,  # 1 x or 10 x?

                'nrNetto': line.net_qty,
                'nrLordo': line.lord_qty,
                'nrColli': parcel,
                'nrPzConf': chunk,
                'dtScadenza': line.deadline,  # Lot?
                'cdPaeseOrigine': line.origin_country or '',
                'cdPaeseProvenienza': line.provenance_country or '',

                'dfDvce': line.dvce or '',
                'dtDvce': line.dvce_date or '',
                'dfAnimo': line.animo or '',
                'dfSif': line.sif or '',
                'flDogana': line.duty or '',  # 0 or 1 (duty document needed)
                'dfMrn': line.mrn or '',

                'dfFattura': line.invoice or '',  # Number
                'dtFattura': line.invoice_date or '',  # Date
                })

        # ---------------------------------------------------------------------
        # Send to the SOAP Portal
        # ---------------------------------------------------------------------
        # Flask:
        # ---------------------------------------------------------------------
        pdb.set_trace()  # todo debug from here!
        if flask_host:
            # Authenticate to get Session ID:
            url = 'http://%s:%s/API/v1.0/micronaet/launcher' % (
                flask_host, flask_port)
            headers = {
                'content-type': 'application/json',
            }
            payload = {
                'jsonrpc': '2.0',
                'params': {
                    'command': 'invoice',
                    'parameters': {
                        # Invoice to be sent:
                        'plotToCreate': plotToCreate,
                    },
                }
            }
            response = requests.post(
                url, headers=headers, data=json.dumps(payload))
            response_json = response.json()
            if response_json['success']:
                res = response_json.get('reply', {}).get('res')
            else:
                res = {}  # No reply

        # ---------------------------------------------------------------------
        # SOAP portal:
        # ---------------------------------------------------------------------
        else:
            service = connection_pool._get_soap_service(
                cr, uid, [logistic.connection_id.id], context=context)
            token = connection_pool.get_token(
                cr, uid, [logistic.connection_id.id], context=context)
            res = service.createNewPLot(
                accessToken=token, plotToCreate=plotToCreate)

        # XXX ? res['ricevuta']  # file (base64) filename

        # ---------------------------------------------------------------------
        # Check response:
        # ---------------------------------------------------------------------
        if not res:
            _logger.error('Errore:\n%s' % plotToCreate)
            raise osv.except_osv(
                _('Errore SOAP'),
                _('Nessuna risposta dal portale del cliente!'),
                )

        try:
            message = res['operationOutcome']['message']
        except:
            message = 'Cannot get message'

        try:
            error_list = ','.join(res['operationOutcome']['errorsList'])
        except:
            error_list = ''

        try:
            message_logistic = res['logistic']
        except:
            message_logistic = 'No logistic response'

        if res['operationOutcome']['statusCode']:
            raise osv.except_osv(
                _('SOAP Error'),
                _('Message: %s [%s]') % (
                    message,
                    error_list,
                    # {%s}plotToCreate,
                    ))
        else:
            self.write(cr, uid, ids, {
                'soap_sent': True,
                'soap_message': message,
                'soap_detail': res['logistic'],
                }, context=context)
        return True

    def setup_pallet_id(self, cr, uid, ids, context=None):
        """ Setup selected pallet in all lines
        """
        line_pool = self.pool.get('edi.soap.logistic.line')
        current_proxy = self.browse(cr, uid, ids, context=context)[0]
        select_pallet_id = current_proxy.select_pallet_id.id
        if not select_pallet_id:
            raise osv.except_osv(
                _('Errore'),
                _('Select before the pallet to setup, and click the button!'),
                )

        line_ids = line_pool.search(cr, uid, [
            ('logistic_id', '=', ids[0]),
            ], context=context)
        return line_pool.write(cr, uid, line_ids, {
            'pallet_id': select_pallet_id,
            }, context=context)

    _columns = {
        'name': fields.char('Invoice reference', size=40, required=True),
        'soap_sent': fields.boolean('MSC sent'),
        'soap_not_sent': fields.boolean('MSC not sent (old order)'),
        'soap_message': fields.char('Returned message', size=100),
        'soap_detail': fields.text('Returned detail'),
        'customer_order': fields.char('Cust. Number', size=40),
        'delivery_date': fields.date('Delivery date'),
        'connection_id': fields.many2one(
            'edi.soap.connection', 'Connection', required=True),
        'order_id': fields.many2one(
            'edi.soap.order', 'Order', help='Generator order linked'),
        'pallet': fields.integer('Pallet used'),
        'select_pallet_id': fields.many2one(
            'edi.soap.logistic.pallet', 'Select pallet'),
        'text': fields.text('File text', help='Account file as original'),
        'mode': fields.related(
            'order_id', 'mode',
            type='selection', string='Mode'),
            # ('WH', 'Warehouse'),
            # ('SH', 'Ship'),
            # ], 'Mode'),
        'state': fields.selection([
            ('draft', 'Draft'), # To be worked
            ('working', 'Working'), # Start assign pallet
            ('confirmed', 'Confirmed'), # Confirmed and sent
            ('done', 'Done'), # Received and approved
            ], 'State'),
        }

    _defaults = {
        'pallet': lambda *x: 1,
        'state': lambda *x: 'draft',
        }


class EdiSoapLogisticPallet(orm.Model):
    """ Soap logistic order
    """
    _name = 'edi.soap.logistic.pallet'
    _description = 'EDI Soap Logistic Pallet'
    _rec_name = 'name'
    _order = 'name'

    # -------------------------------------------------------------------------
    # Button:
    # -------------------------------------------------------------------------
    def all_this_pallet(self, cr, uid, ids, context=None):
        """ Set this pallet to all the line
        """
        pallet = self.browse(cr, uid, ids, context=context)[0]

        line_pool = self.pool.get('edi.soap.logistic.line')
        line_ids = line_pool.search(cr, uid, [
            ('logistic_id', '=', pallet.logistic_id.id),
            ], context=context)

        line_pool.write(cr, uid, line_ids, {
            'pallet': pallet.name,
            'pallet_id': pallet.id,
            }, context=context)
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
            }

    def _get_pallet_totals(self, cr, uid, ids, fields, args, context=None):
        """ Fields function for calculate
        """
        res = {}

        for pallet in self.browse(cr, uid, ids, context=context):
            # Search line linked:
            line_pool = self.pool.get('edi.soap.logistic.line')
            line_ids = line_pool.search(cr, uid, [
                ('logistic_id', '=', pallet.logistic_id.id),
                ('pallet_id', '=', pallet.id)
                ], context=context)
            lines = line_pool.browse(cr, uid, line_ids, context=context)

            # XXX check chunk?
            res[pallet.id] = {
                'total_line': len(line_ids),
                # 'total_weight': sum([
                #    (float(line.product_id.chunk or 1) * line.lord_qty) \
                #        for line in lines])
                'total_weight': sum([line.lord_qty for line in lines])
                }

        return res

    _columns = {
        'name': fields.integer('#', required=True),
        'sscc': fields.char('SSCC Code', size=40, required=True),
        'logistic_id': fields.many2one('edi.soap.logistic', 'Logistic order'),
        'order_id': fields.many2one('edi.soap.order', 'Sale order'),
        'total_line': fields.function(
            _get_pallet_totals, method=True,
            type='integer', string='Total line', multi=True),
        'total_weight': fields.function(
            _get_pallet_totals, method=True,
            type='float', digits=(16, 3), string='Total line', multi=True),
        }


class EdiSoapLogisticLine(orm.Model):
    """ Soap logistic order
    """
    _name = 'edi.soap.logistic.line'
    _description = 'EDI Soap Logistic Line'
    _rec_name = 'name'
    _order = 'sequence, name, splitted_from_id desc'

    # -------------------------------------------------------------------------
    # Onchange:
    # -------------------------------------------------------------------------
    def onchange_pallet_code(
            self, cr, uid, ids, logistic_id, pallet_code,
            field_name='pallet_id', context=None):
        """ Save correct element
            Called also from wizard new_pallet reference
        """
        logistic_pool = self.pool.get('edi.soap.logistic')
        logistic = logistic_pool.browse(cr, uid, logistic_id, context=context)
        pallet_id = False

        for pallet in logistic.pallet_ids:
            if pallet_code == pallet.name:
                pallet_id = pallet.id
                break
        if not pallet_id:
            raise osv.except_osv(
                _('Pallet error'),
                _('Pallet not found use code present in the list'),
                )
        return {'value': {
            field_name: pallet_id,
            }}

    def line_detail(self, cr, uid, ids, context=None):
        """ Open detail line
        """
        model_pool = self.pool.get('ir.model.data')
        view_id = model_pool.get_object_reference(
            cr, uid,
            'account_trip_edi_soap', 'view_edi_soap_logistic_line_form')[1]

        return {
            'type': 'ir.actions.act_window',
            'name': _('Line detail'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': ids[0],
            'res_model': 'edi.soap.logistic.line',
            'view_id': view_id,
            'views': [(view_id, 'form')],
            'domain': [],
            'context': context,
            'target': 'new',
            'nodestroy': False,
            }

    _columns = {
        # ---------------------------------------------------------------------
        # XXX Remember duplication wizard when add fields!!!
        'logistic_id': fields.many2one(
            'edi.soap.logistic', 'Logistic order', ondelete='cascade'),
        'pallet': fields.integer('Pallet'),
        'pallet_id': fields.many2one(
            'edi.soap.logistic.pallet', 'Pallet', ondelete='set null'),
        'order_id': fields.related(
            'logistic_id', 'order_id',
            type='many2one', relation='edi.soap.order',
            string='Order', ondelete='set null'),
        'mapping_id': fields.many2one(
            'edi.soap.mapping', 'Mapping', ondelete='set null'),
        'product_id': fields.many2one(
            'product.product', 'Product', ondelete='set null'),

        # XXX Use mapping - product duty code (not product)
        'duty_code': fields.related(
            'mapping_id', 'duty_code', type='char', string='Duty code'),
        'variable_weight': fields.related(
            'mapping_id', 'variable_weight', type='boolean',
            string='Variable weight'),

        'chunk': fields.related(
            'product_id', 'chunk', type='integer', string='Chunk per pack'),

        'sequence': fields.integer('Seq.'),
        'name': fields.char('Company code', size=40, required=True),
        'customer_code': fields.char('Customer code', size=20),
        'lot': fields.char('Lot', size=6),
        'confirmed_qty': fields.float('Confirmed qty', digits=(16, 2)),
        'net_qty': fields.float('Net qty', digits=(16, 2)),
        'lord_qty': fields.float('Lord qty', digits=(16, 2)),
        'parcel': fields.integer('Parcel'),
        'piece': fields.integer('Piece'),
        'deadline': fields.date('Deadline'),
        'origin_country': fields.char('Origin country', size=4),
        'provenance_country': fields.char('Provenance country', size=4),
        'dvce': fields.char('DVCE', size=10, help='Not mandatory'),
        'dvce_date': fields.date('DVCE Date', help='Not mandatory'),
        'animo': fields.char('ANIMO', size=10, help='Not mandatory'),
        'sif': fields.char('SIF', size=10, help='Not mandatory'),
        'duty': fields.char('Duty', size=10, help='Not mandatory'),
        'invoice': fields.char('Invoice number', size=10),
        'invoice_date': fields.date('Invoice date'),
        'mrn': fields.char('MRN', size=10, help='Not mandatory'),
        'splitted_from_id': fields.many2one(
            'edi.soap.logistic.line', 'Splitted origin'),
        # XXX Remember duplication wizard when add fields!!!
        # ---------------------------------------------------------------------
        }


class EdiSoapLogisticPallet(orm.Model):
    """ Soap logistic order relations
    """
    _inherit = 'edi.soap.logistic.pallet'

    # -------------------------------------------------------------------------
    # Utility for syntax:
    # -------------------------------------------------------------------------
    def _sscc_check_digit(self, fixed):
        """ Generate check digit and return
        """
        tot = 0
        pos = 0

        for c in fixed:
            pos += 1
            number = int(c)
            if pos % 2 == 0:
                tot += number
            else:
                tot += number * 3

        remain = tot % 10
        if remain:
            return 10 - remain
        else:
            return 0

    # -------------------------------------------------------------------------
    # Utility for syntax:
    # -------------------------------------------------------------------------
    def get_sscc_formatted(self, sscc):
        """ Return in format (00) XXXX...
        """
        return '(%s)%s' % (sscc[:2], sscc[2:])

    def _generate_sscc_code(self, cr, uid, raw=True, context=None):
        """ Generate partial code with counter and add check digit
        """
        fixed = self.pool.get('ir.sequence').get(
            cr, uid, 'sscc.code.pallet.number')
        return '%s%s' % (fixed, self._sscc_check_digit(fixed))

    # -------------------------------------------------------------------------
    # Button:
    # -------------------------------------------------------------------------
    def print_label(self, cr, uid, ids, context=None):
        """ Print single label for pallet:
        """
        if context is None:
            context = {}

        if not ids:
            order_id = context.get('order_id')
            if not order_id:
               raise osv.except_osv(
                   _('Error'),
                   _('Cannot get order to print!'),
                   )
            ids = self.search(cr, uid, [
                ('order_id', '=', order_id),
                ], context=context)

        datas = {
            'pallet_ids': ids,  # single or list
            }

        return { # action report
            'type': 'ir.actions.report.xml',
            'report_name': 'sscc_pallet_label_report',
            'datas': datas,
            }

    # -------------------------------------------------------------------------
    # Field function:
    # -------------------------------------------------------------------------
    def _get_sscc_fullname(self, cr, uid, pallet, context=None):
        """ Get image name for SSCC image file crom current proxy obj
        """
        extension = 'png'
        connection = pallet.order_id.connection_id

        sscc_path = os.path.expanduser(os.path.join(
            connection.server_root,
            'sscc',
            ))
        try:
            os.system('mkdir -p %s' % sscc_path)
            return os.path.join(
                sscc_path,
                '%s.%s' % (
                    pallet.sscc,
                    extension,
                    ))
        except:
            raise osv.except_osv(
                _('Error'), _('Errore generating SSCC path!'))
        return False

    def _get_sscc_codebar_image(self, cr, uid, ids, field_name, arg,
            context=None):
        """ Get image from SSCC folder image
        """
        pallet_proxy = self.browse(cr, uid, ids, context=context)

        res = dict.fromkeys(ids, False)
        for pallet in pallet_proxy:
            try:
                fullname = self._get_sscc_fullname(
                    cr, uid, pallet, context=context)
                f = open(fullname, 'rb')
                res[pallet.id] = base64.encodestring(f.read())
                f.close()
            except:
                _logger.error('Cannot load: %s' % fullname)
        return res

    _columns = {
        'sscc_image': fields.function(
            _get_sscc_codebar_image, type='binary', method=True),
        # TODO remove:
        'line_ids': fields.one2many(
            'edi.soap.logistic.line', 'pallet_id', 'Logistic Lines'),
        }


class EdiSoapLogistic(orm.Model):
    """ Soap logistic order relations
    """
    _inherit = 'edi.soap.logistic'

    _columns = {
        'line_ids': fields.one2many(
            'edi.soap.logistic.line', 'logistic_id', 'Lines'),
        'pallet_ids': fields.one2many(
            'edi.soap.logistic.pallet', 'logistic_id', 'Pallet'),
        }


class EdiSoapOrder(orm.Model):
    """ Soap Parameter for connection
    """
    _inherit = 'edi.soap.order'

    _columns = {
        'line_ids': fields.one2many(
            'edi.soap.order.line', 'order_id', 'Lines'),
        'pallet_ids': fields.one2many(
            'edi.soap.logistic.pallet', 'order_id', 'Pallet'),
        }


class ResPartner(orm.Model):
    """ Model name: Res partner
    """

    _inherit = 'res.partner'

    def res_partner_destination_detail(self, cr, uid, ids, context=None):
        """ Detail partner
        """
        return {
            'type': 'ir.actions.act_window',
            'name': _('Destination'),
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_id': ids[0],
            'res_model': 'res.partner',
            'view_id': False,
            'views': [(False, 'form'), (False, 'tree')],
            'domain': [],
            'context': context,
            'target': 'current',
            'nodestroy': False,
            }

    _columns = {
        'connection_id': fields.many2one(
            'edi.soap.connection', 'Connection'),
        }
