An introduction to ICTV
=======================

ICTV is a simple content management system for digital signage on multiple screens.
It is a web application written in Python. Everything from the management of the content to its reproduction on
screens happens in a web browser.
ICTV is easily extendable, with a simple and powerful plugin system.
ICTV is free and open-source. It has been developed at UCLouvain_ and is currently being deployed on more than twenty
screens throughout the campus.

.. _UCLouvain: https://uclouvain.be/en/index.html

Key concepts
------------

Simplicity is a key goal of ICTV. Only a few concepts are needed to be explained to understand the principles of
ICTV.

Plugins
~~~~~~~

Plugins are at the heart of ICTV. They are programs that bring content to the system. They can be automated programs
that operates autonomously once configured, such as a plugin that creates content based on an RSS feed. They can also
offer a rich web interface to the users of ICTV.

There already exist several useful plugins:

* **editor** is a fully featured web editor to create slideshows.
* **embed** allows any web page to be embedded into the system.
* **rss** is an RSS parser creating content based on an RSS feed.
* **img-grabber** easily extracts images from web pages and reproduces them in a stylish way.

Channels
~~~~~~~~

Channels are used to organize content. Much like TV channels, they allow various themed information to be brought in
and distributed over the screen networks. Each channel is an instance of a plugin, i.e. a parametrisation of this
plugin. Channels can have several types of access rights to restrict their use to particular user.

Channel bundles
~~~~~~~~~~~~~~~

Channels can be grouped into bundles. They allow to group channels broadcasting similar content. Screen administrator
can subscribe once to a bundle that can be expanded later on.

Screens
~~~~~~~

Screens are outputs to display the content produced inside ICTV. They may be physical, e.g. a TV, or virtual, e.g. a
web page. Content is brought to screens via subscriptions. A screen displays the content of all channels it is
subscribed to.