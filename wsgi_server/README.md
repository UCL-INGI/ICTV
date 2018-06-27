# Vagrant for WSGI server example
This directory contains a Vagrant configuration that will setup an `httpd` wsgi server with ICTV on the `wsgi_compat` branch.

## What you need to do
Add the private key for the git repository (without passphrase) in this directory, under the name `id_rsa`.

## What it does
Basically, it :
* Disables `selinux`
* Installs all the needed dependencies for ICTV, and `httpd`
* Compiles and installs the mod_wsgi module for httpd. (TODO: It could have been pre-compiled)
* Configures `httpd` to host ICTV on port 80 of the VM. **It does not need a particular hostname and answers to everybody.** The modifications applied to `/etc/sysconfig/httpd` and `/etc/httpd/conf/httpd.conf` are available in this directory in `httpd/httpd.conf.patch` and `sysconfig_httpd.patch`.
* Installs ICTV from the `wsgi_compat` branch, in the `/var/www/ictv-v2` directory of the VM and runs the database setup. It does not enable the `autologin`.
