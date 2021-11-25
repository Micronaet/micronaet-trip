# -*- coding: utf-8 -*-
###############################################################################
#
#    Copyright (C) 2001-2014 Micronaet SRL (<http://www.micronaet.it>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
import os
import pdb
import re
import sys
import logging
import imaplib
import email
import shutil
import base64
from openerp.osv import fields, osv, expression, orm
from datetime import datetime, timedelta
from openerp.tools.translate import _
from openerp.tools import (
    DEFAULT_SERVER_DATE_FORMAT,
    DEFAULT_SERVER_DATETIME_FORMAT,
    DATETIME_FORMATS_MAP,
    float_compare)

_logger = logging.getLogger(__name__)


class ImapServer(orm.Model):
    """ Model name: EDI IMAP
    """
    _name = 'imap.server'
    _description = 'IMAP Server'
    _order = 'name'

    # Utility:
    def parse_uid(self, data):
        pattern_uid = re.compile(r'\d+ \(UID (?P<uid>\d+)\)')
        match = pattern_uid.match(data)
        return match.group('uid')

    # -------------------------------------------------------------------------
    # File procedure:
    # -------------------------------------------------------------------------
    def save_attachment_from_eml_file(self, company, data):
        """ Try to extract the attachments from all files in company folder
            Extract single file and move same time the email
        """
        folder = {
            # 'eml': os.path.expanduser(company.mail_eml_folder),
            'attachment': os.path.expanduser(company.mail_attach_folder),
            'history': os.path.expanduser(company.mail_attach_history),
        }
        content_type = company.mail_content_type
        extension = company.attachment_extension
        utility = self.pool.get(company.type_importation_id.object)  # xxx
        pdb.set_trace()
        for imap, msg_uid, record in data:
            order_name = utility.get_order_number(record)

            # Attachment file:
            attach_filename = '%s.%s' % (order_name, extension)
            attach_fullname = os.path.join(
                folder['attachment'], attach_filename)

            # Loop on part:
            message = record['Message']
            for part in message.walk():
                # Check if is the correct attachement:
                if utility.is_order_attachment(
                        part, content_type, attach_filename):
                    # ---------------------------------------------------------
                    # Save Attachment: todo 'Content-Transfer-Encoding' base64
                    # ---------------------------------------------------------
                    attach_b64 = base64.b64decode(part.get_payload())
                    with open(attach_fullname, 'wb') as attach_f:
                        attach_f.write(attach_b64)

                    # ---------------------------------------------------------
                    # IMAP operations:
                    # ---------------------------------------------------------
                    # todo check if could be a problem keep this code after ^^
                    # Move in archive parsed email:
                    result_operation = imap.uid('COPY', msg_uid, 'Archive')

                    # Delete from INBOX:
                    if result_operation[0] == 'OK':  # always moved!
                        mov, data = imap.uid('STORE', msg_uid, '+FLAGS',
                                             r'(\Deleted)')
                        # imap.store(msg_uid, '+FLAGS', '(\Deleted)')
                    break  # Check only first attachment

            else:  # Only if not break for attachment fount:
                _logger.error('No attachment in %s format %s' % (
                    content_type,
                    attach_fullname,
                ))

    # -------------------------------------------------------------------------
    # Download IMAP server procedure:
    # -------------------------------------------------------------------------
    def force_import_email_document(self, cr, uid, ids, context=None):
        """ Force import passed server import all email in object
        """
        company_pool = self.pool.get('edi.company')

        _logger.info('Start read IMAP server')

        # Read all server active:
        address_ids = self.search(cr, uid, [
            ('is_active', '=', True),
        ], context=context)

        company_records = {}
        for address in self.browse(cr, uid, address_ids, context=context):
            company_ids = company_pool.search(cr, uid, [
                ('import', '=', True),  # Only active company
                ('imap_id', '=', address.id),  # For this active IMAP
            ], context=context)
            if not company_ids:
                _logger.error(
                    'IMAP %s not associated to EDI company!' % address.name)
                continue

            # Collect list of company touched for utility part:
            for company in company_pool.browse(
                    cr, uid, company_ids, context=context):
                if company not in company_records:
                    company_records[company] = []

            # -----------------------------------------------------------------
            #                   Connect IMAP server:
            # -----------------------------------------------------------------
            server = address.host  # '%s:%s' % (address.host, address.port)
            if_error = _('Error find imap server: %s' % server)
            try:
                if address.SSL:
                    imap = imaplib.IMAP4_SSL(server)  # SSL
                else:
                    imap = imaplib.IMAP4(server)  # No more used!

                server_mail = address.user
                if_error = _('Error login access user: %s' % server_mail)
                imap.login(server_mail, address.password)

                if_error = _('Error access start folder: %s' % address.folder)
                imap.select(address.folder)
            except:
                raise osv.except_osv(
                    _('IMAP server error:'),
                    if_error,
                    )

            # -----------------------------------------------------------------
            # Read all email:
            # -----------------------------------------------------------------
            esit, result = imap.search(None, 'ALL')
            tot = 0
            email_ids = result[0].split()
            _logger.info('Found %s mail in %s folder' % (
                len(email_ids), address.folder))
            for msg_id in email_ids:
                tot += 1

                # Parse message in record dict for common field used:
                esit, result_mail = imap.fetch(msg_id, '(RFC822)')
                eml_string = result_mail[0][1]

                message = email.message_from_string(eml_string)
                record = {
                    'To': False,
                    'From': False,
                    'Date': False,
                    'Received': False,
                    'Message-Id': False,
                    'Subject': False,
                    'Message': message,
                    }

                # Populate parameters:
                for (param, value) in message.items():
                    if param in record:
                        record[param] = value

                # todo if not record['Message-Id']:
                for company in company_records:
                    if not company_pool.email_belong_to(company, record):
                        # todo archive unused files
                        continue  # Mail not belong to this company

                    # ---------------------------------------------------------
                    # Save for archive and delete after:
                    # ---------------------------------------------------------
                    resp, uid_data = imap.fetch(msg_id, '(UID)')
                    msg_uid = self.parse_uid(uid_data[0])
                    company_records[company].append((
                        # IMAP operation:
                        imap,  # Logged imap mail
                        msg_uid,

                        # File operation:
                        record,
                    ))

                _logger.info('Read mail: To: %s - From: %s - Subject: %s' % (
                    record['To'], record['From'], record['Subject']))

            _logger.info('End read IMAP %s [tot msg: %s]' % (
                address.name,
                tot,
                ))

            pdb.set_trace()
            _logger.info('Parse attachment mail read')
            for company in company_records:
                self.save_attachment_from_eml_file(
                    company, company_records[company])

            # -----------------------------------------------------------------
            # Close operations:
            # -----------------------------------------------------------------
            # todo close all
            # _logger.info('End read IMAP server %s' % imap)
            # imap.expunge()  # Clean trash bin
            # imap.close()
            # imap.logout()
        return True

    # -------------------------------------------------------------------------
    # Scheduled operations for all IMAP Server:
    # -------------------------------------------------------------------------
    def schedule_import_email_document(self, cr, uid, context=None):
        """ Import Email from IMAP folder scheduled:
        """
        return self.force_import_email_document(
            cr, uid, False, context=context)

    def get_email_address(self, email):
        """ Extract name and email from address
        """
        if not email:
            return ''
        split_value = email.split('<')
        return split_value[-1].split('>')[0]

    _columns = {
        'is_active': fields.boolean('Attiva'),
        'name': fields.char('Email', size=80, required=True),
        'host': fields.char(
            'IMAP server', size=64, help='Email IMAP server', required=True),
        'port': fields.integer('Port', required=True),
        'user': fields.char(
            'Username', size=64, help='Email user', required=True),
        'password': fields.char(
            'Password', size=64, help='Email password', required=True),
        'folder': fields.char(
            'Folder', size=64, help='Email IMAP folder'),
        'SSL': fields.boolean('SSL'),
        'remove': fields.boolean('Remove after import'),
        'comment': fields.text('Note'),
        }

    _defaults = {
        'port': lambda *a: 993,
        'SSL': lambda *a: True,
        'folder': lambda *a: 'INBOX',
        }


class EdiCompany(orm.Model):
    """ EDI Company extend for manage email EDI input source
    """
    _inherit = 'edi.company'

    # -------------------------------------------------------------------------
    # Utility:
    # -------------------------------------------------------------------------
    def email_belong_to(self, company, record):
        """ Check if email belong to this company
        """
        imap_pool = self.pool.get('imap.server')
        email = imap_pool.get_email_address(record['From'])

        if not email.endswith(company.mail_from):  # Check final part of addr.
            return False

        if not record['Subject'] or not \
                record['Subject'].startswith(company.mail_subject):
            return False
        return True

    _columns = {
        'mail_order_input': fields.boolean(
            'Ordini via mail',
            help='Questo provider EDI invia gli ordini via mail'),
        'imap_id': fields.many2one('imap.server', 'Casella IMAP'),
        'mail_from': fields.char(
            'Mittente', size=50,
            help='Indica da quale indirizzo viene ricevuta la mail'),
        'mail_subject': fields.char(
            'Iniziale oggetto', size=50,
            help='Indicare la parte iniziale dell\'oggetto'),
        'mail_eml_folder': fields.char(
            'Cartella EML', size=80,
            help='Cartella dove vengono esporate le mail scaricate dalla '
                 'casella IMAP'),
        'mail_eml_history': fields.char(
            'Cartella EML storico', size=80,
            help='Cartella dove vengono spostate le mail appena viene '
                 'estratto il documento allegato'),
        'mail_attach_folder': fields.char(
            'Cartella Allegati', size=80,
            help='Cartella dove salvati gli allegati estrapolati dalle email'),
        'mail_attach_history': fields.char(
            'Cartella Allegati storica', size=80,
            help='Cartella dove vengono spostati gli allegati convertiti per'
                 'il gestionale'),
        'mail_content_type': fields.selection([
            ('application/vnd.openxmlformats-officedocument.'
             'spreadsheetml.sheet', 'File XLSX'),
            ('application/octet-stream', 'Octect stream'),
            ], 'Content type',
            help='Content type allegato da prendere in considereazione per la'
                 'procedura di import'),
        'attachment_extension': fields.char(
            'Estensione allegato', size=6,
            help='Estensione utilizzata per salvare il file allegato'),
    }

    _defaults = {
        'mail_content_type':
            lambda *x: 'application/vnd.openxmlformats-officedocument.'
                       'spreadsheetml.sheet',
        'attachment_extension': lambda *x: 'xlsx',
    }
