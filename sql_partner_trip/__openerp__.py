# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    $Id$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

{
    'name': 'SQL Partner trip',
    'version': '0.0.1',
    'category': 'Generic Modules/ETL',
    'description': """
        Import partner from external DB in MS SQL server or MySQL
            Add extra utility for manage trip informations
            like destination supplier code importation
        """,
    'author': 'Micronaet s.r.l.',
    'website': 'http://www.micronaet.it',
    'depends': [
        'base',
        'sql_partner',
        ],
    'init_xml': [], 
    'data': [
        'scheduler.xml',
        ],
    'demo_xml': [],
    'active': False, 
    'installable': True, 
    }
