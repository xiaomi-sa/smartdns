#!/bin/bash
. ../../smartdns_env/bin/activate
PYTHON="python"
TWISTD="../script/twistd"
cd ../bin
$PYTHON checkconfig.py || { echo "[FATAL]配置检查失败，取消重启"; exit 1; }
chmod a+r ../conf/sdns.pid &>/dev/null
pid=`cat ../conf/sdns.pid 2>/dev/null`
kill ${pid}
while ps -p ${pid} &>/dev/null; do
	sleep 1
done
$PYTHON $TWISTD -y sdns.py -l ../log/sdns.log --pidfile=../conf/sdns.pid 
