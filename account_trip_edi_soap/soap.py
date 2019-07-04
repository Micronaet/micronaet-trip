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
    def get_token(self, cr, uid, ids, context=None):
        ''' Try to use previous token or get new one for period
        '''
        return self._soap_login(cr, uid, ids, context=context)

    def load_new_order(self, cr, uid, ids, context=None):
        ''' Load order from WSDL Soap Connection
        '''
        order_pool = self.pool.get('edi.soap.order')

        service = self._get_soap_service(cr, uid, ids, context=context)

        import pdb; pdb.set_trace()        
        res = service.getOngoingPOrders(
            accessToken=self.get_token(cr, uid, ids, context=context))            
        self.check_return_status(res, 'Load new order') 
        
        # TODO Manage token problem
        import pdb; pdb.set_trace()
        for order in res['orders']:
            # -----------------------------------------------------------------
            # Header data:
            # -----------------------------------------------------------------
            po_number = order.get('poNumber', False)
            
            order_ids = order_pool.search(cr, uid, [
                ('po_number', '=', po_number),
                ], context=context)
            if order_ids:
                _logger.warning('Order %s yet present' % po_number)                 
                continue      
                
            header = {
                'po_number': po_number, # '2198110479-FB04023',
                'delivery_date': order.get(
                    'deliveryDate', False), # None,
                'entity_name': order.get(
                    'entityName', False),# 'MV Poesia',
                'delivery_port_nam': order.get(
                    'deliveryPortName', False), # u'Wa\xfcnde',
                'status': order.get(
                    'status', False),# 'Emitted',
                'create_date': order.get(
                    'createDate', False),# None,
                'currency': order.get(
                    'currency', False),# 'EUR',
                'fullname': order.get(
                    'fullName', False),# 'xxx yyy',
                'document_value': order.get(
                    'documentValue', False),#: Decimal('234.20000')
                'buyer_group': order.get(
                    'buyerGroup', False),#: 'Buyers',
                'delivery_terms': order.get(
                    'deliveryTerms', False),#: None,
                'info_container': order.get(
                    'infoContainer', False),#: None,
                'document_comment': order.get(
                    'documentComment', False),#: None,
                'invoice_holder': order.get(
                    'invoiceHolder', False),#: 'Cruises',
                'invoice_address': order.get(
                    'invoiceAddress', False),#: u'Eug\xe8ne 40 120 GENEVA (CH)'
                'invoice_vatcode': order.get(
                    'invoiceVatcode', False),#: 'CHE-123.808.357 TVA',
                'delivery_at': order.get(
                    'deliveryAt', False),# 'Comando nave',
                'delivery_address': order.get(
                    'deliveryAddress', False),# 'Via X 91 Genova 16162 Italy',
                'delivery_ship': order.get(
                    'deliveryShip', False),#: None,
                'logistic': order.get(
                    'logistic', False),# False,
                'requires_logistic': order.get(
                    'requiresLogistic', False),# None,
                }            
                
            # Create order not present:    
            order_pool.create(cr, uid, header, context=context)
            # TODO load also file for ERP Management
    
            for line in order.get('orderLines', []):
                # -------------------------------------------------------------
                # Detail data:
                # -------------------------------------------------------------
                line = {
                    'item_code': order.get(
                        'itemCode', False), # 'F0000801',
                    'item_description': order.get(
                        'itemDescription', False), # 'CORN KERNEL WHOLE FRZ',
                    'item_price': order.get(
                        'itemPrice', False), # Decimal('0.93000'),,
                    'item_receiving_unit': order.get(
                        'itemReceivingUnit', False), # 'KG',
                    'quantity_ordered': order.get(
                        'quantityOrdered', False), # Decimal('230.00000'),,
                    'quantity_confirmed': order.get(
                        'quantityConfirmed', False), # Decimal('230.00000'),,
                    'quantity_logistic': order.get(
                        'quantityLogistic', False), # None,
                    'cd_gtin': order.get(
                        'cdGtin', False), # None,
                    'cd_voce_doganale': order.get(
                        'cdVoceDoganale', False), # None,
                    'nr_pz_conf': order.get(
                        'nrPzConf', False), # None,
                    'cd_paese_origine': order.get(
                        'cdPaeseOrigine', False), # None,
                    'cd_paese_provenienza': order.get(
                        'cdPaeseProvenienza', False), # None,
                    'fl_dogana': order.get(
                        'flDogana', False), # None
                    }
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
        }

class EdiSoapOrder(orm.Model):
    ''' Soap Parameter for connection
    '''
    _name = 'edi.soap.order'
    _description = 'EDI Soap Order'
    _rec_name = 'name'
    _order = 'name'

    # TODO Reload operation needes?

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
        #document_value = order.get('documentValue', False)#: Decimal('234.20000'),
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

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
