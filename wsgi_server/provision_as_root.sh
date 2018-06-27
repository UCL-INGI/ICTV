yum install -y https://centos6.iuscommunity.org/ius-release.rpm 
yum install -y git python35u python35u-pip python35u-devel ImageMagick-devel gcc httpd httpd-devel libxml2-devel libxslt libxslt-devel xmlsec1 xmlsec1-devel libtool-ltdl libtool-ltdl-devel mediainfo
yum install -y python35u-mod_wsgi.x86_64
cp /vagrant/httpd_config/httpd.conf /etc/httpd/conf/httpd.conf
cp /vagrant/httpd_config/sysconfig_httpd /etc/sysconfig/httpd
setenforce 0
cp /vagrant/selinux/sysconfig_selinux /etc/sysconfig/selinux
python3.5 -m ensurepip


# Install ICTV2
cd /var/www/
mkdir -p ~/.ssh
cp /vagrant/id_rsa ~/.ssh/
chmod 400 ~/.ssh/id_rsa
ssh-keyscan scm.info.ucl.ac.be >> ~/.ssh/known_hosts
git clone -b wsgi_compat git@scm.info.ucl.ac.be:ictv-v2.git
chown apache ictv-v2 -R
cd ictv-v2
cp configuration.example.yaml configuration.yaml
cp default_slides.example.yaml default_slides.yaml
pip3.5 install .
sudo ./ictv-setup-database
sudo chown apache ictv/database.sqlite

# Start httpd

service httpd enable
service httpd start
