# -*- coding: utf-8 -*-

# version
__version__='1.0.1.1'

import sys, os
import signal
import time
from os.path import isfile
sys.path.append('../lib')
import yaml

from logger import SLogger
logger = SLogger.init_logger("../log/access_dns.log")

# setup epoll reactor @PZ
from twisted.internet import epollreactor
epollreactor.install()
from twisted.internet import reactor

from twisted.names import dns, server, client, cache, common, resolve
from twisted.application import service, internet
from twisted.internet.protocol import DatagramProtocol
from twisted.python import failure
from twisted.internet import defer, interfaces
from zope.interface import implements

sys.path.append('ippool.py')
sys.path.append('dnsserver.py')
import ippool, dnsserver

def loadconfig(path):
	if not isfile(path):
		print "[FATAL] can't find config file %s !" % path
		exit(1)
	f = open(path, 'r')
	x = yaml.load(f)
	f.close
	return x

def get_local_ip():
	import sys,socket,fcntl,array,struct
	is_64bits = sys.maxsize > 2**32
	struct_size = 40 if is_64bits else 32
	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	max_possible = 8 # initial value
	while True:
		bytes = max_possible * struct_size
		names = array.array('B', '\0' * bytes)
		outbytes = struct.unpack('iL', fcntl.ioctl(
			s.fileno(),
			0x8912,  # SIOCGIFCONF
			struct.pack('iL', bytes, names.buffer_info()[0])
		))[0]
		if outbytes == bytes:
			max_possible *= 2
		else:
			break
	namestr = names.tostring()
	return [(namestr[i:i+16].split('\0', 1)[0],
		socket.inet_ntoa(namestr[i+20:i+24]))
		for i in range(0, outbytes, struct_size)]

def prepare_run(run_env):
	#load main config
	logger.info('start to load conf/sdns.yaml ......')
	conf = loadconfig('../conf/sdns.yaml')

	#load dns record config file
	logger.info('start to init IP pool ......')
	Finder = ippool.IPPool(conf['IPDATA'], conf['AFILE'])
	run_env['finder'] = Finder

	logger.info('start to load A,SOA,NS record ......')
	Amapping = loadconfig(conf['AFILE'])
	NSmapping = loadconfig(conf['NSFILE'])
	SOAmapping = loadconfig(conf['SOAFILE'])

	# set up a resolver that uses the mapping or a secondary nameserver
	dnsforward = []
	for i in conf['dnsforward_ip']:
		dnsforward.append((i, conf['dnsforward_port']))

	for ifc,ip in get_local_ip():
		# create the protocols
		SmartResolver = dnsserver.MapResolver(Finder, Amapping, NSmapping, SOAmapping, servers=dnsforward)
		f = dnsserver.SmartDNSFactory(caches=[cache.CacheResolver()], clients=[SmartResolver])
		p = dns.DNSDatagramProtocol(f)
		f.noisy = p.noisy = False
		run_env['tcp'].append([f,ip])
		run_env['udp'].append([p,ip])

def run_server(run_env):
	for e in run_env['tcp']:
		run_env['readers'].append(reactor.listenTCP(53, e[0], interface=e[1]))
	for e in run_env['udp']:
		run_env['readers'].append(reactor.listenUDP(53, e[0], interface=e[1]))

# sets uy the application
application = service.Application('sdns', 0, 0)

env = {'udp':[], 'tcp':[], 'readers':[], 'closed':0, 'updated': False, 'finder':None}
prepare_run(env)
run_server(env)

# run it through twistd!
if __name__ == '__main__':
    print "Usage: twistd -y %s" % sys.argv[0]
