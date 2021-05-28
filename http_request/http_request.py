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
import requests
from openerp.osv import fields, osv, expression, orm
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from openerp import SUPERUSER_ID
from openerp import tools
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
                _('Connection error: ' % reply.text),
                )

        self.write(cr, uid, ids, {
            'token': token,
            'token_expire': token_expire,
        }, context=context)
        return token

    _columns = {
        'name': fields.char('Name', size=64, required=True),
        'endpoint': fields.char(
            'Token endpoint', size=30, required=True,
            help='Endpoint to get token value'),
        'username': fields.char('Username', size=64, required=True),
        'password': fields.char('Password', size=64, required=True),
        'root': fields.char('Root url', size=80, required=True),
        'token': fields.char('Root url', size=180),
        'token_expire': fields.char('Root url', size=80),
    }


class HttpRequestEndpoint(orm.Model):
    """ Model name: HTTP Request endpoint
    """

    _name = 'http.request.endpoint'
    _description = 'HTTP Connection endpoint'
    _rec_name = 'name'
    _order = 'name'

    def call_endpoint(self, cr, uid, ids, context=None):
        """ Call end point and return result
        """
        connection_pool = self.pool.get('http.request.connection')
        endpoint = self.browse(cr, uid, ids, context=context)[0]
        connection = endpoint.connection_id
        token = connection_pool.get_token(
            cr, uid, [connection.id], context=context)
        url = '%s/%s' % (
            connection.root,
            endpoint,
        )
        header = {
            'Authorization': 'token %s' % token,
        }
        # todo needed?
        # content = {
        #    'content-type': endpoint.content,
        # }

        reply = requests.get(url=url, headers=header)
        if reply.ok:
            return reply.json()  # todo keep as parameter
        else:
            raise osv.except_osv(
                _('Endpoint error:'),
                _('Connection error: ' % reply.text),
                )

    _columns = {
        'name': fields.char('Name', size=64, required=True),
        'code': fields.char('Code', size=30, required=True),
        'endpoint': fields.char('Endpoint', size=40, required=True),
        # 'content': fields.char('Content type', size=40, required=True),
        'connection_id': fields.many2one(
            'http.request.connection', 'Connection'),
    }
    _defaults = {
        'context': lambda *x: 'application/json',
    }


class HttpRequestConnectionRelation(orm.Model):
    """ Model name: HTTP Request connection relations
    """

    _inherit = 'http.request.connection'

    _columns = {
        'endpoint_ids': fields.one2many(
            'http.request.endpoint', 'connection_id', 'Endpoint')
    }