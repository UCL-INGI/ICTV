#!/usr/bin/env bash
ictv_root_url=$1
authorized_keys=$2
echo "LC_ALL=en_US.UTF-8
LANG=en_US.UTF-8
" >> /etc/environment
apt-get install -y git curl ca-certificates
apt-get update -y
apt-get install -y xfonts-base texlive-fonts-recommended texlive-fonts-extra xserver-xorg xorg openssh-server
apt-get install -y chromium-browser clang libxml2-dev libxslt-dev unzip acpi acpid vim wget
apt-get install -y python3-pip
pip3 install requests bs4 lxml werkzeug
curl -L -s https://raw.githubusercontent.com/hotice/webupd8/master/install-google-fonts | bash -s
adduser --disabled-password --quiet --gecos "" ictv
git clone https://github.com/joukewitteveen/xlogin
cd xlogin
ln -s /bin/bash /usr/bin/bash
make install
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
