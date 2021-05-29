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
import requests
from openerp.osv import fields, osv, expression, orm
from datetime import datetime, timedelta
from openerp.tools.translate import _
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT,
    DEFAULT_SERVER_DATETIME_FORMAT,
    DATETIME_FORMATS_MAP,
    float_compare)

_logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# HTTP Request
# -----------------------------------------------------------------------------
class HttpRequestConnection(orm.Model):
    """ Model name: HTTP Request connection
    """

    _name = 'http.request.connection'
    _description = 'HTTP Connection'
    _rec_name = 'name'
    _order = 'name'

    def get_token(self, cr, uid, ids, context=None):
        """ Return token
        """
        connection = self.browse(cr, uid, ids, context=context)[0]
        # todo check token_expire to understand in it's necessary reload token
        url = '%s/%s?username=%s&password=%s' % (
            connection.root,
            connection.endpoint,
            connection.username,
            connection.password,
        )
        reply = requests.get(url)
        if reply.ok:
            reply_json = reply.json()
            token = reply_json['JWTToken']
            token_expire = reply_json['Exp']
        else:
            raise osv.except_osv(
                _('Connection error:'),
                _('Connection error: %s' % reply.text),
                )

        self.write(cr, uid, ids, {
            'token': token,
            'token_expire': token_expire,
        }, context=context)
        return token

    _columns = {
        'name': fields.char('Name', size=64, required=True),
        'endpoint': fields.char(
            'Token endpoint', size=100, required=True,
            help='Endpoint to get token value'),
        'username': fields.char('Username', size=64, required=True),
        'password': fields.char('Password', size=64, required=True),
        'root': fields.char('Root url', size=100, required=True),
        'token': fields.text('Root url', size=300),
        'token_expire': fields.char('Root url', size=80),
    }


class HttpRequestEndpoint(orm.Model):
    """ Model name: HTTP Request endpoint
    """

    _name = 'http.request.endpoint'
    _description = 'HTTP Connection endpoint'
    _rec_name = 'name'
    _order = 'name'

    def endpoint_detail(self, cr, uid, ids, context=None):
        """ Open endpoint detail
        """
        model_pool = self.pool.get('ir.model.data')
        view_id = model_pool.get_object_reference(
            cr, uid,
            'http_request', 'view_http_endpoint_form')[1]

        return {
            'type': 'ir.actions.act_window',
            'name': _('Dettaglio end point'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': ids[0],
            'res_model': 'http.request.endpoint',
            'view_id': view_id,
            'views': [(view_id, 'form')],
            'domain': [],
            'context': context,
            'target': 'new',
            'nodestroy': False,
            }

    def call_endpoint(self, cr, uid, ids, context=None):
        """ Call end point and return result
            context parameter:
                some endpoint has parameter in {name} form so in
                context pass data for those parameter, ex.:
                endpoint_xxx?from_date={data_from}

                In context:
                   'endpoint_params': {
                      'data_from': '20210101'}}
                   'payload': {},   # For POST call
        """
        parameter = context.get('endpoint_params', {})
        payload = context.get('payload', {})

        connection_pool = self.pool.get('http.request.connection')
        endpoint = self.browse(cr, uid, ids, context=context)[0]
        connection = endpoint.connection_id
        token = connection_pool.get_token(
            cr, uid, [connection.id], context=context)
        url = '%s/%s' % (
            connection.root,
            endpoint.endpoint,
        )
        for name in parameter:
            url = url.replace('{%s}' % name, parameter[name])
        header = {
            'Authorization': 'token %s' % token,
            'content-type': endpoint.content,
        }
        _logger.info('Calling: %s\nParameter: %s' % (
            url, header))
        if endpoint.mode == 'get':
            reply = requests.get(url=url, headers=header)
        if endpoint.mode == 'post':
            reply = requests.post(url=url, headers=header, data=payload)

        if reply.ok:
            reply_json = reply.json()
            _logger.warning('Result: %s' % reply_json)
            return reply.json()  # todo keep as parameter (json)
        else:
            raise osv.except_osv(
                _('Endpoint error:'),
                _('Connection error: %s' % reply.text),
                )

    _columns = {
        'name': fields.char('Name', size=64, required=True),
        'code': fields.char('Code', size=30, required=True),
        'endpoint': fields.char('Endpoint', size=150, required=True),
        'content': fields.char('Content type', size=40, required=True),
        'connection_id': fields.many2one(
            'http.request.connection', 'Connection'),
        'payload': fields.text(
            'Payload', help='Oggetto JSON passato alla chiamata POST'),
        'mode': fields.selection([
            ('get', 'GET'),
            ('post', 'POST'),
        ], string='Modalità', required=True)
    }
    _defaults = {
        'content': lambda *x: 'application/json',
        'mode': lambda *x: 'get',
    }


class HttpRequestConnectionRelation(orm.Model):
    """ Model name: HTTP Request connection relations
    """

    _inherit = 'http.request.connection'

    _columns = {
        'endpoint_ids': fields.one2many(
            'http.request.endpoint', 'connection_id', 'Endpoint')
    }
