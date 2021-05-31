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
import shutil
import logging
from openerp.osv import fields, osv, expression, orm
from datetime import datetime, timedelta
from openerp.tools.translate import _
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT,
    DEFAULT_SERVER_DATETIME_FORMAT,
    DATETIME_FORMATS_MAP,
    float_compare)

_logger = logging.getLogger(__name__)


class EdiPlatformProduct(orm.Model):
    """ Model name: Edi platform product
    """

    _name = 'edi.platform.product'
    _description = 'Platform product'
    _rec_name = 'product_id'
    _order = 'product_id'

    def platform_product_detail(self, cr, uid, ids, context=None):
        """ Open detailed product (for lot)
        """
        model_pool = self.pool.get('ir.model.data')
        view_id = model_pool.get_object_reference(
            cr, uid,
            'account_trip_edi_platform', 'view_edi_company_platform_object_form')[1]

        return {
            'type': 'ir.actions.act_window',
            'name': _('Dettaglio prodotto piattaforma'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': ids[0],
            'res_model': 'edi.platform.product',
            'view_id': view_id,
            'views': [(view_id, 'form')],
            'domain': [],
            'context': context,
            'target': 'new',
            'nodestroy': False,
            }

    _columns = {
        'not_used': fields.boolean('Non usato'),
        'company_id': fields.many2one('edi.company', 'Company'),
        'product_id': fields.many2one('product.product', 'Product'),
        # 'code': fields.char('Codice articolo', size=20),

        'supplier_name': fields.char('Descrizione cliente', size=90),
        'supplier_code': fields.char('Codice cliente', size=20),
        'uom_supplier': fields.char('UM fornitore', size=10),
    }


class EdiCompany(orm.Model):
    """ Model name: Edi Company
    """
    _inherit = 'edi.company'

    # Button events:
    def update_stock_status(self, cr, uid, ids, context=None):
        """ Send stock status from Account + not imported order
        """
        endpoint_pool = self.pool.get('http.request.endpoint')
        # Date now:
        endpoint_params = {
            'date': datetime.now().strftime('%Y%m%d')
        }

        payload = []
        # Loop on all platform product:
        products = []  # todo list of platform product
        for product in products:
            payload.append({
                'CODICE_PRODUTTORE': 'ITAXXXX',
                'CODICE_ARTICOLO': 'AV040002',
                'UM_ARTICOLO ': 'KG',
                'DATA_SCADENZA': '20210705',  # (FORMATO AAAAMMGG),
                'LOTTO': 'XXXX',
                'QTA': '00000000027000',  # 10 + 4
                })

        company = self.browse(cr, uid, ids, context=context)[0]
        ctx = context.copy()
        ctx['endpoint_params'] = endpoint_params
        ctx['payload'] = payload
        reply = endpoint_pool.call_endpoint(cr, uid, [
            company.endpoint_stock_id.id], context=ctx)

        # Check reply:
        sent_message = ''
        sent_error = False
        if 'ElencoErroriAvvisi' in reply:
            for status in reply['ElencoErroriAvvisi']:
                message_type = status['Tipo']
                if message_type and status['Tipo'] in 'CE':
                    sent_error = True
                sent_message += '[%s] %s' % (
                    message_type,
                    status['Messaggio'],
                )

        # TODO add log data for last sent:
        data = {
            # 'sent_message': sent_message,
            # 'sent_error': sent_error,
        }
        if message_type == 'N':  # todo A is needed?
            data['last_sent'] = str(datetime.now())[:19]
        # self.write(cr, uid, [company.id], data, context=context)

        return True

    def export_all_supplier_order(self, cr, uid, ids, context=None):
        """ Export all order not exported
        """
        order_pool = self.pool.get('edi.supplier.order')
        order_ids = order_pool.search(cr, uid, [
            ('extracted', '=', False),
        ], context=context)
        if not order_ids:
            raise osv.except_osv(
                _('Attenzione:'),
                _('Non sono presenti ordini da estrarre'),
                )
        return order_pool.extract_supplier_order(
            cr, uid, order_ids, context=context)

    def import_all_supplier_order(self, cr, uid, ids, context=None):
        """ Import DDT from account
        """
        order_pool = self.pool.get('edi.supplier.order')
        ddt_line_pool = self.pool.get('edi.supplier.order.ddt.line')

        company = self.browse(cr, uid, ids, context=context)[0]
        company_id = company.id
        # separator = company.separator or '|'
        ddt_path = os.path.expanduser(company.edi_supplier_in_path)
        history_path = os.path.join(ddt_path, 'history')
        unused_path = os.path.join(ddt_path, 'unused')
        # log_path = os.path.join(ddt_path, 'log')  # todo log events!
        _logger.info('Start check DDT files: %s' % ddt_path)
        send_order_ids = []  # Order to be sent afters
        for root, folders, files in os.walk(ddt_path):
            for filename in files:
                ddt_filename = os.path.join(root, filename)
                if not filename.endswith('.csv'):
                    _logger.warning('Jumped file (unused): %s' % filename)
                    shutil.move(
                        ddt_filename,
                        os.path.join(unused_path, filename)
                    )
                    continue

                # todo Check if is a DDT for Portal
                ddt_f = open(ddt_filename, 'r')
                fixed = {  # Fixed data
                    # ID ODOO
                    1: '',  # Order name
                    2: '',  # DDT Number
                    3: '',  # DDT Date
                    4: '',  # DDT Received
                }

                row = 0
                order_id = False
                for line in ddt_f.readline():
                    line = line.strip()
                    row += 1
                    if row in fixed:
                        fixed[row] = line
                        if row == 1:
                            # Check if it is a platform file
                            order_ids = order_pool.search(cr, uid, [
                                ('company_id', '=', company_id),
                                ('name', '=', line),
                            ])

                            if not order_ids:
                                # todo remove file when imported?
                                _logger.error(
                                    'Order %s not in platform, '
                                    'File %s jumped' % (line, filename),
                                    )
                            order_id = False
                        continue
                    # todo check with Laura:
                    sequence = line[:5]
                    code = line[5:10]
                    product_uom = line[20:30]
                    deadline_lot = line[20:30]
                    lot = line[20:30]
                    product_qty = line[10:20]

                    # Order to be sent after:
                    if order_id not in send_order_ids:
                        send_order_ids.append(order_id)

                    # Link to line:
                    line_ids = order_pool.search(cr, uid, [
                        ('order_id', '=', order_id),
                        ('sequence', '=', sequence),
                    ])
                    if line_ids:
                        line_id = line_ids[0]
                    else:
                        line_id = False  # todo consider raise error!
                        _logger.error(
                            'Cannot link to generator line [%s]!' %
                            sequence)

                    ddt_data = {
                        'sequence': sequence,
                        'name': fixed[2],
                        'code': code,
                        'uom_product': product_uom,
                        'product_qty': product_qty,  # todo change in float
                        'lot': lot,
                        'deadline_lot': deadline_lot,

                        'order_id': order_id,
                        'line_id': line_id,
                    }
                    ddt_line_pool.create(cr, uid, ddt_data, context=context)
                    _logger.warning('History used file: %s' % filename)
                    shutil.move(
                        ddt_filename,
                        os.path.join(history_path, filename),
                    )
                break  # Only first folder!
        return order_pool.send_ddt_order(
            cr, uid, send_order_ids, context=context)

    def import_platform_supplier_order(self, cr, uid, ids, context=None):
        """ Import supplier order from platform
            Period always yesterday to today (launched every day)
        """
        order_pool = self.pool.get('edi.supplier.order')
        line_pool = self.pool.get('edi.supplier.order.line')
        product_pool = self.pool.get('edi.platform.product')

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
            supplier_code = line['CODICE_ARTICOLO_PRODUTTORE']
            supplier_name = line['DESCRIZIONE_ARTICOLO_PRODUTTORE']
            uom_supplier = line['UM_ARTICOLO_PRODUTTORE']
            lines. append({
                'order_id': order_id,

                'sequence': line['RIGA_ORDINE'],
                'name': line['DESCRIZIONE_ARTICOLO'],
                'supplier_name': supplier_name,
                'supplier_code': supplier_code,
                'code': line['CODICE_ARTICOLO'],
                'uom_supplier': uom_supplier,
                'uom_product': line['UM_ARTICOLO'],
                'product_qty': line['QTA_ORDINE'],
                # todo change in float
                'order_product_qty': line['QTA_ORDINE_PRODUTTORE'],
                'note': line['NOTA_RIGA'],
            })
            # Update also platform product
            platform_product_ids = product_pool.search(cr, uid, [
                ('company_id', '=', company_id),
                ('supplier_code', '=', supplier_code),
            ], context=context)
            if not platform_product_ids:
                _logger.info('Create plaform product: %s' % supplier_code)
                product_pool.create(cr, uid, {
                    'company_id': company_id,
                    # 'product_id': False,
                    'supplier_code': supplier_code,
                    'supplier_name': supplier_name,
                    'uom_supplier': uom_supplier,
                }, context=context)

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
        'separator': fields.char('Separatore CSV', size=1),
        'connection_id': fields.many2one(
            'http.request.connection', 'Connection'),
        'endpoint_id': fields.many2one('http.request.endpoint', 'Endpoint OF'),
        'endpoint_ddt_id': fields.many2one(
            'http.request.endpoint', 'Endpoint DDT'),
        'endpoint_stock_id': fields.many2one(
            'http.request.endpoint', 'Endpoint Stato magazzino'),
        'last_stock_update': fields.datetime('Ultimo inviato'),
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
        'platform_product_ids': fields.one2many('edi.platform.product', 'company_id', 'Product'),
    }


class EdiSupplierOrder(orm.Model):
    """ Model name: Edi Supplier Order
    """

    _name = 'edi.supplier.order'
    _description = 'Supplier order'
    _rec_name = 'name'
    _order = 'name'

    def send_ddt_order(self, cr, uid, ids, context=None):
        """ Send JSON data file to portal for DDT confirmed
        """
        endpoint_pool = self.pool.get('http.request.endpoint')
        for order in self.browse(cr, uid, ids, context=context):
            name = order.name
            company = order.company_id
            if not order.ddt_line_ids:
                _logger.error('%s Nothing to send (no DDT lines)!' % name)
                continue
            payload = []
            for ddt_line in order.ddt_line_ids:
                order = ddt_line.order_id
                payload.append({
                    'RIGA_ORDINE': ddt_line.sequence,
                    'NUMERO_DDT': ddt_line.name,
                    'CODICE_ARTICOLO': ddt_line.code,  # 'AV040002'
                    'UM_ARTICOLO_PIATTAFORMA': ddt_line.uom_product,
                    'QTA': ddt_line.product_qty,  # todo 10 + 4
                    'DATA_SCADENZA': ddt_line.deadline_lot,
                    'LOTTO': ddt_line.lot,

                    'CODICE_PRODUTTORE': order.supplier_code,  # '2288'
                    'DATA_DDT': ddt_line.date,  # (FORMATO AAAAMMGG)
                    'DATA_ENTRATA_MERCE': ddt_line.date_received,
                    'NUMERO_ORDINE': order.name,
                })

            ctx = context.copy()
            ctx['payload'] = payload
            reply = endpoint_pool.call_endpoint(cr, uid, [
                company.endpoint_ddt_id.id], context=ctx)

            _logger.warning('Reply: %s' % (reply, ))
            if not reply:
                raise osv.except_osv(
                    _('Attenzione:'),
                    _('Errore spedendo il DDT:\n %s' % reply),
                )
            # todo check error
            sent_message = ''
            sent_error = False
            if 'ElencoErroriAvvisi' in reply:
                for status in reply['ElencoErroriAvvisi']:
                    message_type = status['Tipo']
                    if message_type and status['Tipo'] in 'CE':
                        sent_error = True
                    sent_message += '[%s] %s' % (
                        message_type,
                        status['Messaggio'],
                    )

            if message_type == 'N':  # todo A is needed?
                sent = True
            else:
                sent = False
            self.write(cr, uid, [order.id], {
                'sent': sent,
                'sent_message': sent_message,
                'sent_error': sent_error,
            }, context=context)

            # C=Errore critico, E = Errore generico, A = Avviso, N = Nota)
            return True

    def extract_supplier_order(self, cr, uid, ids, context=None):
        """ Extract order to file CSV
        """
        def clean_ascii(value, replace='#'):
            """ Clean not ascii char"""
            value = value or ''
            res = ''
            for c in value:
                if ord(c) < 127:
                    res += c
                else:
                    res += replace
            return res

        for order in self.browse(cr, uid, ids, context=context):
            name = order.name
            if order.extracted:
                _logger.error('Order %s yet extracted, jump' % name)
                continue

            # Read parameter for export:
            company = order.company_id
            separator = company.separator or '|'
            out_path = os.path.expanduser(company.edi_supplier_out_path)
            out_filename = os.path.join(out_path, '%s.csv' % name)
            out_f = open(out_filename, 'w')
            header = [
                'ODOO' % order.id,
                order.name,  # Order number
                clean_ascii(order.supplier_code),  # ITA0000
                # clean_ascii(order.dealer),
                # clean_ascii(order.dealer_code),
                # clean_ascii(order.supplier),
                clean_ascii(order.order_date),
                clean_ascii(order.deadline_date),
                clean_ascii(order.note),
                ]
            header_part = separator.join(header)
            for line in order.line_ids:
                data = [
                    clean_ascii(line.sequence),
                    # clean_ascii(line.name),
                    # clean_ascii(line.supplier_name),
                    # clean_ascii(line.supplier_code),
                    clean_ascii(line.code),  # AV000
                    # clean_ascii(line.uom_supplier),
                    # clean_ascii(line.uom_product),
                    clean_ascii(line.product_qty),  # 12345678901234 (10+4)
                    # clean_ascii(line.order_product_qty),  todo correct?
                    clean_ascii(line.note),
                ]
                # Fixed header
                out_f.write('%s%s%s\r\n' % (
                    header_part,
                    separator,
                    separator.join(data),
                ))
            out_f.close()
            self.write(cr, uid, ids, {
                'extracted': True,
            }, context=context)
        return True

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

        # Sent to Account:
        'extracted': fields.boolean(
            'Estratto',
            help='Estratto per essere importato nel gestionale',
        ),

        # Sent to portal:
        'sent': fields.boolean(
            'Inviato',
            help='Inviato tramite il portale per conferma consegna'),
        'sent_message': fields.text('Esito invio al portale'),
        'sent_error': fields.text('Stato errore'),
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


class EdiSupplierOrderDDTLine(orm.Model):
    """ Model name: Edi Supplier Order DDT Line
    """

    _name = 'edi.supplier.order.ddt.line'
    _description = 'Supplier order DDT line'
    _rec_name = 'name'
    _order = 'sequence'

    _columns = {
        'sequence': fields.char('Seq.', size=4),
        'name': fields.char(
            'Numero DDT', size=20, required=True),
        'date': fields.char('Data DDT', size=20),
        'date_received': fields.char('Data ricezione', size=20),
        'code': fields.char('Codice articolo', size=20),
        'lot': fields.char('Lotto', size=20),
        'deadline_lot': fields.char('Scadenza Lotto', size=20),
        'uom_product': fields.char('UM prodotto', size=10),
        'product_qty': fields.char('Q.', size=20),  # todo change in float

        'order_id': fields.many2one('edi.supplier.order', 'Ordine produttore'),
        'line_id': fields.many2one('edi.supplier.order.line', 'Riga ordine'),
        'sent': fields.boolean('Riga Inviata'),  # todo not used for now
    }


class EdiSupplierOrderRelation(orm.Model):
    """ Model name: Edi Supplier Order relation
    """

    _inherit = 'edi.supplier.order'

    _columns = {
        'line_ids': fields.one2many(
            'edi.supplier.order.line', 'order_id', 'Righe OF'),
        'ddt_line_ids': fields.one2many(
            'edi.supplier.order.ddt.line', 'order_id', 'Righe DDT'),
    }
