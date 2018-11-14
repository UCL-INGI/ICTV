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

import web
import datetime
from onelogin.saml2.auth import OneLogin_Saml2_Auth
from onelogin.saml2.utils import OneLogin_Saml2_Utils

from ictv.models.user import User
from ictv.pages.utils import ICTVPage


def build_settings(settings):
    """
        Build the SAML2 configuration from the app config.

        Note for later : 
            The best would be to include this directly into the ICTVPage class?
            That would allow to call this method only once at boot time.
            Maybe there should be a mechanism that allowed this kind of
            "plugin" (an optionnal authentication method) to access a hook
            into the ICTV core initialization?

            For now, we'll keep all this into a single module.
    """
    if not 'sp' in settings or not 'NameIDFormat' in settings['sp']:
        entity_id = settings['sp']['entityId']
        # add field that are NOT configurable (for now at least...) TODO. add more flexibility to the config
        settings['sp']['assertionConsumerService'] = {
            'url': entity_id + '?acs',
            'binding': 'urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST'
        }
        settings['sp']['singleLogoutService'] = {
            'url': entity_id + '?sls',
            'binding': 'urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect'
        }
        settings['sp']['NameIDFormat'] = 'urn:oasis:names:tc:SAML:1.1:nameid-format:unspecified'
    return settings


def init_saml_auth(req, settings):
    auth = OneLogin_Saml2_Auth(req, settings)
    return auth


def prepare_request():
    # If server is behind proxys or balancers use the HTTP_X_FORWARDED fields
    data = web.input()
    return {
        'https': 'on' if web.ctx.protocol == 'https' else 'off',
        'http_host': web.ctx.environ['HTTP_X_FORWARDED_SERVER'],  # ONLY IN FORWARDED MODE
        'server_port': '443',  # should be dynmically discovered
        'script_name': web.ctx.homepath,
        'get_data': data.copy(),
        'post_data': data.copy(),
        # Uncomment if using ADFS as IdP, https://github.com/onelogin/python-saml/pull/144
        # 'lowercase_urlencoding': True,
        'query_string': web.ctx.query
    }


class MetadataPage(ICTVPage):
    def GET(self):
        req = prepare_request()
        settings = build_settings(self.config['saml2'])
        auth = init_saml_auth(req, settings)
        settings = auth.get_settings()
        metadata = settings.get_sp_metadata()
        errors = settings.validate_metadata(metadata)

        if len(errors) == 0:
            web.header('Content-Type', 'text/xml')
            return metadata
        else:
            web.ctx.status = '500 Internal Server Error'
            return ', '.join(errors)


class Shibboleth(ICTVPage):
    def GET(self):
        req = prepare_request()
        settings = build_settings(self.config['saml2'])
        auth = init_saml_auth(req, settings)
        errors = []
        not_auth_warn = False
        success_slo = False

        input_data = web.input()

        if 'sso' in input_data:
            raise web.seeother(auth.login())

        raise web.seeother('/')

    def POST(self):
        """
            Receive the POST binding request from IDP.

             - process the request
            - extract user attributes
            - create a new User if it doesn't exist
            - fill in the session
            - redirect to RelayState or /
        """

        # SAML boiler plate code
        req = prepare_request()
        settings = build_settings(self.config['saml2'])
        # this is the object to interact with the shibboleth parameters
        auth = init_saml_auth(req, settings)
        errors = []
        not_auth_warn = False
        success_slo = False

        input_data = web.input()

        if 'acs' in input_data:
            auth.process_response()  # decrypt and extract informations
            errors = auth.get_errors()
            not_auth_warn = not auth.is_authenticated()

            if len(errors) == 0:
                attrs = auth.get_attributes()  # get attributes returned by the shibboleth idp

                for key in attrs.keys():
                    print("(" + key + ", " + str(attrs[key]) + ")")

                username = attrs[settings['sp']['attrs']['username']][0]
                realname = attrs[settings['sp']['attrs']['realname']][0]
                email = attrs[settings['sp']['attrs']['email']][0]

                u = User.selectBy(email=email).getOne(None)
                
                if not u:  # The user does not exist in our DB
                    u = User(username=username,
                             email=email,
                             fullname=realname,
                             super_admin=False,
                             disabled=True,
                             creation_date=datetime.datetime.now())
                u.last_connection = datetime.datetime.now()
                self.session['user'] = u.to_dictionary(['id', 'fullname', 'username', 'email'])

                self_url = OneLogin_Saml2_Utils.get_self_url(req)
                if 'RelayState' in input_data and self_url != input_data['RelayState']:
                    raise web.seeother(auth.redirect_to(input_data['RelayState']))

        raise web.seeother('/')
