Advanced concepts
=================

More advanced components have to be understood to be able to develop and contribute to ICTV.

Slides
------

The smallest piece of content in ICTV is a slide. It defines the content it contains and how it is layed out. The
content is a dictionary defining elements of the slide with a special syntax. It has the following form:

.. code:: python

    {
        '[field-type]-[field-number]': {
            '[input-type]': '[field-data]',
            ...
        },
        ...
    }

The field type allows to define what type of content is the element. The supported field types are:

* ``title`` -- The main title of the slide.
* ``subtitle`` -- A subtitle.
* ``text`` -- A general text field. It will generally contain the text paragraphs of a slide.
* ``logo`` -- A small image often found in the corners of the slide, usually indicating the source of the slide.
* ``image`` -- A general purpose image
* ``background`` -- An image that is set as a background of the slide

A number is added to distinguish elements when the slide contains multiple elements of the same type.

The input type defines the pieces of data that the element contains. Field types can sometimes contain multiple input
types as described in the following list:

* ``title``, ``subtitle``, ``text``:
    * ``text`` -- The text to display, also accepts HTML.
* ``logo``, ``image``, ``background``:
    * ``src`` -- A value that will populate the HTML ``image`` element src attribute. It can be a absolute, a relative
      path w.r.t. the application root or a data URL.
    * ``qrcode`` -- A text value that will be converted to a QR code and automatically inserted in the ``src`` field.
* ``background``:
    * ``size`` -- Can be either ``contain`` or ``cover``. It defines if the background will be resized to fit the slide
      or will be stretched cover it. More advanced uses are documented here_.
    * ``color`` -- A color that will fill the background. It defaults to black.
    * ``iframe`` -- An URL that will be displayed in an iframe as background. It cannot be used together with
      ``src`` or ``video``
    * ``video`` -- An URL to a video that will be played in the background of the slide. It cannot be used together with
      ``src`` or ``video``.
      If you plan on playing videos, you should use the :class:`~ictv.plugin_manager.plugin_utils.VideoSlide`
      class rather than this field directly.

Here is an example of slide content:

.. code:: python

    {
        'title-1': {'text': "Awesome title"},
        'subtitle-1': {'text': "Subtile subtitle"},
        'text-1': {'text': "Very long textual text here"},
        'image-1': {'src': "http://thecatapi.com/api/images/get"},
        'logo-1': {'src': "sausage.png"},
    }

Each slide also specifies the duration it should be displayed before switching to a new slide. The abstract class
:class:`~ictv.plugin_manager.plugin_slide.PluginSlide` contains the minimal contract for implementing slides in ICTV.

The way elements are layed out in the slide is defined in its template. A slide specifies a reference to the template
that should be used to render the slide. We define templates in the next section.

.. autoclass:: ictv.plugin_manager.plugin_slide.PluginSlide
.. autoclass:: ictv.plugin_manager.plugin_utils.VideoSlide

.. _here: https://developer.mozilla.org/fr/docs/Web/CSS/background-size

Templates
---------

Templates lay out the content of a slide. They are web.py templates that contain custom functions that render each
field type. Templates should avoid to impose a certain visual aspect to the content, but rather focus on how it is
layed out in the slide.

.. code-block:: html

    $def with (slide)
    $var name: An example template
    $var description: Title and subtitle with text on the left side followed by image
    $code:
        template_id = get_template_id()
    <section>
        <div class="logo">
            $:logo(content=slide, number=1)
        </div>
        <div class="content $template_id">
            $:title(content=slide, number=1, max_chars=20)
            $:subtitle(content=slide, number=1, max_chars=30)
            <div style="display: flex;">
                <div style="flex: 1">
                    $:image(content=slide, number=1)
                </div>
                <div style="flex: 2; vertical-align:middle">
                    $:text(content=slide, number=1, max_chars=160)
                </div>
            </div>
        </div>
    </section>

The template receives the slide content as parameters and outputs HTML content that lays out its elements. This HTML
content can be used with RevealJS_ to display a slide. This template defines five fields that can be filled. The
``number`` argument will match the field number in the slide content. Fields that contain text can be limited to a
certain amount of characters using the ``max_chars`` keyword argument. Each template should provide a name and a
description through the corresponding global variables defined at the top of the file. All templates can be found in
the directory ``ictv/renderer/templates``.

Considering the example of slide content of the previous section and the template above, the
:class:`~ictv.renderer.renderer.ICTVRenderer` will output the following HTML content:

.. code-block:: html

  <section>
    <div class="logo">
      <img src="/static/sausage.jpg">
    </div>
    <div class="content">
      <h1 class="title">Awesome title</h1>
      <h4 class="subtitle">Subtile subtitle</h4>
      <div style="display: flex;">
        <div style="flex: 1">
          <img src="http://thecatapi.com/api/images/get" class="sub-image">
        </div>
        <div style="flex: 2; vertical-align:middle">
          <p style="text-align:justify" class="subtitle">
          Very long textual text here
          </p>
        </div>
      </div>
    </div>
  </section>


.. autoclass:: ictv.renderer.renderer.ICTVRenderer

.. _RevealJS: https://github.com/hakimel/reveal.js/


Capsules
--------

One might need to create several slides to present a particular information. These slides can be grouped together
inside a capsule. A capsule offers the guarantee that the slides it contain will always be presented all together in
the same order.

The :class:`~ictv.plugin_manager.plugin_capsule.PluginCapsule` class contains the minimal contract for implementing
capsules in ICTV.

A capsule also allows to set a common theme for all the slides. Its use is described in the next section.

.. autoclass:: ictv.plugin_manager.plugin_capsule.PluginCapsule

Themes
------

The theme defines the appearance of each slide. It can for example set particular colours for particular elements of
a slide. It can also provide default values for slide elements, such as a default logo. These default values will be
used if the template chosen by a slide accommodates such elements and its slide content does not define values for
them.

The themes are defined in the ``ictv/renderer/themes`` directory. A theme follows this structure inside the theme
directory:

.. code::

    theme_name
    ├── assets
    │   └── # put theme-specific assets here
    └── config.yaml


A full example theme configuration file can be found in ``ictv/renderer/themes/config.example.yaml``.

.. literalinclude:: ../ictv/renderer/themes/config.example.yaml

A theme can include a CSS file that will contain rules for particular elements of a slide. Each rule should be
prefixed by a ``.theme_name`` selector to ensure that each theme can coexists with others.


