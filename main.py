import logging

from ryu import cfg
from ryu.base.app_manager import RyuApp
from ryu.controller.handler import set_ev_cls
from ryu.lib import ofctl_v1_0
from ryu.lib import ofctl_v1_2
from ryu.lib import ofctl_v1_3
from ryu.lib import ofctl_v1_4
from ryu.lib import ofctl_v1_5
from ryu.ofproto import ofproto_v1_0
from ryu.ofproto import ofproto_v1_2
from ryu.ofproto import ofproto_v1_3
from ryu.ofproto import ofproto_v1_4
from ryu.ofproto import ofproto_v1_5
from ryu.topology import event
from ryu.topology.switches import dpid_to_str
from ryu.controller.handler import set_ev_cls
from ryu.lib.ovs.vsctl import VSCtl, VSCtlCommand
from ryu.services.protocols.ovsdb import event

opts = (cfg.StrOpt("ovsdb_controller", default="tcp:127.0.0.1:6641"),
        cfg.StrOpt("transport_switch", default="tswitch0"),
        cfg.StrOpt("openflow_controller", default="tcp:127.0.0.1:6653"))

cfg.CONF.register_opts(opts)

supported_ofctl = {
    ofproto_v1_0.OFP_VERSION: ofctl_v1_0,
    ofproto_v1_2.OFP_VERSION: ofctl_v1_2,
    ofproto_v1_3.OFP_VERSION: ofctl_v1_3,
    ofproto_v1_4.OFP_VERSION: ofctl_v1_4,
    ofproto_v1_5.OFP_VERSION: ofctl_v1_5
}

openflow_version = {
    ofproto_v1_0.OFP_VERSION: "OpenFlow10",
    ofproto_v1_2.OFP_VERSION: "OpenFlow12",
    ofproto_v1_3.OFP_VERSION: "OpenFlow13",
    ofproto_v1_4.OFP_VERSION: "OpenFlow14",
    ofproto_v1_5.OFP_VERSION: "OpenFlow15"
}

vswitch_default = {
    "name": None,
    "dpid": None,
    "protocols": [],
    "ports": {}
}

vport_default = {
    "name": None,
    "peer": None,
    "port_num": None,
    "peer_num": None,
    "type": None,
}

logger = logging.getLogger("vsdnagent")

class OvsdbController(object):
    def __init__(self, addr):

        self.__status = True
        self.__conn = VSCtl(addr)


class VSwitchManager(RyuApp):

    def __init__(self, *_args, **_kwargs):
        super(VSwitchManager, self).__init__(*_args, **_kwargs)

        self.vswitch = {}
        self.ovsdb = None
        self.openflow = None

    def create_vswitch(self, name, dpid, protocols):
        pass

    def count_vswitch(self):
        pass

    def delete_vswitch(self, name):
        pass

    def add_port(self, name, vswitch_name, vport_num, tport_num, type):
        pass

    def del_port(self, vswitch_name, vport_num):
        pass
