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

The aforementioned dependencies can be installed on CentOS 7 as
follows:

.. highlight:: console

::

    yum install -y https://centos7.iuscommunity.org/ius-release.rpm
    yum install -y git python35u python35u-pip python35u-devel ImageMagick-devel mediainfo

Using SAML for authentication requires the following additional dependencies:

::

    yum install -y libxml2 xmlsec1 libxml2-devel xmlsec1-devel xmlsec1-openssl-devel libtool-ltdl-devel


Installing ffmpeg on CentOS 7
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Installing ffmpeg on CentOS 7 is not easy as packages are not broadly available. Moreover, no package have compiled
ffmpeg with the support for WebM encoders (libvpx and libvpx-vp9). We built new packages for this purpose. The
nux-desktop repository offers their dependencies.

::

    yum install -y http://li.nux.ro/download/nux/dextop/el7/x86_64/nux-dextop-release-0-5.el7.nux.noarch.rpm
    yum install -y http://studmanager.info.ucl.ac.be/repo/repo-INGI/centos/7/x86_64/ffmpeg-2.8.13-2.el7.centos.x86_64.rpm http://studmanager.info.ucl.ac.be/repo/repo-INGI/centos/7/x86_64/ffmpeg-libs-2.8.13-2.el7.centos.x86_64.rpm http://studmanager.info.ucl.ac.be/repo/repo-INGI/centos/7/x86_64/libavdevice-2.8.13-2.el7.centos.x86_64.rpm
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
