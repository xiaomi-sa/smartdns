smartdns
========
## 使用场景
##### smartdns是python语言编写，基于twisted框架实现的dns server，能够支持针对不同的dns请求根据配置返回不同的解析结果。smartdns获取dns请求的源IP或者客户端IP（支持edns协议的请求可以获取客户端IP），根据本地的静态IP库获取请求IP的特性，包括所在的国家、省份、城市、ISP等，然后根据我们的调度配置返回解析结果。
##### smartdns的使用场景
1. 服务的多机房流量调度，比如电信流量调度到电信机房、联通流量调度到联通机房；
2. 用户访问控制，将用户调度到离用户最近或者链路质量最好的节点上。

##### 举个简单的例子，我们的一个站点test.test.com同时部署在电信和联通两个机房，该站点在电信机房的ip为1.1.1.1、在联通机房的ip为2.2.2.2，就可以通过smartdns做到该站点域名解析时判断源IP为电信的IP时返回1.1.1.1、判断源IP为联通的IP时返回2.2.2.2，从而达到不同运营商机房流量调度的目的。

## 支持的功能
支持A、SOA、NS记录的查询，支持DNS forward功能

## 性能
在虚拟机2.4G CPU上能够处理1000QPS查询请求，打开debug日志后可以到800QPS。3-5台dns server组成的集群已经能够满足大部分站点的需求。

目前我们正在实现和小流量测试go语言实现的smartdns，能够达到3wQPS以上，后续测试稳定后会开源出来，大家敬请期待：）

## 原理

smartdns响应dns请求的处理流程如下：

![dns请求处理流程](http://noops.me/wp-content/uploads/2013/08/dns%E8%AF%B7%E6%B1%82%E5%A4%84%E7%90%86%E6%B5%81%E7%A8%8B.png)

IPPool类的初始化和该类中FindIP方法进行解析处理是smartdns中最关键的两个要素，这两个要素在下面详细介绍。其他的特性比如继承twisted中dns相关类并重写处理dns请求的方法、升级twisted代码支持解析和处理edns请求等大家可以通过代码了解。edns知识可以猛戳这里：<a href="http://noops.me/?p=653" title="DNS support edns-client-subnet" target="_blank">DNS support edns-client-subnet</a>

#### IPPool初始化

![IPPool初始化流程](http://noops.me/wp-content/uploads/2013/08/ippool%E5%88%9D%E5%A7%8B%E5%8C%96.png)

ip.csv内容格式如下：
``200000001, 200000010,中国,陕西,西安,电信``

其中各个字段含义分别为 ``IP段起始，IP段截止，IP段所属国家，IP段所属省份，IP段所属城市，IP段所属ISP``

a.yaml配置文件格式：
<pre class="lang:default decode:true">test.test.com:
  ttl: 3600
  default: 5.5.5.5 2.2.2.2
  中国,广东,,联通: 1.1.1.1 3.3.3.1
  中国,广东,,电信: 1.1.1.2 3.3.3.2</pre>

配置中地域信息的key包括四个字段，分别带有不同的权重：
- 国家：    8
- 省份：	4
- 城市：	2
- 运营商：  1

初始化阶段，会生成一个名为iphash的dict，具体数据结构如下图：

![iphash数据结构](http://noops.me/wp-content/uploads/2013/08/iphash%E6%95%B0%E6%8D%AE%E7%BB%93%E6%9E%84.png)

其中，iphash的key为ip.csv每一条记录的起始IP，value为一个list，list长度为6，list前5个字段分别为以该key为起始IP记录的IP段截止、IP段所属国家、IP段所属省份、IP段所属城市、IP段所属ISP，第六个字段是一个hash，key为a.yaml里面配置的域名，value为长度为2的list，iphash[IP段起始][6][域名1][0]为域名1在该IP段的最优解析，iphash[IP段起始][6][域名1][1]为该最优解析的总权值，该总权值暂时只做参考。

iphash初始化过程中最关键的是iphash[IP段起始][6][域名1]的最优解析的计算，最简单直接的方式是直接遍历域名1的所有调度配置，挑选出满足条件且总权值最高的解析，即为最优解析。这种方式记录整个iphash的时间复杂度为O(xyz)，x为ip.csv记录数，y为域名总数量，z为各个域名的调度配置数。为了优化启动速度，优化了寻找最优解析的方法：事先将每个域名调度配置生成一颗树，这棵树是用dict模拟出来的，这样需要最优解的时候就不需要遍历所有调度配置，而是最多检索15次即可找到最优，即时间复杂度为O(15xy)，具体实现参考IPPool的LoadRecord和JoinIP两个方法。

有了初始化后的iphash数据结构之后，每次请求处理的时候，只需要定位请求IP处在哪个IP段，找到IP段起始IP，然后从iphash中取出最优解析，取出最优解析的过程是O(1)的。具体流程如下：

![ippool的findip方法](http://noops.me/wp-content/uploads/2013/08/ippool%E7%9A%84findip%E6%96%B9%E5%BC%8F.png)

## 代码

github： https://github.com/xiaomi-sa/smartdns

## 安装

依赖：

python 2.6或者2.7
Twisted 12.2.0
zope.interface 4.0.1

安装：

git clone smartdns到本地路径，进入script目录，执行install_smartdns.sh即可将smartdns安装在本地，同时python环境和相关的依赖都是使用virtualenv来进行管理，不会对系统环境造成影响。

启动：

进入smartdns的script路径下，执行sh run_dns.sh即可启动smartdns

## 测试

本地测试 dig test.test.com @127.0.0.1

或者将搭建的smartdns加到测试域名的ns中进行测试。

## 支持

mail: fangshaosen@xiaomi.com

github: jerryfang8

EDNS相关请参考：<a href="http://noops.me/?p=653" title="DNS support edns-client-subnet" target="_blank">DNS support edns-client-subnet</a>
