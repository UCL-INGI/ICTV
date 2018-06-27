# -*- coding: utf-8 -*-
#
#    This file belongs to the ICTV project, written by Nicolas Detienne,
#    Francois Michel, Maxime Piraux, Pierre Reinbold and Ludovic Taffin
#    at Université catholique de Louvain.
#
#    Copyright (C) 2016-2018  Université catholique de Louvain (UCL, Belgium)
#
#    ICTV is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    ICTV is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with ICTV.  If not, see <http://www.gnu.org/licenses/>.

import logging
import web
from sqlobject import SQLObjectNotFound

from ictv.models.plugin import Plugin
from ictv.models.user import User
from ictv.app import sidebar
from ictv.common.feedbacks import add_feedback, ImmediateFeedback, store_form
from ictv.pages.utils import ICTVAuthPage, PermissionGate

logger = logging.getLogger('pages')


class PluginsPage(ICTVAuthPage):
    @PermissionGate.administrator
    def GET(self):
        return self.render_page()

    @PermissionGate.super_administrator
    def POST(self):
        """ Handles plugin editing and activation. """
        form = web.input()
        try:
            if form.action == 'check_dependencies':
                self.plugin_manager.check_all_plugins_dependencies()
            else:
                plugin_id = int(form.id)
                p = Plugin.get(plugin_id)
                current_user = User.get(self.session['user']['id'])
                if form.action == 'edit':
                    state = 'yes' if 'state' in form and form.state == 'on' else 'no'
                    try:
                        form.name = p.name
                        if p.activated == 'notfound':
                            raise ImmediateFeedback('general', 'plugin_activate_not_found')
                        p.set(activated=state)
                        if p.activated == 'yes':
                            if self.plugin_manager.instantiate_plugin(self.app, p):
                                add_feedback('general', 'plugin_activated')
                            else:
                                raise ImmediateFeedback('general', 'plugin_activation_error')
                        else:
                            add_feedback('general', 'plugin_disabled')
                    except (SQLObjectNotFound, ValueError):
                        raise ImmediateFeedback(form.action, 'invalid_id')
                elif form.action == 'configure':
                    try:
                        for param in p.params_access_rights:
                            param.channel_contributor_read = form.get(param.name + '-cc-r') == 'on'
                            param.channel_contributor_write = form.get(param.name + '-cc-w') == 'on'
                            param.channel_administrator_read = form.get(param.name + '-ca-r') == 'on'
                            param.channel_administrator_write = form.get(param.name + '-ca-w') == 'on'
                            param.administrator_write = form.get(param.name + '-a-r') == 'on'
                            param.administrator_write = form.get(param.name + '-a-w') == 'on'

                        p.cache_activated_default = form.get('cache-activated') == 'on'
                        if 'cache-validity' in form:
                            p.cache_validity_default = int(form['cache-validity'])
                        p.keep_noncomplying_capsules_default = form.get('keep-capsules') == 'on'
                        form.name = p.name
                        add_feedback('general', 'plugin_configured')
                    except (SQLObjectNotFound, ValueError):
                        raise ImmediateFeedback(form.action, 'invalid_id')
                elif form.action == 'delete':
                    if p.channels.count() > 0 and 'confirm-delete' not in form:
                        raise ImmediateFeedback(form.action, 'plugin_has_channels', {'plugin': p.to_dictionary(['id', 'name', 'channels_number', 'screens_number']),
                                                                        'channels': [(c.id, c.name, c.enabled) for c in p.channels]})
                    plugin_name = p.name
                    form.name = plugin_name
                    p.destroySelf()
                    logger.info('The plugin %s has been deleted by %s', plugin_name, current_user.log_name)
                    add_feedback('general', 'plugin_deleted')
        except ImmediateFeedback:
            pass
        store_form(form)
        return self.render_page()

    @sidebar
    def render_page(self):
        current_user = User.get(self.session['user']['id'])
        plugin_dirs = self.plugin_manager.list_plugins()
        plugins = Plugin.update_plugins(plugin_dirs)
        return self.renderer.plugins(plugins=plugins,
                                     missing_dependencies=self.plugin_manager.missing_dependencies,
                                     current_user=current_user)


class PluginConfigPage(ICTVAuthPage):
    @PermissionGate.super_administrator
    def GET(self, plugin_id):
        return self.render_page(Plugin.get(plugin_id))

    @sidebar
    def render_page(self, plugin):
        return self.renderer.plugin_config(plugin)
