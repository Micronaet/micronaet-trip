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
import treepoem
from report import report_sxw
from report.report_sxw import rml_parse

class Parser(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(Parser, self).__init__(cr, uid, name, context)
        self.localcontext.update({
            'get_objects': self.get_objects,        
            })
            
    def get_objects(self, data):
        ''' Return single or multi label
        '''
        cr = self.cr
        uid = self.uid        
        ids = data.get('pallet_ids', [])
        context = {}

        pallet_pool = self.pool.get('edi.soap.logistic.pallet')
        pallets = pallet_pool.browse(cr, uid, ids, context=context)
        for pallet in pallets:
            fullname = pallet_pool._get_sscc_fullname(
                cr, uid, pallet, context=context)
                
            # Generate image during print (only first time)    
            if not os.path.isfile(fullname):
                image = treepoem.generate_barcode(
                    barcode_type='gs1-128', # One of the BWIPP supported codes.
                    data=pallet_pool.get_sscc_formatted(pallet.sscc),
                    )                 
                image.convert('1').save(fullname)
        return pallets
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
