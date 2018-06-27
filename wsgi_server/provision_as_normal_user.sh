mkdir -p ~/.ssh
cp /vagrant/id_rsa ~/.ssh/
chmod 400 ~/.ssh/id_rsa
ssh-keyscan scm.info.ucl.ac.be >> ~/.ssh/known_hosts
