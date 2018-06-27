xset s off -dpms
rm -f .config/chromium/SingletonLock
sed -i 's/"exited_cleanly":false/"exited_cleanly":true/' ~/.config/chromium/'Local State'
sed -i 's/"exited_cleanly":false/"exited_cleanly":true/; s/"exit_type":"[^"]\+"/"exit_type":"Normal"/' ~/.config/chromium/Default/Preferences
pkill -f 'python3 cache_daemon.py'
sleep 15
python3 cache_daemon.py &
exec chromium-browser file:///home/ictv/static/bootstrap.html --start-fullscreen --window-size=1920,1080 --window-position=0,0 --allow-file-access-from-files --noerrdialogs --bwsi --disable-infobars --disable-dinosaur-easter-egg --no-first-run --alsa-output-device=plughw:0,3 --enable-logging --proxy-server=localhost --proxy-bypass-list=localhost,127.0.0.1,::1
