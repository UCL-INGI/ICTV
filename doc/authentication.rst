.. _authenticating:

Authenticating to ICTV
======================

ICTV offers multiple ways of authenticating to the system. Two methods are currently supported. Local authentication
uses local accounts stored inside the ICTV database, while SAML2 relies on an external identity provider such as
Shibboleth to handle the accounts details.

Methods of authentication can be combined in the ICTV configuration file. Add the authentication methods you would
like to use to the list of values for the ``authentication`` key. The first method in the list will be the default
method used. ICTV accounts will be matched based on the email address of the user.

Authenticating for the first time
---------------------------------

After having installed ICTV, a default user named *ICTV Admin* will be created. To log in using this account, the 
`debug.autologin` key should be set to true. At this point you can either enable local authentication and change its
password, or create another administrator account with coherent values for another authentication method. Note that this can be done on a local instance before deploying to production, and then transfer the database between the two.

Local authentication
--------------------

Is configured by indicating the ``local`` value inside the list of value for the ``authentication`` key. No other
configuration is required.

SAML2/Shibboleth authentication
-------------------------------

SAML2 can be configured by adding the ``saml2`` value to the list of authentication methods. It also requires to
configure the ``saml2`` key in the configuration file. An example can be found in the default configuration file and
more details about the meaning of each parameters can be found in the `python3-saml`_ documentation.

.. _python3-saml: https://github.com/onelogin/python3-saml/#settings
