# -*- coding: utf-8 -*-
import sys, os
import random
import re
import time
import inspect
from logger import logger
sys.path.append('../lib')
from twisted.names import dns, server, client, cache, common, resolve
from twisted.python import failure
from twisted.internet import defer

typeToMethod = {
    dns.A:     'lookupAddress',
    dns.AAAA:  'lookupIPV6Address',
    dns.A6:    'lookupAddress6',
    dns.NS:    'lookupNameservers',
    dns.CNAME: 'lookupCanonicalName',
    dns.SOA:   'lookupAuthority',
    dns.MB:    'lookupMailBox',
    dns.MG:    'lookupMailGroup',
    dns.MR:    'lookupMailRename',
    dns.NULL:  'lookupNull',
    dns.WKS:   'lookupWellKnownServices',
    dns.PTR:   'lookupPointer',
    dns.HINFO: 'lookupHostInfo',
    dns.MINFO: 'lookupMailboxInfo',
    dns.MX:    'lookupMailExchange',
    dns.TXT:   'lookupText',
    dns.SPF:   'lookupSenderPolicy',

    dns.RP:    'lookupResponsibility',
    dns.AFSDB: 'lookupAFSDatabase',
    dns.SRV:   'lookupService',
    dns.NAPTR: 'lookupNamingAuthorityPointer',
    dns.AXFR:         'lookupZone',
    dns.ALL_RECORDS:  'lookupAllRecords',
}

smartType = ('lookupAddress', 'lookupAuthority')

class FailureHandler:
    def __init__(self, resolver, query, timeout, addr = None, edns = None):
        self.resolver = resolver
        self.query = query
        self.timeout = timeout
        self.addr = addr
        self.edns = edns

    def __call__(self, failure):
        # AuthoritativeDomainErrors should halt resolution attempts
        failure.trap(dns.DomainError, defer.TimeoutError, NotImplementedError)
        return self.resolver(self.query, self.timeout, self.addr, self.edns)


class MapResolver(client.Resolver):
    def __init__(self, Finder, Amapping, NSmapping, SOAmapping, servers):
        logger.info("[MapResolver] Init.");
        self.Finder = Finder
        self.Amapping = Amapping
        self.NSmapping = NSmapping
        self.SOAmapping = SOAmapping
        client.Resolver.__init__(self, servers=servers)

    def query(self, query, timeout = None, addr = None, edns = None):
        logger.info("[MapResolver] Check query type: [%s] and query name: [%s]" % (query.type, query.name))
        try:
            if typeToMethod[query.type] in smartType:
                return self.typeToMethod[query.type](str(query.name), timeout, addr, edns)
            else:
                return self.typeToMethod[query.type](str(query.name), timeout)
        except KeyError, e:
            return defer.fail(failure.Failure(NotImplementedError(str(self.__class__) + " " + str(query.type))))

    def lookupAddress(self, name, timeout = None, addr = None, edns = None):
        logger.info("[MapResolver] Lookup address name: [%s]" % (name))
        if name in self.Amapping:
            logger.info("[MapResolver] Lookup address name, found in Amapping: [%s]" % (self.Amapping[name]))
            ttl = self.Amapping[name]['ttl']
            # construct result
            def packResult( value ):
                ret = []
                add = []
                for x in value:
                    ret.append(dns.RRHeader(name, dns.A, dns.IN, ttl, dns.Record_A(x, ttl), True))

                if edns is not None:
                    if edns.rdlength > 8:
                        add.append(dns.RRHeader('', dns.EDNS, 4096, edns.ttl, edns.payload, True))
                    else:
                        add.append(dns.RRHeader('', dns.EDNS, 4096, 0, dns.Record_EDNS(None, 0), True))
                return [ret, (), add]

            result = self.Finder.FindIP2(str(addr[0]), name)
            logger.info("[MapResolver] Found ip:[%s] and its information: [%s]" % (str(addr[0]), result))
            #返回的IP数组乱序
            random.shuffle(result)
            return packResult(result)
        else:
            logger.info("[MapResolver] Lookup address name, not found in Amapping.")
            return self._lookup(name, dns.IN, dns.A, timeout)

    def lookupNameservers(self, name, timeout=None):
        logger.info("[MapResolver] Lookup name server: [%s]" % (name))
        if name in self.NSmapping:
            logger.info("[MapResolver] Lookup name server, found in NSmapping: [%s]" % (self.NSmapping[name]))
            result = self.NSmapping[name]
            ttl = result['ttl']
            record = re.split(ur',|\s+', result['record'])
            def packResultNS(value):
                ret = []
                for x in value:
                    ret.append(dns.RRHeader(name, dns.NS, dns.IN, ttl, dns.Record_NS(x, ttl), True))
                return [ret, (), ()]
            return packResultNS(record)
        else:
            logger.info("[MapResolver] Lookup name server, not found in NSmapping")
            return self._lookup(name, dns.IN, dns.NS, timeout)

    def lookupAuthority(self, name, timeout=None, addr = None, edns = None):
        logger.info("[MapResolver] Lookup authority: [%s]" % (name))
        if name in self.SOAmapping:
            logger.info("[MapResolver] Lookup authority, found in SOAmapping: [%s]" % (self.SOAmapping[name]))
            result = self.SOAmapping[name]
            add = []
            def packResultSOA(value):
                if edns is not None:
                    if edns.rdlength > 8:
                        add.append(dns.RRHeader('', dns.EDNS, 4096, edns.ttl, edns.payload, True))
                    else:
                        add.append(dns.RRHeader('', dns.EDNS, 4096, 0, dns.Record_EDNS(None, 0), True))

                return [(dns.RRHeader(name, dns.SOA, dns.IN, value['ttl'], dns.Record_SOA(value['record'], value['email'], value['serial'], value['refresh'], value['retry'], value['expire'], value['ttl']), True),),
                    (),
                    add
                ]
            ret = packResultSOA(result)
            logger.info("SOA\t[domain: %s]\t[return: %s]\t[additional: %s]" % \
                (name, result, add))
            return ret
        else:
            logger.info("[MapResolver] Lookup authority, not found in SOAmapping.")
            return self._lookup(name, dns.IN, dns.SOA, timeout)

    def lookupIPV6Address(self, name, timeout = None, addr = None):
        logger.info("[MapResolver] Lookup IPV6 address, not implemented yet.")
        return [(),(),()]

    def lookupCanonicalName(self, name, timeout = None, addr = None):
        logger.info("[MapResolver] Lookup Canonical name, not implemented yet.")
        return [(), (), ()]

class SmartResolverChain(resolve.ResolverChain):

    def __init__(self, resolvers):
        logger.info("[SmartResolverChain] Init.")
        #resolve.ResolverChain.__init__(self, resolvers)
        common.ResolverBase.__init__(self)
        self.resolvers = resolvers

    def _lookup(self, name, cls, type, timeout, addr = None, edns = None):
        logger.info("[SmartResolverChain] _lookup with name: [%s], cls: [%s], type: [%s], timeout: [%s]" % (name, cls, type, timeout))
        q = dns.Query(name, type, cls)
        #d = self.resolvers[0].query(q, timeout)
        d = defer.fail(failure.Failure(dns.DomainError(name)))
        for r in self.resolvers[1:]:
            d = d.addErrback(
                FailureHandler(r.query, q, timeout, addr, edns)
            )
        return d

    def query(self, query, timeout = None, addr = None, edns = None):
        logger.info("[SmartResolverChain] query with query: [%s]" % (query))
        try:
            if typeToMethod[query.type] in smartType:
                return self.typeToMethod[query.type](str(query.name), timeout, addr, edns)
            else:
                return self.typeToMethod[query.type](str(query.name), timeout)
        except KeyError, e:
            return defer.fail(failure.Failure(NotImplementedError(str(self.__class__) + " " + str(query.type))))

    def lookupAddress(self, name, timeout = None, addr = None, edns = None):
        return self._lookup(name, dns.IN, dns.A, timeout, addr, edns)

    def lookupAuthority(self, name, timeout=None, addr = None, edns = None):
        return self._lookup(name, dns.IN, dns.SOA, timeout, addr, edns)

    def lookupIPV6Address(self, name, timeout = None, addr = None, edns = None):
        return self._lookup(name, dns.IN, dns.AAAA, timeout, addr, edns)

    def lookupNameservers(self, name, timeout = None, addr = None, edns = None):
        return self._lookup(name, dns.IN, dns.NS, timeout, addr, edns)

class SmartDNSFactory(server.DNSServerFactory):
    def handleQuery(self, message, protocol, address):
        logger.info("[SmartDNSFactory] handleQuery with message: [%s], protocol: [%s] and address: [%s]" % (message.queries[0], protocol, address));
        #if len(message.additional) > 0:
        #    print inspect.getmembers(message.additional[0]
        # 可以支持多个query
        query = message.queries[0]
        edns = None
        cliAddr = address
        if query.type == 43 or typeToMethod[query.type] == 'lookupAllRecords':
            return [(),(),()]
        if typeToMethod[query.type] in smartType and \
                    len(message.additional) != 0 and \
                    message.additional[0].type == 41 \
                    and message.additional[0].rdlength > 8:
                cliAddr = (message.additional[0].payload.dottedQuad(), 0)
                edns = message.additional[0]
        logger.info("[type: %s]\t[protocol: %s]\t[query: %s]\t[address: %s]\t[dns_server_addr: %s]\t[additional: %s]" % (typeToMethod[query.type], type(protocol), query, cliAddr[0], address[0], edns))

        return self.resolver.query(query, addr = cliAddr, edns = edns).addCallback(
                self.gotResolverResponse, protocol, message, address
            ).addErrback(
                self.gotResolverError, protocol, message, address
            )

    def __init__(self, authorities = None, caches = None, clients = None, verbose = 0):
        logger.info("[SmartDNSFactory] Init.")
        resolvers = []
        if authorities is not None:
            resolvers.extend(authorities)
        if caches is not None:
            resolvers.extend(caches)
        if clients is not None:
            resolvers.extend(clients)

        self.canRecurse = not not clients
        self.resolver = SmartResolverChain(resolvers)
        self.verbose = verbose
        if caches:
            self.cache = caches[-1]
        self.connections = []
