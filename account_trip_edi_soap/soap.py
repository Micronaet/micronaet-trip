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
import sys
import logging
import openerp
import shutil
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

#try:
from zeep import Client
#except:
#    _logger.error('Install zeep dept.: pip install zeep')         


class EdiSoapConnection(orm.Model):
    ''' Soap Parameter for connection
    '''
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
        3: u'Dati errati', # Campi con i dati errati
        4: u'PON non esistente',
        5: u'Numero Ordine non ammesso per il fornitore',
        6: u'Dati acquisti - Ordine incompleto',
        7: u'Dati acquisti - Righe non presenti in ordine', # Righe in più
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
        ''' Change datetime removing gap from now and GMT 0
        '''
        return pytz.utc.localize(datetime.now()).astimezone(
            pytz.timezone('Europe/Rome'))
        
    def _get_error_status(self, status_code):
        ''' Return error comment:
        '''
        return self._response_status.get(status_code, 'Errore non gestito')
        
    def _get_soap_service(self, cr, uid, ids, wsdl_root=False, namespace=False, 
            context=None):
        ''' Get WSDL Service link
            if passed namespace and wsdl root use that, instead of read from 
            parameters
        '''
        if not wsdl_root: # Read from parameters
            parameter = self.browse(cr, uid, ids, context=context)[0]
            namespace = parameter.namespace
            wsdl_root = parameter.wsdl_root         
            
        client = Client(wsdl_root)
        return client.create_service(
            namespace, 
            wsdl_root,
            )

    def check_return_status(self, res, comment):
        ''' Check returned status error
        '''
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
        ''' Login and get token from WSDL
        '''
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

        service = self._get_soap_service(cr, uid, ids, wsdl_root, namespace, 
            context=context)
        res = service.login(
            username=username, time=timestamp, number=number, hash=hash_text)
        self.check_return_status(res, 'Login')
            
        # Get new token and save for next calls: 
        token = res['accessToken']
        self.write(cr, uid, ids, {
            'token': token,
            }, context=context)            
        _logger.warning('Token reloaded')
        return token
    
    # -------------------------------------------------------------------------
    # Button events:
    # -------------------------------------------------------------------------
    # Server:
    def load_new_invoice(self, cr, uid, ids, context=None):
        ''' Load invoice from file
        '''
        # ---------------------------------------------------------------------
        # Function
        # ---------------------------------------------------------------------
        def log_data(log_f, comment, mode='INFO', newline='\r\n'):
            ''' Write comment on log file:
            '''
            return log_f.write('%s [%s] %s%s' % (
                datetime.now(),
                mode,
                comment,
                cr,
                ))                
        def get_weight(value):
            ''' Clean weight text:
            '''
            try:
                return float(
                    value.lstrip('KG').lstrip('.').lstrip().replace(',', '.'))
            except:
                return 0.0 # TODO raise error        

        # Pool used:
        logistic_pool = self.pool.get('edi.soap.logistic')
        line_pool = self.pool.get('edi.soap.logistic.line')
        pallet_pool = self.pool.get('edi.soap.logistic.pallet')
        
        # ---------------------------------------------------------------------
        # Parameters:
        # ---------------------------------------------------------------------
        newline = '\r\n'
        separator = '|*|'
        start = { # Start text on file:
            'header': 'HEADER',
            'detail': 'DETAIL',
            'invoice': 3,
            'invoice_date': 4,
            'weight': 'PESO LORDO: ',
            'order': 'N.ORDINE',
            'lord': 'PESO LORDO',
            'total': 'PESO TOTALE',
            'pallet': 'BANCALI',
            }

        # Load parameters:
        parameter = self.browse(cr, uid, ids, context=context)[0]
        path = os.path.expanduser(parameter.server_root)
        partner_start = parameter.server_account_code.split('|')
        if not partner_start or not path:
            raise osv.except_osv(
                _('Error'), 
                _('Check parameter on SAOP Configuration!'),
                )

        partner_len = len(partner_start[0])

        # ---------------------------------------------------------------------
        # Extra path:
        # ---------------------------------------------------------------------
        # Path used:
        history_path = os.path.join(path, 'history')
        unsed_path = os.path.join(path, 'unsed')
        log_path = os.path.join(path, 'log')

        # Create process:
        for folder in (path, history_path, unsed_path, log_path):
            os.system('mkdir -p %s' % folder)
        
        # ---------------------------------------------------------------------
        # Check folder for files:
        # ---------------------------------------------------------------------
        log_f = open(os.path.join(log_path, 'invoice.log'), 'w')
        remove_list = []
        history_list = []
        for root, foldes, files in os.walk(path):
            for filename in files:
                fullname = os.path.join(root, filename)                
                if filename[:partner_len] not in partner_start:
                    remove_list.append(fullname)
                    continue
                history_list.append(
                    (fullname, os.path.join(history_path, filename)))

                log_data(log_f, 'File checked: %s' % filename)

                # Read file (last part)
                data = { # Collect order data
                    'i': 0,
                    'text': '',
                    'detail_status': 'off',
                    'product_insert': False, # for double weight
                    'detail_text': '',
                    'error': False,
                    'error_comment': '',
                    
                    #'header': '',
                    #'detail': [],                 
                    #'footer': {},
                    }
                    
                for line in open(fullname):
                    data['i'] += 1
                    line = line.strip()
                    
                    # Keep only last part of the file:    
                    data['text'] += line + newline
                    
                    # ---------------------------------------------------------
                    # Check part of document:
                    # ---------------------------------------------------------
                    if line.startswith(start['header']):
                        data.update({
                            'header': line,
                            'i': 1, # Restart from 1
                            'text': line + newline, # Restart from here

                            'detail': [],                 
                            'footer': {},
                            })
                    elif line.startswith(start['detail']):
                        data['detail_status'] = 'on'

                    # ---------------------------------------------------------
                    #                         Header data:
                    # ---------------------------------------------------------
                    elif data['i'] == start['invoice']: # Invoice number
                        data['invoice'] = line                        
                    elif data['i'] == start['invoice_date']: # Invoice date
                        data['invoice_date'] = line

                    # ---------------------------------------------------------
                    #                         Detail data:
                    # ---------------------------------------------------------
                    elif data['detail_status'] == 'on': # Start details
                        if line.startswith(separator): # Detail line
                            data['detail_text'] = line
                            data['product_insert'] = False
                        elif line.startswith(start['weight']):
                            if data['product_insert']:
                                # Check error (ex. 2 PESO LORDO line)
                                _logger.warning('Extra line: %s' % line)
                            else: 
                                data['detail'].append((
                                    data['detail_text'], 
                                    get_weight(line[len(start['weight']):]),
                                    ))
                                data['product_insert'] = True
                            
                        elif not line: # End detail block
                            data['detail_status'] = 'end'
                        else:
                            data['error'] = True
                            data['error_comment'] += \
                                '%s Detail without correct schema' % data['i']
                        
                    # ---------------------------------------------------------
                    #                       End of document part:
                    # ---------------------------------------------------------
                    elif data['detail_status'] == 'end': # Start details
                        # CONSEGNA DEL:
                        # DESTINAZIONE: 
                        if line.startswith(start['order']):
                            pass # TODO
                        elif line.startswith(start['lord']):
                            pass # TODO
                        elif line.startswith(start['total']):
                            pass # TODO                        
                        elif line.startswith(start['pallet']):
                            pass # TODO
                           
                # -------------------------------------------------------------
                # Create ODOO Record:                
                # -------------------------------------------------------------
                name = 'FT %s del %s' % (data['invoice'], data['invoice_date'])
                logistic_ids = logistic_pool.search(cr, uid, [
                    ('name', '=', name),
                    ], context=context)

                if logistic_ids:
                    logistic = logistic_pool.browse(
                        cr, uid, logistic_ids, context=context)[0]
                    if logistic.state != 'draft':
                        # Yet load cannot override:
                        # TODO move in after folder (unused)
                        continue
                        
                    # Delete and override:
                    logistic_pool.unlink(
                        cr, uid, logistic_ids, context=context)

                # Bug management:                
                text = data['text'].replace('\xb0', ' ')
                
                # A. Import order:
                logistic_id = logistic_pool.create(cr, uid, {
                    'name': name,
                    'connection_id': ids[0],
                    'text': text,
                    }, context=context)

                # B. Import order line:
                sequence = 0
                for row, weight in data['detail']:
                    sequence += 10
                    line_part = row.split(separator)
                    line_pool.create(cr, uid, {
                        'sequence': sequence,
                        'logistic_id': logistic_id,
                        'name': line_part[2],
                        # TODO remain fields
                        }, context=context)
                
            break # only path folder

        # ---------------------------------------------------------------------
        # Remove unused file:        
        # ---------------------------------------------------------------------
        for fullname in remove_list:
            os.remove(fullname)
            log_data(log_f, 'File removed: %s' % filename, 
                mode='WARNING')
        for filename, history in history_list:
            shutil.move(filename, history)
            log_data(log_f, 'File history: %s > %s' % (filename, history))
          
        log_f.close()
        return True

    # SOAP: 
    def get_token(self, cr, uid, ids, context=None):
        ''' Try to use previous token or get new one for period
        '''
        return self._soap_login(cr, uid, ids, context=context)

    def load_new_order(self, cr, uid, ids, context=None):
        ''' Load order from WSDL Soap Connection
        '''
        order_pool = self.pool.get('edi.soap.order')

        service = self._get_soap_service(cr, uid, ids, context=context)

        res = service.getOngoingPOrders(
            accessToken=self.get_token(cr, uid, ids, context=context))            
        self.check_return_status(res, 'Load new order') 
        
        # TODO Manage token problem
        for order in res['orders']:
            order_pool.create_new_order(
                cr, uid, ids[0], order, force=False, context=context)
        return True

    _columns = {
        'name': fields.char('Soap Connection', size=64, required=True),
        'token': fields.char('Soap token', size=180, 
            help='Token assigned and saved when updated'),

        # Soap connection:
        'username': fields.char('Username', size=40, required=True),
        'secret': fields.char('Secret', size=180, required=True),        
        'wsdl_root': fields.char('WSDL Root', size=180, required=True, 
            help='Example: https://example.com/pep/wsdl'),
        'namespace': fields.char('Namespace', size=40, required=True,
            help='Example: {it.example.soapws.ws}WsPortSoap11'),
        
        # Server connection:    
        'server_root': fields.char('Server Root', size=180, required=True, 
            help='Example: ~/account/invoice'),
        'server_account_code': fields.char('Account code', size=180, 
            required=True, 
            help='Account ref. for partners, ex: 02.00001|02.00002'),
        'detail_separator': fields.char('Detail separator', size=5, 
            required=True, help='Separator used for detail columns'),
        }
    
    _defaults = {
        'detail_separator': lambda *x: '|*|',
        }

class EdiSoapOrder(orm.Model):
    ''' Soap Soap Order
    '''
    _name = 'edi.soap.order'
    _description = 'EDI Soap Order'
    _rec_name = 'name'
    _order = 'name'

    # -------------------------------------------------------------------------
    # Utility:
    # -------------------------------------------------------------------------
    def _safe_get(self, item, field, default=False):
        ''' Safe eval the field data
        ''' 
        try:
            return eval("item[field] or default")
        except:    
            _logger.error('Cannot eval: field %s' % field)
            return default

    def create_new_order(self, cr, uid, connection_id, order, force=False, 
            context=None):
        ''' Create new order from order object
        '''        
        line_pool = self.pool.get('edi.soap.order.line')
        po_number = self._safe_get(order, 'poNumber')        
        order_ids = self.search(cr, uid, [
            ('name', '=', po_number),
            ], context=context)

        if order_ids:
            if force:
                # Delete and recreate
                _logger.warning('Order deleted for recreation: %s' % (
                    order_ids,
                    ))
                self.unlink(cr, uid, order_ids, context=context)
            else:
                _logger.warning('Order %s yet present' % po_number)                 
                return False

        header = {
            'connection_id': connection_id,
            'name': self._safe_get(order, 'poNumber'), # '2110479-FB04023'
            #'delivery_date': self._safe_get(
            #    order, 'deliveryDate'), # None,
            'entity_name': self._safe_get(
                order, 'entityName'),# 'MV Poesia',
            'delivery_port_nam': self._safe_get(
                order, 'deliveryPortName'), # u'Wa\xfcnde',
            'status': self._safe_get(
                order, 'status'),# 'Emitted',
            #'po_create_date': self._safe_get(
            #    order, 'createDate'),# None,
            'currency': self._safe_get(
                order, 'currency'),# 'EUR',
            'fullname': self._safe_get(
                order, 'fullName'),# 'xxx yyy',
            #'document_value': self._safe_get(
            #    order, 'documentValue'),#: Decimal('234.20000')
            'buyer_group': self._safe_get(
                order, 'buyerGroup'),#: 'Buyers',
            #'delivery_terms': self._safe_get(
            #    order, 'deliveryTerms'),#: None,
            #'info_container': self._safe_get(
            #    order, 'infoContainer'),#: None,
            #'document_comment': self._safe_get(
            #    order, 'documentComment'),#: None,
            'invoice_holder': self._safe_get(
                order, 'invoiceHolder'),#: 'Cruises',
            'invoice_address': self._safe_get(
                order, 'invoiceAddress'),#: u'Eug\xe8ne 40 120 GENEVA (CH)'
            'invoice_vatcode': self._safe_get(
                order, 'invoiceVatcode'),#: 'CHE-123.808.357 TVA',
            'delivery_at': self._safe_get(
                order, 'deliveryAt'),# 'Comando nave',
            'delivery_address': self._safe_get(
                order, 'deliveryAddress'),# 'Via X 91 Genova 16162 Italy',
            #'delivery_ship': self._safe_get(
            #    order, 'deliveryShip'),#: None,
            #'logistic': self._safe_get(
            #    order, 'logistic'),# False,
            #'requires_logistic': self._safe_get(
            #    order, 'requiresLogistic'),# None,
            }            

        # Create order not present:    
        order_id = self.create(cr, uid, header, context=context)
        _logger.info('New Order %s' % po_number)                 

        # TODO load also file for ERP Management

        for line in order['orderLines']:
            # -------------------------------------------------------------
            # Detail data:
            # -------------------------------------------------------------
            line = {
                'order_id': order_id,
                'name': self._safe_get(
                    line, 'itemCode'), # 'F0000801',
                'description': self._safe_get(
                    line, 'itemDescription'), # 'CORN KERNEL WHOLE FRZ',
                #'item_price': self._safe_get(
                #    line, 'itemPrice'), # Decimal('0.93000'),
                'uom': self._safe_get(
                    line, 'itemReceivingUnit'), # 'KG',
                'ordered_qty': float(self._safe_get(
                    line, 'quantityOrdered', 0.0)), # Decimal('230.00000'),
                'confirmed_qty': float(self._safe_get(
                    line, 'quantityConfirmed', 0.0)), # Decimal('230.00000'),                    
                'logistic_qty': float(self._safe_get(
                    line, 'quantityLogistic', 0.0)), # None,
                
                #'cd_gtin': self._safe_get(
                #    line, 'cdGtin'), # None,
                #'cd_voce_doganale': self._safe_get(
                #    line, 'cdVoceDoganale'), # None,
                #'nr_pz_conf': self._safe_get(
                #    line, 'nrPzConf'), # None,
                #'cd_paese_origine': self._safe_get(
                #    line, 'cdPaeseOrigine'), # None,
                #'cd_paese_provenienza': self._safe_get(
                #    line, 'cdPaeseProvenienza'), # None,
                #'fl_dogana': self._safe_get(
                #    line, 'flDogana'), # None
                }                    
            line_pool.create(cr, uid, line, context=context)
        return order_id

    # -------------------------------------------------------------------------
    # Button events:
    # -------------------------------------------------------------------------
    def reload_this_order(self, cr, uid, ids, context=None):
        ''' Reload this order
        '''
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
            'target': 'current', # 'new'
            'nodestroy': False,
            }    

    _columns = {
        'name': fields.char(
            'PO Number', size=40, required=True),
        'connection_id': fields.many2one(
            'edi.soap.connection', 'Connection', required=True),
        # delivery_date = order.get('deliveryDate', False) # None,
        'entity_name': fields.char('Entity name', size=40),
        'delivery_port_nam': fields.char('Delivery Port Nam', size=40),
        'status': fields.char('Status', size=40),
        # create_date = order.get('createDate', False)# None,
        'currency': fields.char('currency', size=10),
        'fullname': fields.char('Full name', size=40),
        #document_value = order.get('documentValue', False)#: 234.20000,
        'buyer_group': fields.char('Buyer Group', size=30),
        #delivery_terms = order.get('deliveryTerms', False)#: None,
        #info_container = order.get('infoContainer', False)#: None,
        #document_comment = order.get('documentComment', False)#: None,
        'invoice_holder': fields.char('Invoice Holder', size=40),
        'invoice_address': fields.char('Invoice Address', size=60),
        'invoice_vatcode': fields.char('Invoice VAT code', size=40),
        'delivery_at': fields.char('Delivery at', size=40),
        'delivery_address': fields.char('Delivery Address', size=40),
        #delivery_ship = order.get('deliveryShip', False)#: None,
        #logistic = order.get('logistic', False)# False,
        #requires_logistic = order.get('requiresLogistic', False)# None,
        }    

class EdiSoapOrderLine(orm.Model):
    ''' Soap order line
    '''
    _name = 'edi.soap.order.line'
    _description = 'EDI Soap Order line'
    _rec_name = 'name'
    _order = 'name'

    _columns = {
        'name': fields.char('Code', size=40, required=True),
        'order_id': fields.many2one('edi.soap.order', 'Order', 
            ondelete='cascade'),

        'description': fields.char('Description', size=40),
        #'price': fields.char('', size=40),
        'uom': fields.char('UOM', size=10),
        'ordered_qty': fields.float('Ordered', digits=(16, 3)),
        'confirmed_qty': fields.float('Confirmed', digits=(16, 3)),
        'logistic_qty': fields.float('Logistic', digits=(16, 3)),

        #'item_price'
        #'cd_gtin'
        #'cd_voce_doganale'
        #'nr_pz_conf'
        #'cd_paese_origine'
        #'cd_paese_provenienza'
        #'fl_dogana'
        }

class EdiSoapOrder(orm.Model):
    ''' Soap Parameter for connection
    '''
    _inherit = 'edi.soap.order'
    
    _columns = {
        'line_ids': fields.one2many('edi.soap.order.line', 'order_id', 'Lines'),
        }

# -----------------------------------------------------------------------------
#                              LOGISTIC ORDER:
# -----------------------------------------------------------------------------
class EdiSoapLogistic(orm.Model):
    ''' Soap logistic order
    '''
    _name = 'edi.soap.logistic'
    _description = 'EDI Soap Logistic'
    _rec_name = 'name'
    _order = 'name'

    _columns = {
        'name': fields.char('Invoice reference', size=40, required=True),
        'connection_id': fields.many2one(
            'edi.soap.connection', 'Connection', required=True),
        'pallet': fields.integer('Pallet #'),
        'text': fields.text('File text', help='Account file as original'),
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
    ''' Soap logistic order
    '''
    _name = 'edi.soap.logistic.pallet'
    _description = 'EDI Soap Logistic Pallet'
    _rec_name = 'name'
    _order = 'name'

    _columns = {
        'name': fields.integer('#', required=True),
        'sscc': fields.char('SSCC Code', size=40, required=True),
        'logistic_id': fields.many2one('edi.soap.logistic', 'Logistic order'),
        }        

class EdiSoapLogistic(orm.Model):
    ''' Soap logistic order
    '''
    _name = 'edi.soap.logistic.line'
    _description = 'EDI Soap Logistic Line'
    _rec_name = 'name'
    _order = 'name'

    _columns = {
        'sequence': fields.integer('Seq.'),
        'name': fields.char('Article', size=40, required=True),
        # TODO add extra fields
        'logistic_id': fields.many2one('edi.soap.logistic', 'Logistic order'),
        'pallet_id': fields.many2one('edi.soap.logistic.pallet', 'Pallet'),
        # Doganale
        # Collo
        # EAN
        # Peso Variabile
        # Lotto
        # Prevista
        # Netto
        # Lordo
        # Colli
        # Pezzi confez.
        # Scadenza
        # Paese origina
        # Paese Provenienza
        # DVCE
        # DVCE Data
        
        }

class EdiSoapLogisticPallet(orm.Model):
    ''' Soap logistic order relations
    '''
    _inherit = 'edi.soap.logistic.pallet'

    _columns = {
        'line_ids': fields.one2many(
            'edi.soap.logistic.line', 'pallet_id', 'Lines'),
        }
    
class EdiSoapLogistic(orm.Model):
    ''' Soap logistic order relations
    '''
    _inherit = 'edi.soap.logistic'
    
    _columns = {
        'line_ids': fields.one2many(
            'edi.soap.logistic.line', 'logistic_id', 'Lines'),
        'pallet_ids': fields.one2many(
            'edi.soap.logistic.pallet', 'logistic_id', 'Pallet'),
        }    

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
