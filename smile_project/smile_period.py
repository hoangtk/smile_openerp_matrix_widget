# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 Smile. All Rights Reserved
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

import datetime
from dateutil.relativedelta import relativedelta

from osv import osv, fields
from tools.translate import _



class smile_period(osv.osv):
    """ Smile periods are always 1 month long.

    """

    _name = 'smile.period'

    _order = "start_date"


    ## Utility methods

    def _str_to_date(self, date):
        """ Transform string date to a proper date object
        """
        if not isinstance(date, (datetime.date, datetime.datetime)):
            date = datetime.datetime.strptime(date, '%Y-%m-%d').date()
        return date

    def _get_month_start(self, date):
        return datetime.date(date.year, date.month, 1)

    def _get_month_end(self, date):
        return (self._get_month_start(date) + relativedelta(months=1)) - datetime.timedelta(days=1)


    ## Function fields methods

    def _generate_name(self, start_date, end_date):
        """ Generate a human-friendly period name based on its dates
        """
        start_date = self._str_to_date(start_date)
        end_date = self._str_to_date(end_date)
        # TODO: Localize ?
        name = ['?? ???'] * 2
        if start_date:
            name[0] = start_date.strftime("%d %b")
        if end_date:
            name[1] = end_date.strftime("%d %b")
        return ' - '.join(name)

    def _get_name(self, cr, uid, ids, name, arg, context=None):
        res = {}
        for period in self.browse(cr, uid, ids, context):
            res[period.id] = self._generate_name(period.start_date, period.end_date)
        return res

    def _get_month(self, cr, uid, ids, name, arg, context=None):
        res = {}
        for period in self.browse(cr, uid, ids, context):
            if period.start_date:
                # TODO: Localize ?
                res[period.id] = self._str_to_date(period.start_date).strftime("%B")
        return res


    ## Object fields definition

    _columns = {
        'name': fields.function(_get_name, method=True, type='char', size=100, string='Name', readonly=True),
        'start_date': fields.date('Start', required=True),
        'end_date': fields.date('End', required=True),
        'month_name': fields.function(_get_month, method=True, type='char', size=16, string='Month', readonly=True),
        'line_ids': fields.one2many('smile.period.line', 'period_id', "Period lines"),
        'project_ids': fields.one2many('smile.project', 'period_id', "Projects"),
        }

    _defaults = {
        'start_date': datetime.date(datetime.datetime.today().year, datetime.datetime.today().month, 1).strftime('%m/%d/%Y'), # Same behaviour as _get_month_start()
        'end_date': ((datetime.date(datetime.datetime.today().year, datetime.datetime.today().month, 1) + relativedelta(months=1)) - datetime.timedelta(days=1)).strftime('%m/%d/%Y'), # Same behaviour as _get_month_end()
        }


    ## Native methods

    def write(self, cr, uid, ids, vals, context=None):
        today = datetime.date.today()
        for period in self.browse(cr, uid, ids, context):
            if self._str_to_date(period.end_date) < today:
                raise osv.except_osv(_('Error !'), _("Past periods are archived and can't be updated."))
        ret = super(smile_period, self).write(cr, uid, ids, vals, context)
        # Automaticcaly remove out of range lines if dates changes
        if 'start_date' in vals or 'end_date' in vals:
            self.remove_outdated_lines(cr, uid, ids, vals, context)
        return ret

    def copy(self, cr, uid, id, default=None, context=None):
        raise osv.except_osv(_('Error !'), _("Periods can't be duplicated. They have to be generated from scratch."))

    def unlink(self, cr, uid, ids, context=None):
        for period in self.browse(cr, uid, ids, context):
            if len(period.project_ids):
                raise osv.except_osv(_('Error !'), _("Can't remove periods which have projects attached to it."))
        return super(smile_period, self).unlink(cr, uid, ids, context)


    ## Constraints methods

    def _check_period_start(self, cr, uid, ids, context=None):
        today = datetime.date.today()
        for period in self.browse(cr, uid, ids, context):
            if self._str_to_date(period.start_date) < self._get_month_start(today):
                return False
        return True

    def _check_period_range(self, cr, uid, ids, context=None):
        for period in self.browse(cr, uid, ids, context):
            # Dates are YYYY-MM-DD strings, so can be compared as-is
            if period.start_date > period.end_date:
                return False
        return True

    def _check_period_lenght(self, cr, uid, ids, context=None):
        for period in self.browse(cr, uid, ids, context):
            start_date = self._str_to_date(period.start_date)
            end_date = self._str_to_date(period.end_date)
            if start_date != self._get_month_start(start_date) or end_date != self._get_month_end(start_date) or start_date.month != end_date.month or start_date.year != end_date.year:
                return False
        return True

    def _check_overlapping(self, cr, uid, ids, context=None):
        """ Check if any other period overlap the current one
        """
        for period in self.browse(cr, uid, ids, context):
            if len(self.pool.get('smile.period').search(cr, uid, [('start_date', '<=', period.end_date), ('end_date', '>=', period.start_date), ('id', '!=', period.id)], context=context, limit=1)):
                return False
        return True

    _constraints = [
        (_check_period_start, "It doesn't make sense to create a period starting before the current month.", ['start_date']),
        (_check_period_range, "Stop date must be greater or equal to start date.", ['start_date', 'end_date']),
        (_check_period_lenght, "A period must cover the whole month.", ['start_date', 'end_date']),
        (_check_overlapping, "A period can't overlap another one.", ['start_date', 'end_date']),
        ]


    ## On change methods

    def onchange_start_date(self, cr, uid, ids, start_date, end_date):
        return {'value': {'name': self._generate_name(start_date, end_date)}}

    def onchange_end_date(self, cr, uid, ids, start_date, end_date):
        return {'value': {'name': self._generate_name(start_date, end_date)}}


    ## Custom methods

    #def get_date_range(self, day_delta=1):
        #""" Get a list of date objects covering the given date range
        #"""
        #date_range = []
        #start_date = self.start_date
        #end_date = self.end_date
        #if not isinstance(start_date, (datetime.date, datetime.datetime)):
            #start_date = datetime.datetime.strptime(start_date, '%Y-%m-%d')
        #if not isinstance(end_date, (datetime.date, datetime.datetime)):
            #end_date = datetime.datetime.strptime(end_date, '%Y-%m-%d')
        #date = start_date
        #while date <= end_date:
            #date_range.append(date)
            #date = date + datetime.timedelta(days=day_delta)
        #return date_range

    #def get_active_date_range(self, project, day_delta=1):
        #""" Get a list of date objects covering the given date range
        #"""
        #date_range = []
        #start_date = project.start_date
        #end_date = project.end_date
        #if not isinstance(start_date, (datetime.date, datetime.datetime)):
            #start_date = datetime.datetime.strptime(start_date, '%Y-%m-%d')
        #if not isinstance(end_date, (datetime.date, datetime.datetime)):
            #end_date = datetime.datetime.strptime(end_date, '%Y-%m-%d')
        #date = start_date
        #while date <= end_date:
            #date_range.append(date)
            #date = date + datetime.timedelta(days=day_delta)
        #return date_range

    def remove_outdated_lines(self, cr, uid, ids, vals, context):
        """ This method remove out of range lines existing in this period
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        outdated_lines = []
        for period in self.browse(cr, uid, ids, context):
            start_date = datetime.datetime.strptime(period.start_date, '%Y-%m-%d')
            end_date = datetime.datetime.strptime(period.end_date, '%Y-%m-%d')
            for line in period.line_ids:
                date = datetime.datetime.strptime(line.date, '%Y-%m-%d')
                if date < start_date or date > end_date:
                    # Line is out of range. Delete it.
                    outdated_lines.append(line.id)
        if outdated_lines:
            self.pool.get('smile.period.line').unlink(cr, uid, outdated_lines, context)
        return

smile_period()



class smile_period_line(osv.osv):
    _name = 'smile.period.line'

    _columns = {
        'date': fields.date('Date', required=True),
        'period_id': fields.many2one('smile.period', "Period", required=True, ondelete='cascade'),
        }

smile_period_line()