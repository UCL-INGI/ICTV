#!/usr/bin/env bash
ictv_root_url=$1
authorized_keys=$2
setenforce 0
sed -i 's/^SELINUX=.*/SELINUX=disabled/g' /etc/selinux/config
dnf upgrade -y
dnf group install -y base-x fonts
dnf install -y chromium python3 python3-devel clang libxml2-devel libxslt-devel xlogin unzip acpi acpid vim
pip3 install requests bs4 lxml werkzeug
adduser ictv
sed -i 's,ExecStart=/usr/bin/x-daemon -noreset %I,ExecStart=/usr/bin/x-daemon -noreset -nocursor %I,g' /usr/lib/systemd/system/x@.service
systemctl enable xlogin@ictv
systemctl set-default graphical.target
cd /
curl -L -O ${ictv_root_url}/client/ks/system.zip
unzip -o system.zip
cd /home/ictv/
curl -L -O ${ictv_root_url}/client/ks/client.zip
unzip -o client.zip
chown ictv:ictv -R /home/ictv
# Force VT 7 at boot
crontab -l > /root/crontab.old
echo "@reboot chvt 7" > /tmp/root_crontab
crontab /tmp/root_crontab
# Sysadmin key
cd /root
mkdir .ssh
echo ${authorized_keys} > .ssh/authorized_keys
chmod 700 .ssh/
chmod 600 .ssh/authorized_keys

