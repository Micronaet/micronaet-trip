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
try:
    from zeep import Client
except:
    _logger.error('Install zeep dept.: pip install zeep')         


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
    _error_status = {
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
    def _get_error_status(self, error_code):
        ''' Return error comment:
        '''
        return self._error_status.get(error_code, 'Errore non gestito')
        
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
        
    def _soap_login(self, cr, uid, ids, context=None):
        ''' Login and get token from WSDL
        '''
        parameter = self.browse(cr, uid, ids, context=context)[0]
        message_mask = 'GET+/users/%s/account+%s+%s'
        token = parameter.token
        namespace = parameter.namespace
        #'{it.niuma.mscsoapws.ws}MscWsPortSoap11'
        wsdl_root = parameter.wsdl_root         
        # 'https://layer7test.msccruises.com/pep/wsdl'  DEMO
        # 'https://layer7prod.msccruises.com/pep/wsdl'  PRODUCTION

        # ---------------------------------------------------------------------
        # Check if present last token saved:        
        # ---------------------------------------------------------------------
        if token:
            return token

        # ---------------------------------------------------------------------
        #                                 LOGIN:
        # ---------------------------------------------------------------------
        # Parameter for call:
        timestamp = datetime.now().strftime('%d%m%Y%H%M%S')
        number = str(uuid.uuid4())[-6:]
        message = message_mask % (username, timestamp, number)

        # HMAC encrypt:
        signature = hmac.new(
            secret, msg=message, digestmod=hashlib.sha256).digest()
        hash_text = base64.b64encode(signature)

        # Link client and WSDL service:
        service = self._get_soap_service(cr, uid, ids, wsdl_root, namespace, 
            context=context)

        res = service.login(
            username=username, time=timestamp, number=number, hash=hash_text)

        try:
            status_code = res['operationOutcome']['statusCode']
        except:
            raise osv.except_osv(
                _('SOAP Error'), 
                _('Cannot login to SOAP WS: unmanaged error!'),
                )

        if status_code:
            raise osv.except_osv(
                _('SOAP Error'), 
                _('Cannot login to SOAP WS: %s!') % self._get_error_status(
                    error_code)
                )
            
        # Get new token and save for next calls:    
        token = res['accessToken']
        self.write(cr, uid, ids, {
            'token': token,
            }, context=context)
            
        return token
    
    def get_token(self, cr, uid, ids, context=None):
        ''' Try to use previous token or get new one for period
        '''
        return self._soap_login(cr, uid, ids, context=context)

    def load_new_order(self, cr, uid, ids, context=None):
        ''' Load order from WSDL Soap Connection
        '''
        service = self._get_soap_service(cr, uid, ids, context=context)

        res = service.getOngoingPOrders(
            accessToken=self.get_token(cr, uid, ids, context=context))
            
        # TODO Manage new order and import    
        # 1. Check if not present 
        # 2. Create
        
        return True

        
    _columns = {
        'name': fields.char('Soap Connection', size=64, required=True),
        'company_id': fields.many2one('res.company', 'Company', required=True),
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

    # TODO Reload operation

    _columns = {
        'name': fields.char(
            'Ref.', size=40, required=True),
        'connection_id': fields.many2one(
            'edi.soap.connection', 'Connection', required=True),
            
        }    

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
