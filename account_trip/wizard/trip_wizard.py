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
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, DATETIME_FORMATS_MAP, float_compare)
import openerp.addons.decimal_precision as dp
from openerp.tools.translate import _


_logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
#                          Generic function
# -----------------------------------------------------------------------------
def return_view(self, cr, uid, res_id, view_name, object_name):
    ''' Function that return dict action for next step of the wizard
    '''
    if not view_name: 
        return {'type':'ir.actions.act_window_close'}

    view_element = view_name.split(".")
    views = []
    
    if len(view_element) != 2: 
        return  {'type':'ir.actions.act_window_close'}

    model_id = self.pool.get('ir.model.data').search(
        cr, uid, [
            ('model','=','ir.ui.view'), 
            ('module','=',view_element[0]), 
            ('name', '=', view_element[1])
            ])
    if model_id:
        view_id=self.pool.get('ir.model.data').read(
            cr, uid, model_id)[0]['res_id']
        views = [(view_id, 'form'), (False, 'tree')]

    return {
        'view_type': 'form',
        'view_mode': 'form,tree',
        'res_model': object_name, # object linked to the view
        'views': views,
        'domain': [('id', 'in', res_id)],  # TODO problem return in tree
        'type': 'ir.actions.act_window',
        #'target': 'new',
        'res_id': res_id, 
        } 

# -----------------------------------------------------------------------------
#                                   Wizard
# -----------------------------------------------------------------------------
class trip_trip_create_wizard(osv.osv_memory):
    ''' Wizard for create trip.trip from selected orders
    '''
    _name = "trip.trip.create.wizard"
                  
    # -------------                           
    # Button event:
    # -------------                           
    def action_create_trip(self, cr, uid, ids, context=None):
        ''' Create a trip and assign all orders
        '''
        if context is None:
           context = {}

        trip_pool = self.pool.get('trip.trip')
        order_pool = self.pool.get('trip.order')

        wizard_proxy = self.browse(cr, uid, ids, context=context)[0] # wizard fields proxy
        
        # Create a production order and open it:
        if wizard_proxy.trip_id:
            trip_id = wizard_proxy.trip_id.id
        else:
            trip_id = trip_pool.create(cr, uid, {
                'date': wizard_proxy.date,
                'tour_id': wizard_proxy.tour_id.id,
                'vector_id': False,
                'note': '',                
                }, context=context)
            
        if wizard_proxy.option == 'override':
            # Change in false all order with trip_id:
            order_ids = order_pool.search(cr, uid, [
                ('trip_id', '=', trip_id)], context=context)
            order_pool.write(cr, uid, order_ids, {
                'trip_id': False, }, context=context)    
        
        order_ids = context.get('active_ids', [])            

        # Set trip id to selected order 
        order_pool.write(cr, uid, order_ids, {
            'trip_id': trip_id, }, context=context)    
                          
        return return_view(
            self, cr, uid, trip_id, 
            "account_trip.view_trip_trip_form", 
            "trip.trip", 
            ) 
        
    # -----------------    
    # Utility function:    
    # -----------------    
    def get_status_trip(self, cr, uid, tour_id, context=None):
        ''' Search the trip element for the tour_id passed and return a sort
            of HTML status
        '''
        res = ""    
        trip_pool = self.pool.get('trip.trip')        
        trip_ids = trip_pool.search(
            cr, uid, [('tour_id', '=', tour_id)], context=context)        
        res = _("<p>Trip found: %s</p>") % len(trip_ids)
        for item in trip_pool.browse(cr, uid, trip_ids, context=context):
            for order in item.order_ids:
                if order.id == item.order_ids[0]: # only the first loop
                    res += _("""
                        <p>Order: %s [Date: %s]</p>
                        <p>Load: Prevision %s Max %s  Current: %s</p>
                        <table>
                            <th>
                                <td>Order</td>
                                <td>Date</td>
                                <td>Partner</td>
                                <td>Destination</td>
                            </th>
                        </table>
                        """) % (
                            item.name,
                            item.date,
                            
                            item.max_load,
                            item.prevision_load,
                            item.current_load,                            
                            )
                res += _("""
                    <th>
                        <td>%s</td>
                        <td>%s</td>
                        <td>%s</td>
                        <td>%s</td>
                    </th>                    
                    """) % (
                        order.name,
                        order.date,
                        order.partner_id.name if order.partner_id else "/",
                        order.destination_id.name if order.destination_id else "/",
                        )
        return res
    
    # -------------------    
    # On change function:
    # -------------------    
    def onchange_trip_tour(self, cr, uid, ids, tour_id, context=None):
        ''' Search if there's one previuos trip to update / override
        '''
        res = {'value': {}}
        res['value']['status'] = self.get_status_trip(
            cr, uid, tour_id, context=context)
        return res
        
    # -----------------    
    # Fields functions:
    # -----------------
    # Utility:
    def get_first_tour_id(self, cr, uid, context=None):
        ''' Utility function for search context active_ids and read firs
            order tour element
        '''
        if context is None:
            context = {}
            
        item_ids = context.get('active_ids', []) 
        if item_ids:
            try:
                order_pool = self.pool.get('trip.order')
                order_proxy = order_pool.browse(
                    cr, uid, item_ids, context=context)[0]
                return order_proxy.tour_id.id
            except:
                pass # False                
        return False
    
    def function_get_status(self, cr, uid, fields=None, args=None, 
        context=None):
        ''' Search if is present a previous tour and return a short preview
        '''
        tour_id = self.get_first_tour_id(cr, uid, context=context)
        if tour_id:
            return self.get_status_trip(
                cr, uid, tour_id, context=context)
        else:
            return ''
        
    def function_get_default_trip(self, cr, uid, fields=None, args=None, 
        context=None):
        ''' Search first trip of the list with tour setted up
        '''
        tour_id = self.get_first_tour_id(cr, uid, context=context)
        if tour_id:
            trip_pool = self.pool.get('trip.trip')
            trip_ids = trip_pool.search(
                cr, uid, [('tour_id', '=', tour_id)], context=context)
            if trip_ids:
                return trip_ids[0]            
        return False

    def function_get_default_tour(self, cr, uid, fields=None, args=None, 
        context=None):
        ''' Search first trip of the list with tour setted up
        '''
        return self.get_first_tour_id(cr, uid, context=context)
        
    _columns = {
        'date': fields.date('Date', required=True),        
        'option': fields.selection([
            ('override', 'Create / Override'),
            ('uppend', 'Uppend'), ], 'Option', required=True),
        'tour_id': fields.many2one('trip.tour', 'Tour', 
            required=True, 
            ondelete='set null'),    
        'trip_id': fields.many2one('trip.trip', 'Trip', 
            ondelete='set null'),    
        'status': fields.text('Status',
            help='See the status of previous trip day'),
        }
        
    _defaults = {
        'option': lambda *x: 'override',
        'trip_id': lambda s, cr, uid, ctx: s.function_get_default_trip(
            cr, uid, context=ctx),
        'tour_id': lambda s, cr, uid, ctx: s.function_get_default_tour(
            cr, uid, context=ctx),
        'status': lambda s, cr, uid, ctx: s.function_get_status(
            cr, uid, context=ctx),
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:


