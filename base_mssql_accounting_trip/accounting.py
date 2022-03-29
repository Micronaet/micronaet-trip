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
import sys
import netsvc
import logging
from openerp.osv import osv, orm, fields
from datetime import datetime, timedelta
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, DATETIME_FORMATS_MAP, float_compare
import openerp.addons.decimal_precision as dp
from openerp.tools.translate import _

_logger = logging.getLogger(__name__)


class micronaet_accounting(osv.osv):
    """ Add extra query for manage trip
    """
    _inherit = "micronaet.accounting"

    # -------------------------------------------------------------------------
    #                             Table access method
    # -------------------------------------------------------------------------
    # -------------------
    #  DESTINATION CODE -
    # -------------------
    def get_destination_code(self, cr, uid, prefix, year=False, context=None):
        """ Access to anagrafic extra table of destinations
            With table: PC_VAWD_DOCUMENTOP
        """
        if self.pool.get('res.company').table_capital_name(cr, uid, context=context):
            table1 = "PA_RUBR_PDC_CLFR"
            table2 = "PC_VAWD_DOCUMENTOP"
        else:
            table1 = "pa_rubr_pdc_clfr"
            table2 = "pc_vawd_documentop"

        cursor = self.connect(cr, uid, year=year, context=context)
        try:
            # All destination with extra code or va code
            cursor.execute("""
                SELECT pa.CKY_CNT, pa.CSG_CODALT, va.CDS_COD__IMPIANTO_
                FROM 
                    %s pa JOIN %s va
                ON (pa.CKY_CNT = va.CKY_CNT) 
                WHERE 
                    pa.CKY_CNT like '%s.%s' and (pa.CSG_CODALT != '' 
                    OR va.CDS_COD__IMPIANTO_ != '');
                """ % (
                    table1, table2, prefix, "%"))
            return cursor
        except:
            print(sys.exc_info())  # False  # Error return nothing
            return False

    def get_destination_tour(self, cr, uid, year=False, context=None):
        """ Access to anagrafic extra table of destinations
            With table: PC_VI02_GIRI
        """
        if self.pool.get('res.company').table_capital_name(cr, uid, context=context):
            table = "PC_VI02_GIRI"
        else:
            table = "pc_vi02_giri"

        cursor = self.connect(cr, uid, year=year, context=context)
        try:
            # All destination with extra code or va code
            # cursor.execute("""
            #    SELECT
            #        CKY_CNT, CDS_PRIMO_GIRO, CDS_SECONDO_GIRO,
            #        CDS_NOTE_CONSEGNA, CDS_CONTROLLO_PAGA
            #    FROM
            #        %s
            #    WHERE
            #        CDS_PRIMO_GIRO != '' OR CDS_SECONDO_GIRO != '' OR
            #        CDS_NOTE_CONSEGNA != '';
            #    """ % table)
            # Use all for clean previous setup
            cursor.execute("""
                SELECT 
                    CKY_CNT, CDS_PRIMO_GIRO, CDS_SECONDO_GIRO, 
                    CDS_NOTE_CONSEGNA, CDS_CONTROLLO_PAGA                
                FROM 
                    %s;
                """ % table)
            return cursor
        except:
            return False  # Error return nothing

    def get_trip_order(self, cr, uid, year=False, context=None):
        """ Trip order for importation
            With table: OC_TESTATE
        """
        if self.pool.get('res.company').table_capital_name(cr, uid, context=context):
            table = "OC_TESTATE"
        else:
            table = "oc_testate"

        cursor = self.connect(cr, uid, year=year, context=context)
        try:
            # All destination with extra code or va code
            cursor.execute("""
                SELECT 
                    CSG_DOC, NGB_SR_DOC, NGL_DOC, DTT_DOC,
                    CKY_CNT_CLFR, CKY_CNT_SPED_ALT, CKY_CNT_AGENTE,
                    CKY_CNT_VETT, CDS_NOTE, NPS_TOT
                FROM 
                    %s;
                """ % table)
            return cursor
        except:
            return False  # Error return nothing
