.. _setting_up:

Setting up a development environment
====================================

Working directly from the source is not adequate if one has to constantly install and upgrade the Python packages
developed to run the code together. There exist a more appropriate way to integrate ICTV packages from multiple
directories. ICTV is able to discover automatically plugins that are available to import. Adding these directories to
the ``PYTHONPATH`` will make the plugins they contain available for the ICTV server.

.. code-block:: bash

    git clone https://github.com/UCL-INGI/ICTV.git
    git clone https://github.com/UCL-INGI/ICTV-plugins.git
    ...
    PYTHONPATH=ICTV-plugins/ ./ICTV/ictv-webapp


More directories can be added by delimiting them using ``:``.

A minimal ``configuration.yaml`` file for a development environment is:

.. code-block:: yaml

    debug:
      autologin: yes
    database_uri: sqlite:///tmp/ictv_database.sqlite  # You may want to move the database to a persistent directory
    client:
      root_password: ''
      authorized_keys: ''

Linking templates and themes
----------------------------

As themes and templates are not Python modules, they cannot be discovered by using the same mechanism. The simplest way
is to link and unlink the files when needed. One can use the following script to achieve this task.

.. code-block:: python
    :caption: link_assets_for_development.py
    :name: link_assets_for_development.py

    #!/usr/bin/env python3
    import sys
    import os

    try:
        import ictv.renderer
        renderer_path = ictv.renderer.__path__[0]
    except (TypeError, ImportError):
        print('ICTV core could not be found, aborting')
        sys.exit(-1)

    remove = len(sys.argv) > 1

    parent_dir = os.path.dirname(os.path.abspath(__file__))
    themes_dir = os.path.join(parent_dir, 'ictv', 'renderer', 'themes')
    templates_dir = os.path.join(parent_dir, 'ictv', 'renderer', 'templates')

    if os.path.exists(themes_dir):
        for theme in os.listdir(themes_dir):
            link = os.path.join(renderer_path, 'themes', theme)
            if not remove and not os.path.exists(link):
                os.symlink(os.path.join(themes_dir, theme), link, target_is_directory=True)
                print('Installed theme %s {%s -> %s}' % (theme, os.path.join(themes_dir, theme), link))
            elif remove and os.path.exists(link):
                os.unlink(link)
                print('Removed theme ' + link)

    if os.path.exists(templates_dir):
        for template in os.listdir(templates_dir):
            link = os.path.join(renderer_path, 'templates', template)
            if not remove and not os.path.exists(link):
                os.symlink(os.path.join(templates_dir, template), link)
                print('Installed template %s {%s -> %s}' % (theme, os.path.join(themes_dir, theme), link))
            elif remove and os.path.exists(link):
                os.unlink(link)
                print('Removed template ' + link)

.. code-block:: bash

    PYTHONPATH=ICTV/ ICTV-plugins/link_assets_for_development.py
    ...
    PYTHONPATH=ICTV/ ICTV-plugins/link_assets_for_development.py remove
