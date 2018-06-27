Developing plugins for ICTV
===========================

Plugins are located inside the ``ictv/plugins`` directory. Each plugin follows this file structure:

::

    plugin_name
    └── __init__.py
    └── plugin_name.py
    └── config.yaml

Each plugin must implement a ``get_content`` function that returns a list of objects that extends the
:class:`~ictv.plugin_manager.plugin_capsule.PluginCapsule` abstract class. These files are the only three required
files for creating a minimal plugin for ICTV.

Plugin configuration file
-------------------------

The ``config.yaml`` file is a YAML formatted file with the following structure:

.. code-block:: yaml

    plugin:
      webapp: (yes|no)
      static: (yes|no)
      description: |
        A description of the plugin
      dependencies:
        - a list of dependencies
    channels_params:
      param_name:
        name: 'The pretty name of the channel parameter'
        placeholder: 'A placeholder for its input field'
        type: string  # The type of the parameter
        default: 'A default value for the parameter'

The first block defines the plugin itself, the second one defines the parameters required for its functioning.

In the first block, the following parameters can be specified:

* ``webapp`` -- It defines whether the plugin embeds a web application or not. This possibility is explained in
  detail in :ref:`plugin-web-app`.
* ``static`` -- It defines whether the plugin contains a static directory that will be made available at
  ``/static/plugins/plugin_name`` by the ICTV server.
* ``description`` -- A short description that will be shown to the user. Explain the basics about the plugin in a few
  lines here.
* ``dependencies`` -- A list of strings that indicate the Python modules needed for this plugin to function.

.. note::

    ``dependencies`` lists Python module names, not ``pip`` package names. This allows the ICTV server to check that
    all required packages can be imported before executing the plugin. Missing modules will be reported.


The second block contains all the parameters that a channel should provide to a plugin to execute properly. Each
parameter must be have a unique id as key of ``channels_params`` and must define using the following arguments:

* ``name`` -- The name of the parameter that will be shown to the user.
* ``placeholder`` -- The text that will fill the parameter input field when empty.
* ``type`` -- A string indicating the type of the parameter. The supported types are:

    * ``bool`` -- A boolean value that will be rendered as a checkbox
    * ``int`` -- An integer value. One can specify ``min`` and ``max`` arguments to constrain the range of the value.
    * ``float`` -- A floating point value
    * ``string`` -- A string value
    * ``template`` -- A template that can be chosen from the available templates
    * ``list[type]`` -- A list of value of a given type

* ``default`` -- A default value for the parameter. If possible, provide a set of default working values for the plugin.

This configuration block is used by the ICTV server to generate a configuration page for each channel automatically.

Plugin Python module
--------------------

The ``img-grabber`` plugin is a very simple plugin that we will use as an example to illustrate the code needed to
create a simple plugin. This plugin is given an url and a CSS selector and will extract the first image matching the
selector and output it on a single slide.

.. literalinclude:: ../ictv/plugins/img-grabber/img-grabber.py
    :pyobject: ImgGrabberSlide

The plugin module contains first a definition of a class representing a slide. The slide receives an URL to an
image, a duration and a optional qrcode text value as input. The template that will be used to display the slide is
fixed.

.. literalinclude:: ../ictv/plugins/img-grabber/img-grabber.py
    :pyobject: ImgGrabberCapsule

Then a capsule that will contain a single slide is defined. No theme is set because the slide mainly consists of a
full-size image.

.. literalinclude:: ../ictv/plugins/img-grabber/img-grabber.py
    :linenos:
    :pyobject: get_content
    :emphasize-lines: 2,5-8,12-15,19,25

The ``get_content`` method receives a single argument, which is the id of the channel for which it should produce
content. The channel instance object can be retrieved as shown on line 2. The values for the channel parameters
defined in the config file can be retrieved using the :func:`~ictv.models.channel.PluginChannel.get_config_param`
method as shown in line 5 to 8.

Plugin can report failures arising from configuration errors to the user in a very easy way.
The :class:`~ictv.plugin_manager.plugin_utils.MisconfiguredParameters` class allows to report parameters that caused
failures to the user. Lines 15 and 19 show two examples of usage of this class.

Finally, on line 25, the function returns a list containing a single capsule with the content extracted from the web
page.

.. autoclass:: ictv.models.channel.PluginChannel
    :members: get_config_param

.. autoclass:: ictv.plugin_manager.plugin_utils.MisconfiguredParameters
    :members: add_faulty_parameter

.. _plugin-web-app:

Embedding a web application inside a plugin
-------------------------------------------

More complex plugins that integrate interactive web application can be developed. A full web.py application can be
included with a plugin. To interface with ICTV server, the plugin directory must contain a ``app.py`` file containing
a ``get_app`` function. This function will receive a reference to the main ICTV web.py application and should return
the web.py application of the plugin.

The web application can be used to interact with users. The ``editor`` and ``rss`` plugins embed web application. The
first allows user to create slides and capsules through the web application. The second embeds a more configuration
environment that ease its configuration.

The plugin web application will be embedded inside the ICTV server for each channels of its plugin. For example,
given that the channel with id 4 is a ``PluginChannel`` of ``editor``, the remaining of all URLs starting with
``/channels/4/`` will be passed to its web application.

Plugins web page can use the :class:`~ictv.plugin_manager.plugin_utils.ChannelGate` class to ensure that only
authorised users for a given channel can access the application.

.. autoclass:: ictv.plugin_manager.plugin_utils.ChannelGate

.. automodule:: ictv.plugin_manager.plugin_utils
    :members: webapp_decorator

Storing files for plugins
-------------------------

TODO