# -*- coding: utf-8 -*-
###############################################################################
#
# ODOO (ex OpenERP)
# Open Source Management Solution
# Copyright (C) 2001-2015 Micronaet S.r.l. (<http://www.micronaet.it>)
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
import erppeek
from datetime import datetime, timedelta
import ConfigParser
import pdb

# -----------------------------------------------------------------------------
# Read configuration parameter:
# -----------------------------------------------------------------------------
# From config file:
cfg_file = os.path.expanduser('./company.cfg')

config = ConfigParser.ConfigParser()
config.read([cfg_file])
dbname = config.get('dbaccess', 'dbname')
user = config.get('dbaccess', 'user')
pwd = config.get('dbaccess', 'pwd')
server = config.get('dbaccess', 'server')
port = config.get('dbaccess', 'port')   # verify if it's necessary: getint

# -----------------------------------------------------------------------------
# Connect to ODOO:
# -----------------------------------------------------------------------------
odoo = erppeek.Client(
    'http://%s:%s' % (
        server, port),
    db=dbname,
    user=user,
    password=pwd,
    )

# Pool used:
company_pool = odoo.model('edi.company')

connection_pool = odoo.model('http.request.connection')
company_ids = company_pool.search([
    ('connection_id', '!=', False),
])

# Update date period:
from_date = str(datetime.now() - timedelta(days=3))[:10].replace('-', '')
to_date = str(datetime.now())[:10].replace('-', '')

company_pool.write(company_ids, {
    'force_from_date': from_date,
    'force_to_date': to_date,
})
pdb.set_trace()
for company in company_pool.browse(company_ids):
    # Call import OF order:
    company_pool.import_platform_supplier_order([company.id])
    company_pool.export_all_supplier_order([company.id])
