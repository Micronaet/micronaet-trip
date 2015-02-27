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

{
    'name': 'Account Trip Manage',
    'version': '0.1',
    'category': '',
    'description': """
        Manage trip for account order
        """,
    'author': 'Micronaet S.r.l. - Nicola Riolini',
    'website': 'http://www.micronaet.it',
    'license': 'AGPL-3',
    'depends': [
        'base',
        'sql_partner',
        'sql_product',
        'web_m2x_options',

        'report_aeroo',
        'report_aeroo_ooo',
        ],
    'init_xml': [],
    'demo': [],
    'data': [
        'security/trip_group.xml',
        'security/ir.model.access.csv',
        
        'wizard/change_trip_view.xml',

        'trip_view.xml',        
        'scheduler.xml',
        'menuitem_view.xml',
        
        'report/trip_report.xml',

        'wizard/view_trip_wizard.xml',
        'wizard/multi_print_view.xml',
        ],
    'active': False,
    'installable': True,
    'auto_install': False,
    }
