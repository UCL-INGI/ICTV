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

import collections
import os
from datetime import datetime
import io
import random
import string

import qrcode
import qrcode.image.svg
from functools import wraps

import flask
from sqlobject.main import SQLObjectNotFound
from ictv.models.role import UserPermissions
from ictv.models.user import User

import ictv.flask.response as resp



urls = (
    '/', 'ictv.app.IndexPage',
    '/users', 'ictv.pages.users_page.UsersPage',
    '/users/(\d+)','ictv.pages.users_page.UserDetailPage',
    '/screens', 'ictv.pages.screens_page.ScreensPage',
    '/screens/(\d+)', 'ictv.pages.screens_page.DetailPage',
    '/screens/(\d+)/config', 'ictv.pages.screens_page.ScreenConfigPage',
    '/screens/(\d+)/view/(.+)', 'ictv.pages.screen_renderer.ScreenRenderer',
    '/screens/(\d+)/client/(.+)', 'ictv.pages.screen_client.ScreenClient',
    '/screens/(\d+)/subscriptions', 'ictv.pages.screen_subscriptions_page.ScreenSubscriptionsPage',
    '/screens/redirect/(.+)', 'ictv.pages.screen_router.ScreenRouter',
    '/buildings', 'ictv.pages.buildings_page.BuildingsPage',
    '/channels', 'ictv.pages.channels_page.ChannelsPage',
    '/channels/(\d+)', 'ictv.pages.channel_page.ChannelPage',
    '/channels/(\d+)/request/(\d+)', 'ictv.pages.channel_page.RequestPage',
    '/channels/(\d+)/manage_bundle', 'ictv.pages.manage_bundle_page.ManageBundlePage',
    '/channels/(\d+)/subscriptions', 'ictv.pages.channel_page.SubscribeScreensPage',
    '/channel/(\d+)','ictv.pages.channel_page.DetailPage',
    '/channel/(\d+)/force_update','ictv.pages.channel_page.ForceUpdateChannelPage',
    '/plugins', 'ictv.pages.plugins_page.PluginsPage',
    '/plugins/(\d+)/config', 'ictv.pages.plugins_page.PluginConfigPage',
    '/preview/channels/(\d+)/(.+)', 'ictv.pages.channel_renderer.ChannelRenderer',
    '/renderer/(\d+)', 'ictv.pages.utils.DummyRenderer',
    '/renderer/(\d+)/capsule/(\d+)', 'ictv.pages.utils.DummyCapsuleRenderer',
    '/cache/(\d+)', 'ictv.storage.cache_page.CachePage',
    '/storage', 'ictv.pages.storage_page.StoragePage',
    '/storage/(\d+)', 'ictv.pages.storage_page.StorageChannel',
    '/logs', 'ictv.pages.logs_page.LogsPage',
    '/logs/(.+)', 'ictv.pages.logs_page.ServeLog',
    '/logas/(.+)', 'ictv.pages.utils.LogAs',
    '/tour/(started|ended)', 'ictv.pages.utils.TourPage',
    '/client/ks/(.+)', 'ictv.client.pages.client_pages.Kickstart',
    '/emails', 'ictv.pages.emails_page.EmailPage',
    '/transcoding/(.+)/progress', 'ictv.storage.transcoding_page.ProgressPage'
)

sidebar_elements = {
    'ictv.pages.plugins_page.PluginsPage': {'name': 'Plugins', 'icon': 'fa-plug',
                                           'rights': UserPermissions.administrator},
    'ictv.pages.users_page.UsersPage': {'name': 'Users', 'icon': 'fa-users',
                                       'rights': UserPermissions.administrator},
    'ictv.pages.buildings_page.BuildingsPage': {'name': 'Buildings', 'icon': 'fa-building-o',
                                         'rights': UserPermissions.administrator},
    'ictv.pages.channels_page.ChannelsPage': {'name': 'Channels', 'icon': 'fa-picture-o',
                                             'rights': UserPermissions.no_permission},
    'ictv.pages.screens_page.ScreensPage': {'name': 'Screens', 'icon': 'fa-television',
                                           'rights': UserPermissions.screen_administrator},
    'ictv.pages.storage_page.StoragePage': {'name': 'Storage', 'icon': 'fa-hdd-o',
                                            'rights': UserPermissions.super_administrator},
    'ictv.pages.logs_page.LogsPage': {'name': 'Logs', 'icon': 'fa-history',
                                      'rights': UserPermissions.super_administrator},
    'ictv.pages.emails_page.EmailPage': {'name': 'Emails', 'icon': 'fa-envelope',
                                         'rights': UserPermissions.super_administrator}
}


def sidebar(f):
    """ Utility method providing a simple way to populate the sidebar in function of the user permissions. """

    def get_classes_from_user(user):
        """ Returns a list as a tuple of the names of classes in the `pages` package accessible to this user. """
        highest_permission_level = user.highest_permission_level
        if user.disabled:
            return ()
        return (name for name, params in sidebar_elements.items() if params['rights'] in highest_permission_level)

    @wraps(f)
    def decorated_function(*args, **kwargs):
        app = flask.current_app
        app.session = flask.session

        if 'user' in app.session and 'sidebar' not in app.session:
            try:
                u = User.get(app.session['user']['id'])
                if 'real_user' in app.session:
                    real_user = User.get(app.session['real_user']['id'])
                    # if the real user has at least the same right as the "logged as" user
                    if u.highest_permission_level not in real_user.highest_permission_level:
                        resp.seeother('/logas/nobody')
                user_sidebar = {}
                for class_name in get_classes_from_user(u):
                    e = sidebar_elements[class_name]
                    user_sidebar[e['name']] = {'url': urls[urls.index(class_name) - 1], 'icon': e['icon']}
                    app.session['sidebar'] = sorted(user_sidebar.items())
            except SQLObjectNotFound:
                return f(*args, **kwargs)
        return f(*args, **kwargs)

    return decorated_function



def generate_secret(digits=string.digits):
    return ''.join(
        random.SystemRandom().choice(string.ascii_lowercase + string.ascii_uppercase + digits) for _ in range(8))


def make_tooltip(text, placement='top', icon=False, icon_class='fa-info-circle', classes='pull-right'):
    tooltip_attrs = 'data-toggle="tooltip" data-container="body" data-placement="%s" data-original-title="%s"' % \
                    (placement, text)
    if icon:
        return '<i class="fa %s %s" style="margin: 0 !important" %s></i>' % (icon_class, classes, tooltip_attrs)
    return tooltip_attrs


def make_alert(title, text, alert_type='alert-warning', icon=False, icon_class='fa-info-circle'):
    icon_str = ('<i class="icon fa %s"></i>' % icon_class) if icon else ""
    html = """
    <div class="alert %s">
        <button type="button" class="close" data-dismiss="alert" aria-hidden="true">×</button>
        <h4>%s%s</h4>
        %s
    </div>
    """ % (alert_type, icon_str, title, text)
    return html


def make_qrcode(text, size=25, border=1):
    """
        Returns a byte array with the content of a svg file representing the QR code for the given text.
        size controls the size of each pixel of the QR code,
        border sets how many blank pixels from the QR code are bordering the image.
    """
    stream = io.BytesIO()
    qrcode.make(text, border=border,
                image_factory=qrcode.image.svg.SvgPathFillImage, box_size=size).save(stream)
    return stream.getvalue()


def get_feedback(type, message):
    return {
        'type': type,
        'message': message
    }


def feedbacks_has_type(type, feedbacks):
    for f in feedbacks:
        if f['type'] == type:
            return True
    return False


def deep_update(d, u):
    for k, v in u.items():
        if isinstance(v, collections.Mapping):
            r = deep_update(d.get(k, {}), v)
            d[k] = r
        else:
            d[k] = u[k]
    return d


def timesince(dt, default="just now", when_none=Exception()):
    """
    Returns string representing "time since" e.g.
    3 days ago, 5 hours ago etc.
    When dt is None, raises an exception if when_none == Exception, returns when_none otherwise.
    """

    if dt is None:
        if when_none == Exception():
            raise Exception("The datetime parameter is None")
        else:
            return when_none
    now = datetime.now()
    diff = now - dt

    periods = (
        (diff.days // 365, "year", "years"),
        (diff.days // 30, "month", "months"),
        (diff.days // 7, "week", "weeks"),
        (diff.days, "day", "days"),
        (diff.seconds // 3600, "hour", "hours"),
        (diff.seconds // 60, "minute", "minutes"),
        (diff.seconds, "second", "seconds"),
    )

    for period, singular, plural in periods:

        if period > 0:
            return "%d %s ago" % (period, singular if period == 1 else plural)

    return default


def pretty_print_size(byte_size):
    suffixes = ['B', 'kB', 'MB', 'GB', 'TB', 'PB']
    if not byte_size or byte_size == 0:
        return '0 B'
    i = 0
    while byte_size >= 1024 and i < len(suffixes) - 1:
        byte_size /= 1024.
        i += 1
    f = ('%.2f' % byte_size).rstrip('0').rstrip('.')
    return '%s %s' % (f, suffixes[i])


def is_test():
    return os.environ.get('WEBPY_ENV') == 'test'

def get_methods(elem):
    http_methods = ["GET","POST","DELETE","PUT","HEAD","CONNECT","OPTIONS","TRACE","PATCH"]
    return [m for m in http_methods if elem.__dict__.get(m.lower())!=None]
