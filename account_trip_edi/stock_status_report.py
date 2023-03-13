#!/usr/bin/python
# -*- coding: utf-8 -*-
###############################################################################
#
# ODOO (ex OpenERP)
# Open Source Management Solution
# Copyright (C) 2001-2015 Micronaet S.r.l. (<https://micronaet.com>)
# Developer: Nicola Riolini @thebrush (<https://it.linkedin.com/in/thebrush>)
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################

import os
import sys
import logging
import locale
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
import pdb

_logger = logging.getLogger(__name__)


class edi_company_report(orm.Model):
    """ Manage more than one importation depend on company
    """
    _inherit = 'edi.company'

    # -------------------------------------------------------------------------
    # OVERRIDE: Collect data for report
    # -------------------------------------------------------------------------
    def update_report_with_company_data(
            self, cr, uid, this_id, report, context=None):
        """ Add data, data_comment, detail from edi_id passed
            Function call from company module to use internal object for
            extract data
        """
        if context is None:
            context = {}

        multiplier = context.get('multiplier', 1.0)
        # Restored to 1 for next data (if not present)
        context['multiplier'] = 1.0

        # todo reset here multiplier in context for next overridden?

        company = self.get_module_company(cr, uid, this_id, context=context)

        if not company:
            return report

        report['title'] += '[%s]' % company.name

        # =====================================================================
        # Data will be create with override:
        # =====================================================================
        this_pool = self.pool.get('edi.company.c%s' % this_id)
        trace = this_pool.trace

        data = report['data']
        data_comment = report['comment']
        detail = report['detail']

        # Append this company data:
        path = os.path.expanduser(company.trip_import_folder)
        for root, folders, files in os.walk(path):
            for filename in files:
                # create or delete mode TODO
                mode = this_pool.get_state_of_file(filename, [])  # No forced
                if mode == 'create':
                    sign = -1  # Note: create order is negative for stock!
                else:
                    _logger.warning('Not used: %s' % filename)
                    continue   # todo complete!!
                    # sign = +1

                fullname = os.path.join(root, filename)
                order_file = open(fullname)
                deadline = False

                # -------------------------------------------------------------
                # Load OC in EDI folder (not in Accounting)
                # -------------------------------------------------------------
                for row in order_file:
                    # Use only data row:
                    if this_pool.is_an_invalid_row(row):
                        continue

                    # Deadline information:
                    if not deadline:
                        deadline = this_pool.format_date(
                            row[trace['deadline'][0]: trace['deadline'][1]])
                        number = row[
                            trace['number'][0]: trace['number'][1]].strip()

                        # Define col position:
                        if deadline < report['min']:
                            col = 0
                        elif deadline > report['max']:
                            col = report['days'] - 1  # Go in last cell
                        else:
                            col = report['header'][deadline]

                    # Extract used data:
                    default_code = row[
                        trace['detail_code'][0]:
                            trace['detail_code'][1]].strip()
                    try:
                        quantity = multiplier * float(row[
                            trace['detail_quantity'][0]:
                                trace['detail_quantity'][1]])
                    except:
                        # Micronaet: remove error 18 gen 2022:
                        _logger.error('Row quantity error: %s' % row)
                        quantity = 0

                    # ---------------------------------------------------------
                    # Report data:
                    # ---------------------------------------------------------
                    if default_code not in data:
                        data[default_code] = report['empty'][:]
                        data_comment[default_code] = report['empty_comment'][:]

                    data[default_code][col] += sign * quantity
                    data_comment[default_code][col] += '[%s: %s] q. %s\n' % (
                        company.name, number, quantity)

                    # Detail data:
                    detail.append([
                        default_code,
                        col,
                        'OC',
                        company.name,
                        filename,
                        number,
                        deadline,
                        quantity,
                        '',
                        ])
                order_file.close()
            break  # No subfolder!
        return report

    # -------------------------------------------------------------------------
    # Utility:
    # -------------------------------------------------------------------------
    def get_product_category(self, default_code):
        """ Auto product category depend on start code
        """
        code = (default_code or 'NON PRESENTE').upper()
        start_1 = code[:1]
        start_2 = code[:2]
        start_3 = code[:3]

        # ---------------------------------------------------------------------
        # 3 char test start:
        # ---------------------------------------------------------------------
        if start_3 == 'SPA':
            return _('Pasta')  # 4

        # ---------------------------------------------------------------------
        # 2 char test start:
        # ---------------------------------------------------------------------
        if start_2 in ('SP', 'SS'):
            return _('Gelo')  # 1

        # ---------------------------------------------------------------------
        # 1 char test start:
        # ---------------------------------------------------------------------
        if start_1 in 'CDFPSV':
            return _('Gelo')  # 1
        elif start_1 in 'BILT':
            return _('Freschi')  # 2
        elif start_1 in 'HO':
            return _('Secchi')  # 3
        elif start_1 in 'G':
            return _('Pasta')  # 4
        else:  # Error list
            return _('Non identificata')  # 5

    def get_module_company(self, cr, uid, module_id, context=None):
        """ Return browse object for company generated with the module
        """
        model_pool = self.pool.get('ir.model.data')

        company = False
        try:
            try:
                reference_id = model_pool.get_object_reference(
                    cr, uid,
                    'account_trip_edi_c%s' % module_id,
                    'importatione_account_trip_edi_c%s' % module_id,
                    )[1]
            except:
                # bug fix for bad XMLID name!
                reference_id = model_pool.get_object_reference(
                    cr, uid,
                    'account_trip_edi_c%s' % module_id,
                    'importation_account_trip_edi_c%s' % module_id,
                    )[1]

            company_ids = self.search(cr, uid, [
                ('type_importation_id', '=', reference_id),
                ], context=context)

            if company_ids:
                company = self.browse(
                    cr, uid, company_ids, context=context)[0]
                if company.__getattr__('import'):
                    _logger.warning('Append data for: #%s' % company.name)
                    return company
                else:
                    _logger.error('Company not active: #%s' % company.name)
        except:
            if company:
                _logger.error('Error get company reference #%s' % company.name)
            else:
                _logger.error('Error get company reference (no company)')
        return False

    # -------------------------------------------------------------------------
    # Collect data for report (overridable)
    # -------------------------------------------------------------------------
    def collect_future_order_data_report(self, cr, uid, context=None):
        """ Overridable procedure for manage the report data collected in all
            company with active EDI company
        """
        if context is None:
            context = {}

        # Read parameters:
        account_days_covered = context.get('account_days_covered', 2)
        report_days = context.get('report_days', 28)
        columns = report_days  # Report Days total columns

        now_dt = datetime.now()
        now = now_dt.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        from_date_dt = now_dt + timedelta(days=account_days_covered)
        to_date_dt = from_date_dt + timedelta(days=report_days)

        report = {
            'days': report_days,

            # -----------------------------------------------------------------
            # Title:
            # -----------------------------------------------------------------
            'title':
                u'Stampa progressivi di magazzino, data: %s - Aziende: ' % now,

            # -----------------------------------------------------------------
            # Header data:
            # -----------------------------------------------------------------
            'header': {
                # Data col: position
                },

            # -----------------------------------------------------------------
            # Sheet data:
            # -----------------------------------------------------------------
            'negative': {
                # Product with negative
                },

            'detail': [
                # Detail line for check problems
                ],

            'data': {
                # Article record: [Q., data, list]
                },

            'comment': {
                # Article record: [Q., data, list]
                },

            'empty': [0.0 for item in range(columns)],
            'empty_comment': ['' for item in range(columns)],

            }

        # Header creation:
        pos = 0
        this_date = False
        for day in range(columns):
            date = from_date_dt + timedelta(days=day)
            this_date = date.strftime('%Y-%m-%d')
            if 'min' not in report:
                report['min'] = this_date
            report['header'][this_date] = pos
            pos += 1
        report['max'] = this_date

        # =====================================================================
        # XXX Data will be create with override:
        # =====================================================================
        return report

    # -------------------------------------------------------------------------
    # Report action:
    # -------------------------------------------------------------------------
    def transform_delta_record(self, start_qty, delta, excel_format):
        """ Transform delta record with quantity record
        """
        def get_heat(excel_format, number):
            """ Return format depend on heat
            """
            import math

            if number > 0:
                mode = 'heat_green'
            else:  # <=0
                number = -number
                mode = 'heat_red'

            if not number:
                position = 0
            else:
                position = int(math.log10(number))
            if position > 4:
                position = 4
            elif position < 0:
                position = 0

            return excel_format[mode][position]

        # Transform in progress total:
        has_negative = False
        for col in range(0, len(delta)):
            if col:
                previous_qty = delta[col - 1][0]
            else: # first line:
                previous_qty = start_qty

            new_qty = delta[col] + previous_qty  # Append previous col
            delta[col] = (new_qty, get_heat(excel_format, new_qty))
            if not has_negative and new_qty <= 0:
                has_negative = True

        # Format cell (not installed on Ubuntu 12.04 server:
        locale.setlocale(locale.LC_ALL, '')  # Default en_US
        for col in range(0, len(delta)):
            delta[col] = (
                locale.format('%0.0f', delta[col][0], grouping=True).replace(
                    ',', '.'),  # XXX not work with Italian setup!
                delta[col][1],
                )
        return has_negative

    def generate_future_order_data_report(self, cr, uid, ids, context=None):
        """ Overridable procedure for manage the report data collected in all
            company with active EDI company
        """
        def clean_header_date(date):
            """ Clean data in italian mode
            """
            date_part = date.split('-')
            return u'%s/%s' % (
                date_part[2],
                date_part[1],
                )

        def clean_not_ascii_char(value):
            """ Clean float from csv file
            """
            value = value or u''
            res = u''
            for c in value:
                if ord(c) < 127:
                    res += c
                else:
                    res += '#'
            return res

        def clean_float(value):
            """ Clean float from csv file
            """
            value = (value or u'')
            if not value:
                return 0.0

            value = value.strip().replace(',', '.')
            return float(value)

        excel_pool = self.pool.get('excel.writer')
        if context is None:
            context = {}

        # ---------------------------------------------------------------------
        # Extract data from EDI provider
        # ---------------------------------------------------------------------
        # Parameters:
        context.update({
            'account_days_covered': 2,
            'report_days': 28,
            })

        _logger.info('Start collect information for EDI stock status report')
        report = self.collect_future_order_data_report(
            cr, uid, context=context)

        # ---------------------------------------------------------------------
        #                Get information from account:
        # ---------------------------------------------------------------------
        separator = ';'

        # Get data from account
        company_pool = self.pool.get('res.company')
        company_ids = company_pool.search(cr, uid, [], context=None)
        company = company_pool.browse(
            cr, uid, company_ids, context=context)[0]
        edi_account_data = company.edi_account_data
        if not edi_account_data:
            raise osv.except_osv(
                _('Errore parametri'),
                _('Manca un parametro nella azienda scheda EDI!'),
                )
        edi_account_data = os.path.expanduser(edi_account_data)
        try:
            stock_status = open(
                os.path.join(edi_account_data, 'stato-mag.gfd'))
            supplier_order = open(
                os.path.join(edi_account_data, 'stato-of.gfd'))
        except:
            raise osv.except_osv(
                _('Errore file di scambio'),
                _('Non si possono leggere i file di scambio cartella: %s!' % (
                    edi_account_data)),
                )

        # ---------------------------------------------------------------------
        # A. Stock status:
        # ---------------------------------------------------------------------
        account_data = {}
        for line in stock_status:
            line = line.strip()
            column = line.split(separator)

            # -----------------------------------------------------------------
            # Field:
            # -----------------------------------------------------------------
            # Description:
            default_code = column[0].strip()
            name = column[1].strip()
            uom = column[2].strip().upper()

            # Quantity:
            inventory_qty = clean_float(column[3])
            load_qty = clean_float(column[4])
            unload_qty = clean_float(column[5])
            oc_e_qty = clean_float(column[6])
            oc_s_qty = clean_float(column[7])
            of_qty = clean_float(column[8])

            moved = any((
                inventory_qty, load_qty, unload_qty, oc_e_qty, oc_s_qty,
                of_qty))

            # Calculated:
            net_qty = inventory_qty + load_qty - unload_qty  # Stock net Q.
            oc_qty = oc_e_qty + oc_s_qty  # XXX OF added in real columns
            available_qty = net_qty - oc_qty

            # -----------------------------------------------------------------
            # Startup data for Account OC present:
            # -----------------------------------------------------------------
            # if oc_qty and default_code not in report['data']:
            if moved and default_code not in report['data']:
                report['data'][default_code] = report['empty'][:]
                report['comment'][default_code] = \
                    report['empty_comment'][:]

            # todo make better:
            # try:  # Clean no ascii char
            #    name = u'{}'.format(name)
            # except:
            clean_name = ''
            for c in name:
                if ord(c) < 127:
                    clean_name += c
                else:
                    clean_name += '[ERR]'

            account_data[default_code] = [
                clean_name,
                uom,

                of_qty,
                net_qty,
                oc_qty,
                available_qty,
                ]

        # ---------------------------------------------------------------------
        # B. Supplier order (update report database)
        # ---------------------------------------------------------------------
        supplier_comment = {}
        for line in supplier_order:
            line = line.strip()
            column = line.split(separator)

            default_code = column[0].strip()[:11]  # XXX Max parent length
            if default_code not in supplier_comment:
                supplier_comment[default_code] = ''

            if default_code not in report['data']:
                _logger.warning(u'No OF product in report: %s' % default_code)
                continue

            of_qty = float((column[3].strip() or u'0').replace(u',', u'.'))
            of_delivery = column[4].strip()
            supplier = column[5].strip()
            number = column[6].strip()
            if of_delivery:
                of_delivery = u'%s-%s-%s' % (
                    of_delivery[:4],
                    of_delivery[4:6],
                    of_delivery[6:8],
                    )

            # Add comment for cell:
            supplier_comment[default_code] += u'[%s: %s (il %s)] q. %s\n' % (
                supplier, number, of_delivery or u'?', of_qty,
                )
            if not of_delivery:
                continue

            # Define col position:
            if of_delivery < report['min']:
                comment = u'Non usato (< min)'
                col = -1
            elif of_delivery > report['max']:
                comment = u'Messo ultima colonna (< max)'
                col = report['days'] - 1  # Go in last cell
            else:
                comment = u'Usato'
                col = report['header'][of_delivery]

            if col >= 0:
                report['data'][default_code][col] += of_qty
                report['comment'][default_code][col] += u'[%s: %s] q. %s' % (
                    supplier,
                    number,
                    of_qty,
                    )

            # todo add detail data?
            report['detail'].append([
                default_code,
                col,
                u'OF',
                supplier,
                u'',
                number,
                of_delivery,
                of_qty,
                comment,
                ])

        # ---------------------------------------------------------------------
        # Read convert customer code
        # ---------------------------------------------------------------------
        code_loop = {
            'Elior': u'/home/openerp/mexal/cella/csv/codelior.csv',
            'Dussmann': u'/home/openerp/mexal/cella/csv/coddussmann.csv',
        }
        cmp_2_cust_code = {}
        for code_company in code_loop:
            cmp_2_cust_code[code_company] = {}
            filename = code_loop[code_company]
            try:
                for line in open(filename, 'r'):
                    row = line.strip().split(';')
                    if len(row) == 2:
                        default_code = u'{}'.format(row[0].strip())
                        customer_code = u'{}'.format(row[1].strip())
                        cmp_2_cust_code[code_company][default_code] = \
                            customer_code
            except:
                _logger.error('Error reading %s, no customer code' % filename)

        # ---------------------------------------------------------------------
        # Excel file:
        # ---------------------------------------------------------------------
        extension = 'xlsx'
        ws_name = _(u'EDI stato magazzino')
        excel_pool.create_worksheet(ws_name, extension=extension)

        # excel_pool.set_format(number_format='0.#0')
        excel_pool.set_format(number_format='0')
        excel_pool.get_format()  # Update workbook

        excel_format = {
            'title': excel_pool.get_format('title'),
            'header': excel_pool.get_format('header'),

            'black': {
                'text': excel_pool.get_format('text'),
                'number': excel_pool.get_format('number'),
                },

            'green': {
                'text': excel_pool.get_format('bg_green'),
                'number': excel_pool.get_format('bg_green_number'),
                },

            'red': {
                'text': excel_pool.get_format('bg_red'),
                'number': excel_pool.get_format('bg_red_number'),
                },

            'heat_red': [
                excel_pool.get_format('bg_red_number_0'),
                excel_pool.get_format('bg_red_number_1'),
                excel_pool.get_format('bg_red_number_2'),
                excel_pool.get_format('bg_red_number_3'),
                excel_pool.get_format('bg_red_number_4'),
                ],

            'heat_green': [
                excel_pool.get_format('bg_green_number_0'),
                excel_pool.get_format('bg_green_number_1'),
                excel_pool.get_format('bg_green_number_2'),
                excel_pool.get_format('bg_green_number_3'),
                excel_pool.get_format('bg_green_number_4'),
                ],
            }

        col_width = [
            6, 8,
            11, 10, 10,
            40, 2, 6, 6, 6, 6
            # todo append date total
            ]
        col_width.extend(
            [6 for item in range(context.get('report_days'))])

        header = [
            # Product:
            u'Stato',
            u'Categoria',
            u'Cod. GFD',
            u'Elior',
            u'Dussmann',
            u'Nome',
            u'UM',

            # Account program:
            u'OF',
            u'Mag.',
            u'OC',
            u'Mag.-OC',

            # Number data:
            ]

        fixed_cols = len(header)
        supplier_col = header.index('OF')
        excel_pool.column_width(ws_name, col_width)

        # ---------------------------------------------------------------------
        # Title:
        # ---------------------------------------------------------------------
        row = 0
        excel_pool.write_xls_line(ws_name, row, (
            report['title'],
            ), excel_format['title'])

        # ---------------------------------------------------------------------
        # Header:
        # ---------------------------------------------------------------------
        row += 2
        excel_pool.write_xls_line(
            ws_name, row, header, excel_format['header'])

        # Integration:
        excel_pool.write_xls_line(ws_name, row, [
            clean_header_date(item) for item in sorted(report['header'].keys())
            ], excel_format['header'], col=fixed_cols)

        excel_pool.autofilter(ws_name, row, 0, row, 3)
        excel_pool.freeze_panes(ws_name, row + 1, 3)  # Lock row

        # ---------------------------------------------------------------------
        # Data
        # ---------------------------------------------------------------------
        black = excel_format['black']
        red = excel_format['red']

        for default_code in sorted(
                report['data'],
                key=lambda c: (
                    self.get_product_category(c),
                    c,
                    )):
            row += 1
            delta = report['data'][default_code]
            try:
                name, uom, of_qty, net_qty, oc_qty, start_qty = \
                    account_data[default_code]
            except:
                name = uom = u''
                of_qty = net_qty = oc_qty = start_qty = 0.0

            has_negative = self.transform_delta_record(
                start_qty, delta, excel_format)
            if has_negative:
                color = red
            else:
                color = black

            excel_pool.write_xls_line(ws_name, row, [
                (u'Neg.' if has_negative else u'Pos.', color['text']),
                (self.get_product_category(default_code), color['text']),
                #(default_code, color['text']),
                (cmp_2_cust_code['Elior'].get(
                    default_code), color['text']),  # Customer ELI code
                (cmp_2_cust_code['Dussmann'].get(
                    default_code), color['text']),  # Customer DUS code
                (name, color['text']),
                uom,
                (of_qty, black['number']),
                (net_qty, black['number']),
                (oc_qty, black['number']),
                (start_qty, black['number']),
                ], black['text'])
            # OF comment:
            if supplier_comment.get(default_code):
                excel_pool.write_comment(
                    ws_name, row, supplier_col, supplier_comment[default_code])

            # Integration:
            excel_pool.write_xls_line(
                ws_name, row, delta, col=fixed_cols)

            # Comment: # todo
            excel_pool.write_comment_line(
                ws_name, row, report['comment'].get(default_code, []),  # todo!
                col=fixed_cols)

        # ---------------------------------------------------------------------
        #                                Detail
        # ---------------------------------------------------------------------
        ws_name = _(u'EDI dettaglio')
        excel_pool.create_worksheet(ws_name, extension=extension)

        col_width = [
            10, 22, 5, 12, 10, 4, 15, 15, 8, 30,
            ]

        header = [
            u'Azienda',
            u'File',
            u'Tipo',
            u'Numero',
            u'Scadenza',
            u'Pos.',
            u'Categoria',
            u'Codice',
            u'Q.',
            u'Commento',
            ]
        excel_pool.column_width(ws_name, col_width)

        # ---------------------------------------------------------------------
        # Title:
        # ---------------------------------------------------------------------
        row = 0
        excel_pool.write_xls_line(ws_name, row, (
            u'Dettaglio report',
            ), excel_format['title'])

        # ---------------------------------------------------------------------
        # Header:
        # ---------------------------------------------------------------------
        row += 2
        excel_pool.write_xls_line(
            ws_name, row, header, excel_format['header'])
        excel_pool.autofilter(ws_name, row, 0, row, len(header)-1)
        excel_pool.freeze_panes(ws_name, row + 1, 0)  # Lock row

        # ---------------------------------------------------------------------
        # Data
        # ---------------------------------------------------------------------
        for line in sorted(report['detail']):
            row += 1
            (code, position, mode, company, filename, order, deadline, q,
                comment) = line
            if mode == 'OF':
                sign = 1
            else:
                sign = -1

            data = [
                company,
                filename,

                mode,
                order,
                deadline,
                (position, black['number']),
                self.get_product_category(code),
                clean_not_ascii_char(code),
                (sign * q, black['number']),
                comment,
                ]
            excel_pool.write_xls_line(ws_name, row, data, black['text'])
        return excel_pool.return_attachment(
            cr, uid, ws_name,
            name_of_file=u'future_stock_status.xls', version='7.0',
            php=True, context=context)
