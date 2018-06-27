Installing a dedicated ICTV client
==================================

A dedicated ICTV client offers more features than directly using the webpage
of a screen to display its content. It adds a local caching mechanism that
ensures that previous content is kept across reboots. A client that cannot
fetch new content from the server will display the past content and display
a non-obtrusive error message.

A dedicated ICTV client also does not require direct access to the Internet.
It only requires access to the ICTV server, which will serve all the assets
needed by a client. This is a safer approach for deploying ICTV clients and is
the recommended way.

ICTV has a built-in mechanism for easy deployment of clients. ICTV clients are
meant to be run on x64 hardware. Once your ICTV server instance is deployed,
you are ready to install and attach clients to it.

The installation is rather simple as it only consists of two steps:

-  Locate your client MAC address and associate it with a screen inside
   ICTV interface. Make sure to input the MAC of the interface your
   client will use to connect to the ICTV server.

The second step is OS-specific. Note that those two steps can be swapped,
but you will need to restart the client after associating it with a screen
inside ICTV.

Installing Fedora-based clients
-------------------------------

-  Boot the client using a Fedora installation media and load the
   kickstart file served by your ICTV instance. Kickstart files are
   located under the ``/client/ks`` directory and are served by the
   webserver. If your server is HTTPS-enabled, use the HTTPS protocol
   when setting the kickstart file URL. Setting the kickstart file URL can be
   done from the command line when booting the installation media. Refer to the
   `Fedora documentation`_ for more details. Once the installation is complete,
   hit reboot.

.. _Fedora documentation:
    https://fedoraproject.org/wiki/Anaconda/Kickstart/KickstartingFedoraLiveInstallation#The_Network_Solution

Installing Ubuntu-based clients
-------------------------------

Ubuntu sometimes offers better hardware support for 3D acceleration out of the
box. ICTV can also be installed on Ubuntu clients.

-  Boot the client using a Ubuntu installation media and load the preseed
   configuration file served by your ICTV instance. It can be found in the
   ``/client/ks`` directory. Setting the preseed file is detailed in the
   `Debian documentation`_.


.. warning::

   If your server is HTTPS-enabled, you may
   have to add the ``debian-installer/allow_unauthenticated_ssl=true`` option
   to bypass certificate checks.

.. _Debian documentation: https://wiki.debian.org/DebianInstaller/Preseed#Loading_the_preseeding_file_from_a_webserver

Restarting the client
---------------------

The client can be restarted without a full reboot by restarting the
systemd service ``xlogin@ictv``. In the same manner, it can be stopped
and started as necessary.
