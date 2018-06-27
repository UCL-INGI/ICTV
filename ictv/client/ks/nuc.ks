#version=DEVEL
# System authorization information
auth --enableshadow --passalgo=sha512
# Use Belnet FTP
url --mirrorlist="https://mirrors.fedoraproject.org/mirrorlist?repo=fedora-25&arch=x86_64"
# Use graphical install
graphical
# Run the Setup Agent on first boot
firstboot --enable
ignoredisk --only-use=sda
# Keyboard layouts
keyboard --vckeymap=be-oss --xlayouts='be (oss)'
# System language
lang en_GB.UTF-8

# Network information
network  --bootproto=dhcp --device=enp3s0 --ipv6=auto --activate
network  --hostname=localhost.localdomain
# Root password
rootpw --iscrypted {root_password}
# System services
services --enabled="chronyd"
# System timezone
timezone Europe/Brussels --isUtc
# System bootloader configuration
bootloader --location=mbr --boot-drive=sda
autopart --type=lvm
# Partition clearing information
clearpart --all --initlabel --drives=sda

%packages
@^minimal-environment
chrony

%end

%addon com_redhat_kdump --disable --reserve-mb='128'

%end

%anaconda
pwpolicy root --minlen=0 --minquality=1 --notstrict --nochanges --emptyok
pwpolicy user --minlen=0 --minquality=1 --notstrict --nochanges --emptyok
pwpolicy luks --minlen=0 --minquality=1 --notstrict --nochanges --emptyok
%end

%post
curl -L -s {ictv_root_url}/client/ks/post_install.sh | bash -s {ictv_root_url} "{authorized_keys}" &> /root/post_install.log
%end