Installing ICTV server
======================

ICTV is intended to be ran on Linux, compatibility with others OSes is
unknown at the moment.

Dependencies
------------

ICTV has the following dependencies:

-  Python (with pip) **3.5.1+**
-  Library links and header files for ImageMagick (packaged as
   ImageMagick-devel on RHEL derivatives)
-  Libxml2 >= 2.9.1
-  xmlsec1 >= 1.2.14
-  MediaInfo, a convenient unified tool to display the most relevant
   technical and tag data for video and audio files.
-  FFmpeg, for automatic video transcoding to WebM.

The aforementioned dependencies can be installed on CentOS 8 as
follows:

.. highlight:: console

::

    dnf config-manager --set-enabled PowerTools
    dnf install python36 python36-devel git ImageMagick-devel mediainfo

Using SAML for authentication requires the following additional dependencies:

::

    dnf install wget gcc xmlsec1-devel libtool-ltdl-devel


Installing the dependencies on macOS
------------------------------------

All dependencies can be installed using brew.

::

    brew install imagemagick Libxml2 MediaInfo FFmpeg xmlsec1 libmagic


Installing ffmpeg on CentOS 8
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Installing ffmpeg on CentOS 8 can be done via the RPMFusion repositories. It is compiled with the
support for WebM encoders (libvpx and libvpx-vp9).

::

    dnf install https://download1.rpmfusion.org/free/el/rpmfusion-free-release-8.noarch.rpm
    dnf install https://download1.rpmfusion.org/nonfree/el/rpmfusion-nonfree-release-8.noarch.rpm
    dnf install ffmpeg
    ffmpeg -encoders | grep vpx  # Check that both vpx encoders are available

Installing ICTV
---------------

Your system is now setup, you are free to use a privileged or unprivileged
user for the rest of the procedure. The recommended way to install ICTV is
by using pip and the master branch of the ICTV git repository.

::

    pip3 install --upgrade git+https://github.com/UCL-INGI/ICTV.git
    pip3 install --upgrade git+https://github.com/UCL-INGI/ICTV-plugins.git

pip will automatically install the additional Python dependencies.

Configuring ICTV
----------------

Creating a configuration file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In the configuration file, you will be able to set many parameters to
fine tune ICTV to your use. An example of a full configuration file
named ``configuration.example.yaml`` can be found at the root of the
source code. Feel free to start from it but remember to create a
separate file. If a parameter is missing from the configuration
file, a default value specified in ``ictv/configuration.default.yaml``
will be used. If no default value is available for the parameter, an
error message and exception will be raised at the start of the application.

See :ref:`authenticating` for more details on configuring authentication.
See :ref:`setting_up` for a minimal configuration file.

Creating a new database
~~~~~~~~~~~~~~~~~~~~~~~

Run ``ictv-setup-database`` to create a new database. Skip this
step if you are upgrading from an existing installation.

::

  usage: ictv-setup-database [-h] [--config CONFIG]

  optional arguments:
    -h, --help       show this help message and exit
    --config CONFIG  Path to configuration file. Defaults to: configuration.yaml


Running ICTV
------------

Starting the webapp can be done with ``ictv-webapp``.

::

    usage: ictv-webapp [-h] address_port [--config CONFIG]

    positional arguments:
      address_port     Address and port to bind the webapp to.
                       E. g.: 0.0.0.0:8080

    optional arguments:
      -h, --help       show this help message and exit
      --config CONFIG  Path to configuration file. Defaults to: configuration.yaml

Using WSGI
~~~~~~~~~~

Use ``ictv.wsgi`` to deploy ICTV using WSGI. An example of Apache, ``mod_wsgi`` and
ICTV running together on a CentOS virtual machine is available in the
``wsgi_server`` directory.
