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


class EdiCompany(orm.Model):
    """ Model name: Edi Company
    """
    _inherit = 'edi.company'

    def import_platform_supplier_order(self, cr, uid, ids, context=None):
        """ Import supplier order from platform
            Period always yesterday to today (lauched every day)
        """
        company = self.browse(cr, uid, ids, context=context)[0]
        # Call end point for get order:
        # 20210101 data format
        connection_pool = self.pool.get('http.request.endpoint')
        ctx = context.copy()
        from_date = str(datetime.now() - timedelta(days=1))[:10].replace(
            '-', '')
        to_date = str(datetime.now())[:10].replace('-', '')
        ctx['endpoint_params'] = {
            'data_from': company.force_from_date or from_date,
            'data_to': company.force_to_date or to_date,
        }

        orders = connection_pool.call_endpoint(
            cr, uid, [company.endpoint_id.id], context=ctx)

        _logger.info(str(orders))

    _columns = {
        'has_platform': fields.boolean('Has platform'),
        'connection_id': fields.many2one(
            'http.request.connection', 'Connection'),
        'endpoint_id': fields.many2one(
            'http.request.endpoint', 'Endpoint'),
        'force_from_date': fields.char(
            'Forza dalla data', size=19,
            help='Forza la data di partenza per leggere gli ordini, formato: '
                 'AAAAMMGG'),
        'force_to_date': fields.char(
            'Forza alla data', size=19,
            help='Forza la data di arrivo per leggere gli ordini, formato: '
                 'AAAAMMGG'),
    }


class EdiSupplierOrder(orm.Model):
    """ Model name: Edi Supplier Order
    """

    _name = 'edi.supplier.order'
    _description = 'Supplier order'
    _rec_name = 'name'
    _order = 'name'

    _columns = {
        'name': fields.char('Numero ordine', size=30, required=True),
        'supplier_code': fields.char(
            'Codice produttore', size=30, required=True),
        'dealer': fields.char('Concessionario', size=30),
        'dealer_code': fields.char('Codice Concessionario', size=30),
        'supplier': fields.char('Ragione sociale produttore', size=40),
        'order_date': fields.char('Data ordine', size=20),
        'deadline_date': fields.char('Data consegna richiesta', size=20),
        'note': fields.text('Nota ordine'),
    }
# 'NUMERO_ORDINE': u'210083054_000', 'RAGIONE_SOCIALE_PRODUTTORE':
# u'PANAPESCA SPA', 'DATA_ORDINE': u'20210510', 'DATA_CONSEGNA_RICHIESTA':
# u'20210505', 'NOTA_ORDINE': u'',
# 'CONCESSIONARIO': u'PANAPESCA SPA' 'CODICE_CONCESSIONARIO': u'1335',
# 'CODICE_PRODUTTORE': u'ITA000061',


class EdiSupplierOrderLine(orm.Model):
    """ Model name: Edi Supplier Order Line
    """

    _name = 'edi.supplier.order.line'
    _description = 'Supplier order line'
    _rec_name = 'name'
    _order = 'sequence'

    _columns = {
        'sequence': fields.char('Seq.', size=4),
        'name': fields.char(
            'Descrizione articolo', size=40, required=True),
        'supplier_name': fields.char(
            'Descrizione articolo produttore', size=40),
        'supplier_code': fields.char('Codice produttore', size=20),
        'code': fields.char('Codice articolo', size=20),
        'uom_supplier': fields.char('UM fornitore', size=10),
        'uom_product': fields.char('UM prodotto', size=10),
        'product_qty': fields.char('Q.', size=20),  # todo change in float
        'order_product_qty': fields.char('Q.', size=20),
        'note': fields.char('Nota riga', size=40),
        'order_id': fields.many2one('edi.supplier.order', 'Ordine produttore'),
    }

# 'RIGA_ORDINE': u'1', 'CODICE_ARTICOLO_PRODUTTORE': u'419490',
# 'CODICE_ARTICOLO': u'AV030149',
# 'UM_ARTICOLO_PRODUTTORE': u'KG', 'DESCRIZIONE_ARTICOLO_PRODUTTORE':
# u'FILETTI DI PANGASIO CONGELATI',
# 'QTA_ORDINE': u'00000004700000', 'UM_ARTICOLO': u'KG',
# 'QTA_ORDINE_PRODUTTORE': u'00000004700000',
# 'NOTA_RIGA': u'', 'DESCRIZIONE_ARTICOLO': u'PANGASIO FILETTI
# SP 100-180GR GELO',


class EdiSupplierOrderRelation(orm.Model):
    """ Model name: Edi Supplier Order relation
    """

    _inherit = 'edi.supplier.order'

    _columns = {
        'line_ids': fields.one2many(
            'edi.supplier.order.line', 'order_id', 'Righe')
    }

