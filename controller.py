# The program implements a simple controller for a network with 6 hosts and 5 switches.
# The switches are connected in a diamond topology (without vertical links):
#    - 3 hosts are connected to the left (s1) and 3 to the right (s5) edge of the diamond.
# Overall operation of the controller:
#    - default routing is set in all switches on the reception of packet_in messages form the switch,
#    - then the routing for (h1-h4) pair in switch s1 is changed every one second in a round-robin manner to load balance the traffic through switches s3, s4, s2. 

from audioop import avg
from cgi import print_arguments
from webbrowser import get
from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.util import dpidToStr
from pox.lib.addresses import IPAddr, EthAddr
from pox.lib.packet.arp import arp
from pox.lib.packet.ethernet import ethernet, ETHER_BROADCAST
from pox.lib.packet.packet_base import packet_base
from pox.lib.packet.packet_utils import *
import pox.lib.packet as pkt
from pox.lib.recoco import Timer
import time
import datetime

 
log = core.getLogger()
 
s1_dpid=0
s2_dpid=0
s3_dpid=0
s4_dpid=0
s5_dpid=0
 
s1_p1=0
s1_p4=0
s1_p5=0
s1_p6=0
s2_p1=0
s3_p1=0
s4_p1=0
 
pre_s1_p1=0
pre_s1_p4=0
pre_s1_p5=0
pre_s1_p6=0
pre_s2_p1=0
pre_s3_p1=0
pre_s4_p1=0

s2_load=0
s3_load=0
s4_load=0

OWD = [0.0, 0.0, 0.0, 0.0]

mytimer=0
mytimer2=0

intent_value = 100 
intent_value_list = [300, 140, 200]

delay2_array = []
delay3_array = []
delay4_array = []

delay_s2 = 0
delay_s3 = 0
delay_s4 = 0

possible_flows=[]

def getTime():
  return time.time() * 1000 * 10

def sendProbePackets():
  global start_time
  
  f = myproto()
  e = pkt.ethernet()
  e.src = EthAddr("1:0:0:0:0:0")
  e.dst = EthAddr("2:0:0:0:0:0")
  e.type=0x5577
  msg = of.ofp_packet_out()
  msg.actions.append(of.ofp_action_output(port=4))
  f.timestamp = int(getTime() - start_time)
  e.payload = f
  msg.data = e.pack()
  core.openflow.getConnection(s1_dpid).send(msg)

  f = myproto()
  e = pkt.ethernet()
  e.src = EthAddr("1:0:0:0:0:0")
  e.dst = EthAddr("3:0:0:0:0:0")
  e.type=0x5577
  msg = of.ofp_packet_out()
  msg.actions.append(of.ofp_action_output(port=5))
  f.timestamp = int(getTime() - start_time)
  e.payload = f
  msg.data = e.pack()
  core.openflow.getConnection(s1_dpid).send(msg)

  f = myproto()
  e = pkt.ethernet()
  e.src = EthAddr("1:0:0:0:0:0")
  e.dst = EthAddr("4:0:0:0:0:0")
  e.type=0x5577
  msg = of.ofp_packet_out()
  msg.actions.append(of.ofp_action_output(port=6))
  f.timestamp = int(getTime() - start_time)
  e.payload = f
  msg.data = e.pack()
  core.openflow.getConnection(s1_dpid).send(msg)
  
def search_for_possible_flows(delay_s2, delay_s3, delay_s4):
  global intent_value, possible_flows
  global s2_dpid, s3_dpid, s4_dpid
  possible_flows = []
  
  if delay_s2 < intent_value:
    possible_flows.append(s2_dpid)
  if delay_s3 < intent_value:
    possible_flows.append(s3_dpid)
  if delay_s4 < intent_value:
    possible_flows.append(s4_dpid)
 
class myproto(packet_base):
  #My Protocol packet struct
  """
  myproto class defines our special type of packet to be sent all way along including the link between the switches to measure link delays;
  it adds member attribute named timestamp to carry packet creation/sending time by the controller, and defines the 
  function hdr() to return the header of measurement packet (header will contain timestamp)
  """
   #For more info on packet_base class refer to file pox/lib/packet/packet_base.py

  def __init__(self):
    packet_base.__init__(self)
    self.timestamp=0

  def hdr(self, payload):
    return struct.pack('!I', self.timestamp) # code as unsigned int (I), network byte order (!, big-endian - the most significant byte of a word at the smallest memory address)

def _handle_ConnectionDown (event):
  global mytimer, mytimer2
  print "ConnectionDown: ", dpidToStr(event.connection.dpid)
  mytimer.cancel()
  mytimer2.cancel()

#In the following, event.connection.dpid identifies the switch the message has been received from.

def _handle_ConnectionUp (event):
  # waits for connections from all switches, after connecting to all of them it starts a round robin timer for triggering h1-h4 routing changes
  global s1_dpid, s2_dpid, s3_dpid, s4_dpid, s5_dpid
  global mytimer, mytimer2
  #print "ConnectionUp: ",dpidToStr(event.connection.dpid)
 
  #remember the connection dpid for the switch
  for m in event.connection.features.ports:
    if m.name == "s1-eth1":
      # s1_dpid: the DPID (datapath ID) of switch s1;
      s1_dpid = event.connection.dpid
      print "s1_dpid=", s1_dpid
    elif m.name == "s2-eth1":
      s2_dpid = event.connection.dpid
      print "s2_dpid=", s2_dpid
    elif m.name == "s3-eth1":
      s3_dpid = event.connection.dpid
      print "s3_dpid=", s3_dpid
    elif m.name == "s4-eth1":
      s4_dpid = event.connection.dpid
      print "s4_dpid=", s4_dpid
    elif m.name == "s5-eth1":
      s5_dpid = event.connection.dpid
      print "s5_dpid=", s5_dpid
 
  # start 1-second recurring loop timer for round-robin routing changes; _timer_func is to be called on timer expiration to change the flow entry in s1
  if s1_dpid<>0 and s2_dpid<>0 and s3_dpid<>0 and s4_dpid<>0 and s5_dpid<>0:
    mytimer = Timer(3, _timer_func, recurring=True)
    mytimer2 = Timer(0.3, load_balance, recurring=True)

def _handle_portstats_received (event):
  #Observe the handling of port statistics provided by this function.

  global s1_dpid, s2_dpid, s3_dpid, s4_dpid, s5_dpid
  global s1_p1, s1_p4, s1_p5, s1_p6, s2_p1, s3_p1, s4_p1
  global pre_s1_p1, pre_s1_p4, pre_s1_p5, pre_s1_p6, pre_s2_p1, pre_s3_p1, pre_s4_p1
  global s2_load, s3_load, s4_load

  global OWD, start_time, sent_time1, sent_time2, sent_time3, sent_time4

  received_time = getTime() - start_time

  if event.connection.dpid==s1_dpid:
    OWD[0]=0.5*(received_time - sent_time1)
    
    for f in event.stats:
      if int(f.port_no)<65534:
        if f.port_no==1:
          pre_s1_p1=s1_p1
          s1_p1=f.rx_packets
        if f.port_no==4:
          pre_s1_p4=s1_p4
          s1_p4=f.tx_packets
        if f.port_no==5:
          pre_s1_p5=s1_p5
          s1_p5=f.tx_packets
        if f.port_no==6:
          pre_s1_p6=s1_p6
          s1_p6=f.tx_packets

  if event.connection.dpid==s2_dpid:
    OWD[1]=0.5*(received_time - sent_time2)
    for f in event.stats:
      if int(f.port_no)<65534:
        if f.port_no==1:
          pre_s2_p1=s2_p1
          s2_p1=f.rx_packets
    s2_load = s1_p4-pre_s1_p4
    print "s2_load:", s2_load
    s2_load = 0
 
  if event.connection.dpid==s3_dpid:
    OWD[2]=0.5*(received_time - sent_time3)
    for f in event.stats:
      if int(f.port_no)<65534:
        if f.port_no==1:
          pre_s3_p1=s3_p1
          s3_p1=f.rx_packets
    s3_load = s1_p5-pre_s1_p5
    print "s3_load:", s3_load
    s3_load = 0

  if event.connection.dpid==s4_dpid:
    OWD[3]=0.5*(received_time - sent_time4)
    for f in event.stats:
      if int(f.port_no)<65534:
        if f.port_no==1:
          pre_s4_p1=s4_p1
          s4_p1=f.rx_packets
    s4_load = s1_p6-pre_s1_p6
    print "s4_load:", s4_load
    s4_load = 0
 
def _handle_PacketIn(event):
  global s1_dpid, s2_dpid, s3_dpid, s4_dpid, s5_dpid
  global delay2_array, delay3_array, delay4_array, delay_s2, delay_s3, delay_s4
  global OWD, start_time

  received_time = getTime() - start_time
  packet=event.parsed
  
  if packet.type==0x5577 and event.connection.dpid==s2_dpid: 
    c=packet.find('ethernet').payload
    d,=struct.unpack('!I', c)
    delay2 = int(received_time - d - OWD[0] - OWD[1])/10
    delay2_array.append(delay2)
    avg_size = len(delay2_array)
    if avg_size > 3:
      avg_size = 3
    delay_s2 = sum(delay2_array[-avg_size:])/avg_size
    print "s2 delay: ", delay_s2

  if packet.type==0x5577 and event.connection.dpid==s3_dpid:
    c=packet.find('ethernet').payload
    d,=struct.unpack('!I', c)
    delay3 = int(received_time - d - OWD[0] - OWD[2])/10
    delay3_array.append(delay3)
    avg_size = len(delay3_array)
    if avg_size > 3:
      avg_size = 3
    delay_s3 = sum(delay3_array[-avg_size:])/avg_size
    print "s3 delay: : ", delay_s3

  if packet.type==0x5577 and event.connection.dpid==s4_dpid:
    c=packet.find('ethernet').payload
    d,=struct.unpack('!I', c)
    delay4 = int(received_time - d - OWD[0] - OWD[3])/10
    delay4_array.append(delay4)
    avg_size = len(delay4_array)
    if avg_size > 3:
      avg_size = 3
    delay_s4 = sum(delay4_array[-avg_size:])/avg_size
    print "s4 delay: ", delay_s4

  search_for_possible_flows(delay_s2, delay_s3, delay_s4)
  
  # Below, set the default/initial routing rules for all switches and ports.
  # All rules are set up in a given switch on packet_in event received from the switch which means no flow entry has been found in the flow table.
  # This setting up may happen either at the very first pactet being sent or after flow entry expirationn inn the switch
 
  if event.connection.dpid==s1_dpid:
     a=packet.find('arp')					# If packet object does not encapsulate a packet of the type indicated, find() returns None
     if a and a.protodst=="10.0.0.4":
       msg = of.ofp_packet_out(data=event.ofp)			# Create packet_out message; use the incoming packet as the data for the packet out
       msg.actions.append(of.ofp_action_output(port=4))		# Add an action to send to the specified port
       event.connection.send(msg)				# Send message to switch
 
     if a and a.protodst=="10.0.0.5":
       msg = of.ofp_packet_out(data=event.ofp)
       msg.actions.append(of.ofp_action_output(port=5))
       event.connection.send(msg)
 
     if a and a.protodst=="10.0.0.6":
       msg = of.ofp_packet_out(data=event.ofp)
       msg.actions.append(of.ofp_action_output(port=6))
       event.connection.send(msg)
 
     if a and a.protodst=="10.0.0.1":
       msg = of.ofp_packet_out(data=event.ofp)
       msg.actions.append(of.ofp_action_output(port=1))
       event.connection.send(msg)
 
     if a and a.protodst=="10.0.0.2":
       msg = of.ofp_packet_out(data=event.ofp)
       msg.actions.append(of.ofp_action_output(port=2))
       event.connection.send(msg)
 
     if a and a.protodst=="10.0.0.3":
       msg = of.ofp_packet_out(data=event.ofp)
       msg.actions.append(of.ofp_action_output(port=3))
       event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =100
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.dl_type = 0x0800		# rule for IP packets (x0800)
     msg.match.nw_dst = "10.0.0.1"
     msg.actions.append(of.ofp_action_output(port = 1))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =100
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.dl_type = 0x0800
     msg.match.nw_dst = "10.0.0.2"
     msg.actions.append(of.ofp_action_output(port = 2))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =100
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.dl_type = 0x0800
     msg.match.nw_dst = "10.0.0.3"
     msg.actions.append(of.ofp_action_output(port = 3))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =100
     msg.idle_timeout = 0
     msg.hard_timeout = 1
     msg.match.dl_type = 0x0800
     msg.match.nw_dst = "10.0.0.4"
     msg.actions.append(of.ofp_action_output(port = 4))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =100
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.dl_type = 0x0800
     msg.match.nw_dst = "10.0.0.5"
     msg.actions.append(of.ofp_action_output(port = 5))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =100
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.dl_type = 0x0800
     msg.match.nw_dst = "10.0.0.6"
     msg.actions.append(of.ofp_action_output(port = 6))
     event.connection.send(msg)
 
  elif event.connection.dpid==s2_dpid: 
     msg = of.ofp_flow_mod()
     msg.priority =10
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.in_port = 1
     msg.match.dl_type=0x0806		# rule for ARP packets (x0806)
     msg.actions.append(of.ofp_action_output(port = 2))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =10
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.in_port = 1
     msg.match.dl_type=0x0800
     msg.actions.append(of.ofp_action_output(port = 2))
     event.connection.send(msg)
  
     msg = of.ofp_flow_mod()
     msg.priority =10
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.in_port = 2
     msg.match.dl_type=0x0806
     msg.actions.append(of.ofp_action_output(port = 1))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =10
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.in_port = 2
     msg.match.dl_type=0x0800
     msg.actions.append(of.ofp_action_output(port = 1))
     event.connection.send(msg)
 
  elif event.connection.dpid==s3_dpid: 
     msg = of.ofp_flow_mod()
     msg.priority =10
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.in_port = 1
     msg.match.dl_type=0x0806
     msg.actions.append(of.ofp_action_output(port = 2))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =10
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.in_port = 1
     msg.match.dl_type=0x0800
     msg.actions.append(of.ofp_action_output(port = 2))
     event.connection.send(msg)
  
     msg = of.ofp_flow_mod()
     msg.priority =10
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.in_port = 2
     msg.match.dl_type=0x0806
     msg.actions.append(of.ofp_action_output(port = 1))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =10
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.in_port = 2
     msg.match.dl_type=0x0800
     msg.actions.append(of.ofp_action_output(port = 1))
     event.connection.send(msg)
  
  elif event.connection.dpid==s4_dpid: 
     msg = of.ofp_flow_mod()
     msg.priority =10
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.in_port = 1
     msg.match.dl_type=0x0806
     msg.actions.append(of.ofp_action_output(port = 2))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =10
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.in_port = 1
     msg.match.dl_type=0x0800
     msg.actions.append(of.ofp_action_output(port = 2))
     event.connection.send(msg)
  
     msg = of.ofp_flow_mod()
     msg.priority =10
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.in_port = 2
     msg.match.dl_type=0x0806
     msg.actions.append(of.ofp_action_output(port = 1))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =10
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.in_port = 2
     msg.match.dl_type=0x0800
     msg.actions.append(of.ofp_action_output(port = 1))
     event.connection.send(msg)
 
  elif event.connection.dpid==s5_dpid: 
     a=packet.find('arp')
     if a and a.protodst=="10.0.0.4":
       msg = of.ofp_packet_out(data=event.ofp)
       msg.actions.append(of.ofp_action_output(port=4))
       event.connection.send(msg)
 
     if a and a.protodst=="10.0.0.5":
       msg = of.ofp_packet_out(data=event.ofp)
       msg.actions.append(of.ofp_action_output(port=5))
       event.connection.send(msg)
 
     if a and a.protodst=="10.0.0.6":
       msg = of.ofp_packet_out(data=event.ofp)
       msg.actions.append(of.ofp_action_output(port=6))
       event.connection.send(msg)
 
     if a and a.protodst=="10.0.0.1":
       msg = of.ofp_packet_out(data=event.ofp)
       msg.actions.append(of.ofp_action_output(port=1))
       event.connection.send(msg)
 
     if a and a.protodst=="10.0.0.2":
       msg = of.ofp_packet_out(data=event.ofp)
       msg.actions.append(of.ofp_action_output(port=2))
       event.connection.send(msg)
 
     if a and a.protodst=="10.0.0.3":
       msg = of.ofp_packet_out(data=event.ofp)
       msg.actions.append(of.ofp_action_output(port=3))
       event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =100
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.dl_type = 0x0800
     msg.match.nw_dst = "10.0.0.1"
     msg.actions.append(of.ofp_action_output(port = 1))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =10
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.in_port = 6
     msg.actions.append(of.ofp_action_output(port = 3))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =100
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.dl_type = 0x0800
     msg.match.nw_dst = "10.0.0.1"
     msg.actions.append(of.ofp_action_output(port = 1))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =100
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.dl_type = 0x0800
     msg.match.nw_dst = "10.0.0.2"
     msg.actions.append(of.ofp_action_output(port = 2))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =100
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.dl_type = 0x0800
     msg.match.nw_dst = "10.0.0.3"
     msg.actions.append(of.ofp_action_output(port = 3))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =100
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.dl_type = 0x0800
     msg.match.nw_dst = "10.0.0.4"
     msg.actions.append(of.ofp_action_output(port = 4))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =100
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.dl_type = 0x0800
     msg.match.nw_dst = "10.0.0.5"
     msg.actions.append(of.ofp_action_output(port = 5))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =100
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.dl_type = 0x0800
     msg.match.nw_dst = "10.0.0.6"
     msg.actions.append(of.ofp_action_output(port = 6))
     event.connection.send(msg)

def load_balance():
  global possible_flows, s1_dpid, s2_dpid, s3_dpid, s4_dpid, s5_dpid
  global s2_load, s3_load, s4_load

  selected_port = 4
  selected_load = 999999
  
  '''
  print "\n===== Flows load balance ====="
  print "s2_load: ", s2_load
  print "s3_load: ", s3_load
  print "s4_load: ", s4_load
  print "Possible flows: ", possible_flows
  print "==============================="
  '''
  
  if s2_dpid in possible_flows and s2_load < selected_load:
    selected_port = 4
    #print "Selected port: ", selected_port, " s2_load < selected_load: ", s2_load, " ", selected_load, " Flows: ", possible_flows
    selected_load = s2_load
    
  if s3_dpid in possible_flows and s3_load < selected_load:
    selected_port = 5
    #print "Selected port: ", selected_port, " s3_load < selected_load: ", s3_load, " ", selected_load, " Flows: ", possible_flows
    selected_load = s3_load
    
  if s4_dpid in possible_flows and s4_load < selected_load:
    selected_port = 6
    #print "Selected port: ", selected_port, " s4_load < selected_load: ", s4_load, " ", selected_load, " Flows: ", possible_flows
    
  if selected_port == 4:
    s2_load = s2_load + 1
  elif selected_port == 5:
    s3_load = s3_load + 1
  else:
    s4_load = s4_load + 1
    
  msg = of.ofp_flow_mod()
  msg.command=of.OFPFC_MODIFY_STRICT
  msg.priority =100
  msg.idle_timeout = 0
  msg.hard_timeout = 0
  msg.match.dl_type = 0x0800
  msg.match.nw_dst = "10.0.0.6"
  msg.actions.append(of.ofp_action_output(port = selected_port))
  core.openflow.getConnection(s1_dpid).send(msg)

def _timer_func (): 
  global s1_dpid, s2_dpid, s3_dpid, s4_dpid, s5_dpid
  global start_time, sent_time1, sent_time2, sent_time3, sent_time4, intent_value

  if s1_dpid <>0 and not core.openflow.getConnection(s1_dpid) is None:
    core.openflow.getConnection(s1_dpid).send(of.ofp_stats_request(body=of.ofp_port_stats_request()))
    sent_time1=getTime() - start_time
    sendProbePackets()

  if s2_dpid <>0 and not core.openflow.getConnection(s2_dpid) is None:
    core.openflow.getConnection(s2_dpid).send(of.ofp_stats_request(body=of.ofp_port_stats_request()))
    sent_time2=getTime() - start_time 

  if s3_dpid <>0 and not core.openflow.getConnection(s3_dpid) is None:
    core.openflow.getConnection(s3_dpid).send(of.ofp_stats_request(body=of.ofp_port_stats_request()))
    sent_time3=getTime() - start_time
    
  if s4_dpid <>0 and not core.openflow.getConnection(s4_dpid) is None:
    core.openflow.getConnection(s4_dpid).send(of.ofp_stats_request(body=of.ofp_port_stats_request()))
    sent_time4=getTime() - start_time

  print_stats()

def print_stats():
  global start_time, intent_value, possible_flows 
  current_time = getTime()

  if (current_time - start_time)/10000 >= 21 and (current_time - start_time)/10000 < 36:
    intent_value = intent_value_list[0]

  if (current_time - start_time)/10000 >= 36 and (current_time - start_time)/10000 < 51:
    intent_value = intent_value_list[1]

  if (current_time - start_time)/10000 >= 51:
    intent_value = intent_value_list[2]

  print '\n[Intent] h1 -> h4 max delay: ', intent_value, "ms" 
  print "Possible flows: ", possible_flows, "\n"

def launch ():
  global start_time
  start_time = getTime()

  core.openflow.addListenerByName("PortStatsReceived",_handle_portstats_received)
  core.openflow.addListenerByName("ConnectionUp", _handle_ConnectionUp)
  core.openflow.addListenerByName("ConnectionDown", _handle_ConnectionDown)
  core.openflow.addListenerByName("PacketIn",_handle_PacketIn)

