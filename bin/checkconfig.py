# -*- coding: utf-8 -*-

import sys, os
import traceback
from os.path import isfile
sys.path.append('../lib')
import yaml

def loadconfig(path):
	if not isfile(path):
		print "[FATAL] can't find config file %s !" % path
		exit(1)
	f = open(path, 'r')
	x = yaml.load(f)
	f.close
	return x

def checkDnsMainConfig(c):
	if c['dnsforward_port'] not in range(1, 65536):
		print "[FATAL] dnsforward_port out of range."
		return False
	for ip in c['dnsforward_ip']:
		boollist = map(lambda x: -1<x<256,map(int,ip.split('.')))
		if len(boollist) != 4 or not all(boollist):
			print "[FATAL] dnsforward_ip config error"
			return False
	print "[INFO] 'dns MAIN' configuration check succ"
	return True

def checkAmapConfig(c):
	for url,ref in c.items():
		#must have 'default' and 'ttl' in every url
		if ref['default'] and "" == ref['default']:
			print "[FATAL] default value is Null"
			return False
		int(ref['ttl'])
		for rl,ip in ref.items():
			if rl in ['default', 'ttl']:
				continue
			if (len(rl.split(',')) != 4):
				print "[FATAL] bucket ip refer error"
				return False
	print "[INFO] 'A' configuration check succ"
	return True

def checkNSmapConfig(c):
	for url,ref in c.items():
		#must have 'record' and 'ttl' in every url
		ref['record']
		int(ref['ttl'])
	print "[INFO] 'NS' configuration check succ"
	return True

def checkSOAmapConfig(c):
	for url,ref in c.items():
		#must have 'record' and 'ttl' in every url
		ref['record']
		ref['email']
		ref['serial']
		int(ref['refresh'])
		int(ref['retry'])
		int(ref['expire'])
		int(ref['ttl'])
	print "[INFO] 'SOA' configuration check succ"
	return True

def checkIPList(ipfile):
	''' 判断ip列表是否有重合的部分 '''
	iphash = {}
	iplist = []
	f = open(ipfile, 'r')
	for eachline in f:
		ipstart, ipend, country, province, city, sp = eachline.strip().split(',')
		ipstart = long(ipstart)
		ipend = long(ipend)
		if ipstart > ipend:
			print "[ERROR] ip starts(%s) bigger than ends(%s)" %(ipstart, ipend)
			return False
		if 0 == ipstart:
			print "[ERROR] ip starts with 0"
			return False
		if ipstart in iphash:
			print "[ERROR] ip起始点重合：start（%s），end（%s）" % (ipstart, ipend)
			return False
		iplist.append(ipstart)
		iphash[ipstart] = ipend
	iplist.sort()
	i = 0
	length = len(iplist) - 1
	while i < length:
		if iphash[iplist[i]] >= iplist[i + 1]:
			print "[ERROR] ip有重合，start(%s),end(%s)和start(%s),end(%s)" % \
					( iplist[i], iphash[iplist[i]], iplist[i+1], iphash[iplist[i+1]])
			return False
		i += 1
	print "[INFO] 'IP.CSV' configuration check succ"
	return True

def checkconfig():
	#main config
	try:
		conf = loadconfig('../conf/sdns.yaml')
		if not checkDnsMainConfig(conf):
			return False
		
		#dns record config file
		Amapping = loadconfig(conf['AFILE'])
		NSmapping = loadconfig(conf['NSFILE'])
		SOAmapping = loadconfig(conf['SOAFILE'])
		if not checkAmapConfig(Amapping) or not checkNSmapConfig(NSmapping) or not checkSOAmapConfig(SOAmapping):
			return False
		if not checkIPList("../data/ip.csv"):
			return False
		return True
	except:
		print traceback.print_exc()
		return False

if __name__ == '__main__':
	print "[INFO] start check configuration"
	if not checkconfig():
		print "\x1b[1;31m[FATAL] check configuration failed.\x1b[0m"
		sys.exit(1)
	print "[INFO] check configuration done, all ok."
