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
    'name': 'Account trip - EDI order import procedure for Company 8',
    'version': '0.1',
    'category': 'EDI',
    'description': """
        Import function for load EDI files
        this is a model of importation for Company 8
        This type of module are linked to edi.company for parametrize
        function for importation.
        Import procedure is in account_trip_edi 
        """,
    'author': 'Micronaet S.r.l. - Nicola Riolini',
    'website': 'http://www.micronaet.it',
    'license': 'AGPL-3',
    'depends': [
        'base',
        'account_trip_edi',
        ],
    'init_xml': [],
    'demo': [],
    'data': [
        'security/ir.model.access.csv',
        'data/edi_company_importation.xml'
        ],
    'active': False,
    'installable': True,
    'auto_install': False,
    }