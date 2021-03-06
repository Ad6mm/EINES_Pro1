#!/usr/bin/python
 
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import CPULimitedHost
from mininet.link import TCLink
from mininet.util import dumpNodeConnections
from mininet.log import setLogLevel, info
from mininet.node import Controller 
from mininet.cli import CLI
from functools import partial
from mininet.node import RemoteController
from threading import Timer
import os

class MyTopo(Topo):
    "Single switch connected to n hosts."
    def __init__(self):
        Topo.__init__(self)

        s1=self.addSwitch('s1')
        s2=self.addSwitch('s2')
        s3=self.addSwitch('s3')
        s4=self.addSwitch('s4')
        s5=self.addSwitch('s5')

        h1=self.addHost('h1')
        h2=self.addHost('h2')
        h3=self.addHost('h3')
        h4=self.addHost('h4')
        h5=self.addHost('h5')
        h6=self.addHost('h6')

        self.addLink(h1, s1, bw=100, delay='0ms', loss=0, max_queue_size=1000, use_htb=True)
        self.addLink(h2, s1, bw=100, delay='0ms', loss=0, max_queue_size=1000, use_htb=True)
        self.addLink(h3, s1, bw=100, delay='0ms', loss=0, max_queue_size=1000, use_htb=True)
        self.addLink(s1, s2, bw=100, delay='200ms', loss=0, max_queue_size=1000, use_htb=True)
        self.addLink(s1, s3, bw=100, delay='50ms', loss=0, max_queue_size=1000, use_htb=True)
        self.addLink(s1, s4, bw=100, delay='10ms', loss=0, max_queue_size=1000, use_htb=True)
        self.addLink(s2, s5, bw=100, delay='0ms', loss=0, max_queue_size=1000, use_htb=True)
        self.addLink(s3, s5, bw=100, delay='0ms', loss=0, max_queue_size=1000, use_htb=True)
        self.addLink(s4, s5, bw=100, delay='0ms', loss=0, max_queue_size=1000, use_htb=True)
        self.addLink(s5, h4, bw=100, delay='0ms', loss=0, max_queue_size=1000, use_htb=True)
        self.addLink(s5, h5, bw=100, delay='0ms', loss=0, max_queue_size=1000, use_htb=True)
        self.addLink(s5, h6, bw=100, delay='0ms', loss=0, max_queue_size=1000, use_htb=True)

def perfTest():
   "Create network and run simple performance test"
   topo = MyTopo()
   
   net = Mininet(topo=topo, host=CPULimitedHost, link=TCLink, controller=partial(RemoteController, ip='127.0.0.1', port=6633))
   net.start()
   
   print("Dumping host connections")
   dumpNodeConnections(net.hosts)

   h1, h2, h3=net.get('h1','h2','h3')
   h4, h5, h6=net.get('h4','h5','h6')

   h1.setMAC("0:0:0:0:0:1")
   h2.setMAC("0:0:0:0:0:2")
   h3.setMAC("0:0:0:0:0:3")
   h4.setMAC("0:0:0:0:0:4")
   h5.setMAC("0:0:0:0:0:5")
   h6.setMAC("0:0:0:0:0:6")

   s1, s2, s3=net.get('s1', 's2', 's3')
   s4, s5=net.get('s4', 's5')
   
   s1.setMAC("1:0:0:0:0:0")
   s2.setMAC("2:0:0:0:0:0")
   s3.setMAC("3:0:0:0:0:0")
   s4.setMAC("4:0:0:0:0:0")
   s5.setMAC("5:0:0:0:0:0")
   
   h1.cmd('ping -i 0.1 -c 100 10.0.0.6')

   def cDelay1(): 
      info( '+++++++++++++ Setting delays 1\n' )
      s1.cmdPrint('tc qdisc del dev s1-eth4 root')
      s1.cmdPrint('tc qdisc add dev s1-eth4 root netem delay 400ms') 
      
      s1.cmdPrint('tc qdisc del dev s1-eth5 root')
      s1.cmdPrint('tc qdisc add dev s1-eth5 root netem delay 60ms') 

      s1.cmdPrint('tc qdisc del dev s1-eth6 root')
      s1.cmdPrint('tc qdisc add dev s1-eth6 root netem delay 120ms')
      h1.cmd('ping -i 0.1 -c 100 10.0.0.6')
       

   def cDelay2(): 
      info( '+++++++++++++ Setting delays 2\n' )
      s1.cmdPrint('tc qdisc del dev s1-eth4 root')
      s1.cmdPrint('tc qdisc add dev s1-eth4 root netem delay 320ms') 
      
      s1.cmdPrint('tc qdisc del dev s1-eth5 root')
      s1.cmdPrint('tc qdisc add dev s1-eth5 root netem delay 40ms') 

      s1.cmdPrint('tc qdisc del dev s1-eth6 root')
      s1.cmdPrint('tc qdisc add dev s1-eth6 root netem delay 110ms')
      h1.cmd('ping -i 0.1 -c 100 10.0.0.6')

   def cDelay3(): 
      info( '+++++++++++++ Setting delays 3\n' )
      s1.cmdPrint('tc qdisc del dev s1-eth4 root')
      s1.cmdPrint('tc qdisc add dev s1-eth4 root netem delay 230ms') 
      
      s1.cmdPrint('tc qdisc del dev s1-eth5 root')
      s1.cmdPrint('tc qdisc add dev s1-eth5 root netem delay 30ms') 

      s1.cmdPrint('tc qdisc del dev s1-eth6 root')
      s1.cmdPrint('tc qdisc add dev s1-eth6 root netem delay 90ms')
      h1.cmd('ping -i 0.1 -c 100 10.0.0.6')

   t1=Timer(21, cDelay1)
   t1.start()

   t2=Timer(36, cDelay2)
   t2.start()

   t3=Timer(51, cDelay3)
   t3.start()

   CLI(net) # launch simple Mininet CLI terminal window
   net.stop()

if __name__ == '__main__':
   setLogLevel('info')
   perfTest()