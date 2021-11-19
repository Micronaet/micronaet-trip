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

    # -------------------------------------------------------------------------
    # File procedure:
    # -------------------------------------------------------------------------
    def save_attachment_from_eml_file(self, cr, uid, ids, context=None):
        """ Try to extract the attachments from all files in company folder
        """
        company_pool = self.pool.get('edi.company')
        company_ids = company_pool.search(cr, uid, [
            ('mail_order_input', '=', True),
        ], context=context)
        for company in company_pool.browse(
                cr, uid, company_ids, context=context):
            folder = {
                'eml': company.mail_eml_folder,
                'history': company.mail_eml_history,
                'attachment': company.mail_attach_folder,
            }
            content_type = company.mail_content_type
            extension = company.attachment_extention
            # os.path.exists(folder) or os.makedirs(folder)

            for root, folders, files in os.walk(folder['eml']):
                for filename in files:
                    if filename.split('.')[-1].lower() != 'eml':
                        _logger.warning('File ignored: %s' % filename)
                        continue
                    attach_filename = '%s.%s' % (
                        filename.split('.')[0],
                        extension,
                    )

                    fullname = os.path.join(
                        root, filename)
                    history_fullname = os.path.join(
                        folder['history'], filename)
                    attach_fullname = os.path.join(
                        folder['attachment'], attach_filename)
                    try:
                        with open(filename, 'r') as eml_f:
                            message = email.message_from_file(eml_f)

                        # Loop on part:
                        for part in message.walk():
                            if part.get_content_type() == content_type:
                                name = part['Content-Disposition']
                                # attachment_id = part['Content-ID']
                                # attachment_format =
                                #     part['Content-Transfer-Encoding']
                                attach_b64 = base64.b64decode(
                                    part.get_payload())
                                with open(attach_fullname, 'wb') as attach_f:
                                    attach_f.write(attach_b64)

                                # Move parsed email in history:
                                shutil.move(fullname, history_fullname)
                                _logger.warning('EML history: %s in %s' % (
                                    fullname, history_fullname))
                                break  # todo Check only first attach
                        else:  # Only if not break
                            _logger.error('No attachment in %s format %s' % (
                                content_type,
                                fullname,
                            ))
                    except:
                        _logger.error('Cannot read: %s' % fullname)
                break  # Only this folder

    # -------------------------------------------------------------------------
    # Download IMAP server procedure:
    # -------------------------------------------------------------------------
    def force_import_email_document(self, cr, uid, ids, context=None):
        """ Force import passed server import all email in object
        """
        mail_pool = self.pool.get('imap.server.mail')

        _logger.info('Start read # %s IMAP server' % (
            len(ids),
            ))

        # Read all server:
        for address in self.browse(cr, uid, ids, context=context):
            server = address.host  # '%s:%s' % (address.host, address.port)
            store_as_file = address.store_as_file
            authorized = [item.strip() for item in
                          address.authorized.split('|')]

            # -----------------------------------------------------------------
            # Read all email:
            # -----------------------------------------------------------------
            if_error = _('Error find imap server: %s' % server)
            try:
                if address.SSL:
                    mail = imaplib.IMAP4_SSL(server)  # SSL
                else:
                    mail = imaplib.IMAP4(server)  # No more used!

                server_mail = address.user
                if_error = _('Error login access user: %s' % server_mail)
                mail.login(server_mail, address.password)

                if_error = _('Error access start folder: %s' % address.folder)
                mail.select(address.folder)
            except:
                raise osv.except_osv(
                    _('IMAP server error:'),
                    if_error,
                    )

            esit, result = mail.search(None, 'ALL')
            tot = 0
            for msg_id in result[0].split():
                tot += 1

                # Read and parse result:
                esit, result = mail.fetch(msg_id, '(RFC822)')
                eml_string = result[0][1]
                message = email.message_from_string(eml_string)
                record = {
                    'To': False,
                    'From': False,
                    'Date': False,
                    'Received': False,
                    'Message-Id': False,
                    'Subject': False,
                    }

                # Populate parameters:
                for (param, value) in message.items():
                    if param in record:
                        record[param] = value
                address_from = record['From']
                address_to = record['To']
                odoo_data = {
                    'to': address_to,
                    'from': address_from,
                    'date': record['Date'],
                    'received': record['Received'],
                    'message_id': record['Message-Id'],
                    'subject': record['Subject'],
                    'state': 'draft',
                    'server_id': address.id,
                    }

                # if server_mail in address_to:
                #    _logger.warning('Jumped server mail is in CCN')
                #    continue

                # is_authorized = False
                # for check_mail in authorized:
                #    if check_mail in address_from:
                #        is_authorized = True
                #        break
                # if not is_authorized:
                #    _logger.warning('Jumped mail not authorized')
                #    continue

                # if not record['Message-Id']:
                #    _logger.warning('No message ID for this email')
                # if not store_as_file:
                #    odoo_data['message'] = message

                # todo not in odoo:
                # mail_id = mail_pool.create(
                #    cr, uid, odoo_data, context=context)

                # -------------------------------------------------------------
                # Write on file:
                # -------------------------------------------------------------
                # if store_as_file:
                fullname = 'prova.xml' # todo mail_pool.get_fullname(cr, uid, mail_id, context=context)
                _logger.info('...Saving %s' % fullname)
                f_eml = open(fullname, 'w')
                f_eml.write(eml_string)
                f_eml.close()

                # TODO manage commit roll back also in email
                mail.store(msg_id, '+FLAGS', '\\Deleted')
                _logger.info('Read mail: To: %s - From: %s - Subject: %s' % (
                    record['To'],
                    record['From'],
                    record['Subject'],
                    ))

            _logger.info('End read IMAP %s [tot msg: %s]' % (
                address.name,
                tot,
                ))

            # -----------------------------------------------------------------
            # Close operations:
            # -----------------------------------------------------------------
            # mail.expunge() # TODO clean trash bin
            mail.close()
            mail.logout()
            _logger.info('End read IMAP server')
            # todo operation with email
        return True

    # -------------------------------------------------------------------------
    # Scheduled operations for all IMAP Server:
    # -------------------------------------------------------------------------
    def schedule_import_email_document(self, cr, uid, context=None):
        """ Import Email from IMAP folder scheduled:
        """
        return self.force_import_email_document(
            cr, uid, False, context=context)

    def parse_address(self, address, subject):
        """ Extract name and email from address
        """
        token = '-'
        if not address:
            return '', ''
        split_value = address.split('<')
        email = split_value[-1].split('>')[0]
        if token in subject:
            name = subject.split(token)[0].strip()
        else:
            name = '<'.join(split_value[:-1]).strip().strip('"').strip()

        return name or email, email


    _columns = {
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

    _columns = {
        'mail_order_input': fields.boolean(
            'Ordini via mail',
            help='Questo provider EDI invia gli ordini via mail'),
        'imap_id': fields.many2one('imap.server', 'Casella IMAP'),
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
            ], 'Content type',
            help='Content type allegato da prendere in considereazione per la'
                 'procedura di import'),
        'attachment_extension': fields.char(
            'Cartella EML', size=6,
            help='Estensione utilizzata per salvare il file allegato'),
    }

    _defaults = {
        'mail_content_type':
            lambda *x: 'application/vnd.openxmlformats-officedocument.'
                       'spreadsheetml.sheet',
        'attachment_extension': lambda *x: 'xlsx',
    }
