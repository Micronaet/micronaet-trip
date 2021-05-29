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
            Period always yesterday to today (launched every day)
        """
        order_pool = self.pool.get('edi.supplier.order')
        line_pool = self.pool.get('edi.supplier.order.line')

        company = self.browse(cr, uid, ids, context=context)[0]
        # Call end point for get order:
        # 20210101 data format
        connection_pool = self.pool.get('http.request.endpoint')
        ctx = context.copy()
        from_date = str(datetime.now() - timedelta(days=1))[:10].replace(
            '-', '')
        to_date = str(datetime.now())[:10].replace('-', '')
        ctx['endpoint_params'] = {
            'from_date': company.force_from_date or from_date,
            'to_date': company.force_to_date or to_date,
        }

        connection_id = company.connection_id.id
        endpoint_id = company.endpoint_id.id
        company_id = company.id

        order_lines = connection_pool.call_endpoint(
            cr, uid, [endpoint_id], context=ctx)

        order_db = {}
        for line in order_lines:
            name = line['NUMERO_ORDINE']
            if name not in order_db:
                order_ids = order_pool.search(cr, uid, [
                    ('company_id', '=', company_id),
                    ('name', '=', name),
                ], context=context)
                if order_ids:
                    order_db[name] = [order_ids[0], []]
                else:
                    data = {
                        'company_id': company_id,
                        'connection_id': connection_id,
                        'endpoint_id': endpoint_id,
                        'name': name,
                        'supplier_code': line['CODICE_PRODUTTORE'],
                        'dealer': line['CONCESSIONARIO'],
                        'dealer_code': line['CODICE_CONCESSIONARIO'],
                        'supplier': line['RAGIONE_SOCIALE_PRODUTTORE'],
                        'order_date': line['DATA_ORDINE'],
                        'deadline_date': line['DATA_CONSEGNA_RICHIESTA'],
                        'note': line['NOTA_ORDINE'],
                    }
                    order_id = order_pool.create(
                        cr, uid, data, context=context)
                    order_db[name] = [order_id, []]
            order_id, lines = order_db[name]
            lines. append({
                'order_id': order_id,

                'sequence': line['RIGA_ORDINE'],
                'name': line['DESCRIZIONE_ARTICOLO'],
                'supplier_name': line['DESCRIZIONE_ARTICOLO_PRODUTTORE'],
                'supplier_code': line['CODICE_ARTICOLO_PRODUTTORE'],
                'code': line['CODICE_ARTICOLO'],
                'uom_supplier': line['UM_ARTICOLO_PRODUTTORE'],
                'uom_product': line['UM_ARTICOLO'],
                'product_qty': line['QTA_ORDINE'],
                # todo change in float
                'order_product_qty': line['QTA_ORDINE_PRODUTTORE'],
                'note': line['NOTA_RIGA'],
            })

        # Update lines:
        for name in order_db:
            order_id, lines = order_db[name]

            # Update order line deleting previous:
            order_pool.write(cr, uid, [order_id], {
                'line_ids': [(6, 0, [])],
            }, context=context)

            for line in lines:
                line_pool.create(cr, uid, line, context=context)
        return True

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

        'edi_supplier_out_path': fields.char(
            'Cartella ordini produttore', size=50,
            help='Cartella dove vengono depositati gli ordini produttore da '
                 'importare nel gestionale'),
        'edi_supplier_in_path': fields.char(
            'Cartella DDT produttore', size=50,
            help='Cartella dove vengono prelevati i DDT del roduttore da '
                 'inviare al portale per copia conforme.'),
    }


class EdiSupplierOrder(orm.Model):
    """ Model name: Edi Supplier Order
    """

    _name = 'edi.supplier.order'
    _description = 'Supplier order'
    _rec_name = 'name'
    _order = 'name'

    def extract_supplier_order(self, cr, uid, ids, context=None):
        """ Estract order to file CSV
        """
        def clean_ascii(value, replace='#'):
            """ Clean not ascii char"""
            value = value or ''
            res = ''
            for c in value:
                if ord(c) < 127:
                    res += value
                else:
                    res += replace
            return res

        order = self.browse(cr, uid, ids, context=context)[0]
        name = order.name
        separator = '|'

        # Read parameter for export:
        company = order.company_id
        out_path = os.path.expanduser(company.edi_supplier_out_path)
        out_filename = os.path.join(out_path, '%s.csv' % name)
        out_f = open(out_filename, 'w')
        header = [
            order.name,
            order.supplier_code,
            clean_ascii(order.dealer),
            order.dealer_code,
            clean_ascii(order.supplier),
            order.order_date,
            order.deadline_date,
            clean_ascii(order.note),
            ]
        header_part = separator.join(header)
        for line in order.line_ids:
            data = [
                line.sequence,
                clean_ascii(line.name),
                clean_ascii(line.supplier_name),
                line.supplier_code,
                line.code,
                line.uom_supplier,
                line.uom_product,
                line.product_qty,
                line.order_product_qty,
                clean_ascii(line.note),
            ]
            # Fixed header
            out_f.write('%s%s%s\r\n' % (
                header_part,
                separator,
                separator.join(data),
            ))
        out_f.close()
        return self.write(cr, uid, ids, {
            'extracted': True,
        }, context=context)

    _columns = {
        'company_id': fields.many2one(
            'edi.company', 'Company'),
        # History parameter:
        'connection_id': fields.many2one(
            'http.request.connection', 'Connessione'),
        'endpoint_id': fields.many2one(
            'http.request.endpoint', 'Endpoint'),

        'name': fields.char('Numero ordine', size=30, required=True),
        'supplier_code': fields.char(
            'Codice produttore', size=30, required=True),
        'dealer': fields.char('Concessionario', size=30),
        'dealer_code': fields.char('Codice Concessionario', size=30),
        'supplier': fields.char('Ragione sociale produttore', size=40),
        'order_date': fields.char('Data ordine', size=20),
        'deadline_date': fields.char('Data consegna richiesta', size=20),
        'note': fields.text('Nota ordine'),
        'extracted': fields.boolean('Estratto'),
    }


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
            'Descrizione articolo', size=90, required=True),
        'supplier_name': fields.char(
            'Descrizione articolo produttore', size=90),
        'supplier_code': fields.char('Codice produttore', size=20),
        'code': fields.char('Codice articolo', size=20),
        'uom_supplier': fields.char('UM fornitore', size=10),
        'uom_product': fields.char('UM prodotto', size=10),
        'product_qty': fields.char('Q.', size=20),  # todo change in float
        'order_product_qty': fields.char('Q.', size=20),
        'note': fields.char('Nota riga', size=40),
        'order_id': fields.many2one('edi.supplier.order', 'Ordine produttore'),
    }


class EdiSupplierOrderRelation(orm.Model):
    """ Model name: Edi Supplier Order relation
    """

    _inherit = 'edi.supplier.order'

    _columns = {
        'line_ids': fields.one2many(
            'edi.supplier.order.line', 'order_id', 'Righe')
    }

