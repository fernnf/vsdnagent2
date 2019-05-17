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
    def __init__(self, addr, tswitch):

        self.__status = True
        self.__conn = VSCtl(addr)
        self.__tswitch = tswitch

    def __run_command(self, cmd, args):
        command = VSCtlCommand(cmd, args)
        self.__conn.run_command([command])
        return command.result

    def __get_ovs_attr(self, table, record, column, key=None):
        if key is not None:
            column = "{c}:{k}".format(c=column, k=key)
        if self.__status:
            ret = self.__run_command("get", [table, record, column])
            return ret[0]
        else:
            raise ConnectionError("The OVSDB is not available")

    def __set_ovs_attr(self, table, record, column, value, key=None):
        if key is not None:
            column = "{c}:{k}".format(c=column, k=key)
        if self.__status:
            ret = self.__run_command("set", [table, record, "{c}={v}".format(c=column, v=value)])
            if ret is None:
                return True
            else:
                raise ValueError(ret)
        else:
            raise ConnectionError("The OVSDB is not available")

    def get_status(self):
        return self.__status

    def get_tswitch(self):
        return self.__tswitch

    def get_dpid(self, bridge):
        assert self.__status, "The OVSDB is not working"
        return self.__get_ovs_attr("Bridge", bridge, "datapath_id")

    def bridge_exist(self, bridge):
        assert self.__status, "The OVSDB is not working"
        return self.__run_command("br-exists", [bridge])

    def create_bridge(self, name, dpid=None, protocols=None):
        assert (name is not None), "The bridge name cannot be null"
        assert self.__status, "The OVSDB is not working"

        ret = self.__run_command("add-br", [name])

        if ret is None:
            if dpid is not None:
                self.__set_ovs_attr("Bridge", name, "other_config", dpid, "datapath_id")
            if protocols is not None:
                assert (isinstance(protocols, list)), "the protocols must be a list object"
                ptr = ",".join(protocols)
                self.__set_ovs_attr("Bridge", name, "protocols", ptr)
            return True
        else:
            raise ValueError("Cannot to create bridge")

    def remove_bridge(self, name):
        assert self.__status, "The OVSDB is not working"
        assert (self.bridge_exist(name)), "The bridge is not exist"

        ret = self.__run_command("del-br", [name])
        if ret is None:
            return True
        else:
            raise ValueError(ret)

    def get_port_num(self, port_name):
        assert self.__status, "The OVSDB is not working"
        return self.__get_ovs_attr("Interface", port_name, "ofport")

    def delete_port(self, bridge_name, port_name):
        assert (bridge_name is not None), "The bridge name cannot be null"
        assert (port_name is not None), "The port name cannot be null"

        ret = self.__run_command("del-port", [bridge_name, port_name])
        assert (ret is None), "{err}".format(err=ret)

        return True

    def create_port(self, bridge_name, port_name, peer_name=None,type=None,ofport=None):
        assert (bridge_name is not None), "The bridge name cannot be null"
        assert (port_name is not None), "The port name cannot be null"

        assert self.__status, "The OVSDB is not working"
        ret = self.__run_command("add-port", [bridge_name, port_name])

        assert (ret is None), "{err}".format(err=ret)

        if ofport > 0:
            self.__set_ovs_attr("Interface", port_name, "ofport_request", ofport)
        else:
            raise ValueError("Value Unsupported")

        if type is "patch":
            assert (peer_name is not None), "The peer name cannot be null"
            self.__set_ovs_attr("Interface", port_name, "type", "patch")
            self.__set_ovs_attr("Interface", port_name, "options", peer_name, "peer")

        return self.get_port_num(port_name)


class OpenflowController(object):
    def __init__(self, dp):
        self.__dp = dp
        self.__status = False

    def __mod_flow(self, flow, cmd):
        cmd_supported = {
            "add": self.__dp.ofproto.OFPFC_ADD,
            "modify": self.__dp.ofproto.OFPFC_MODIFY,
            "modify_strict": self.__dp.ofproto.OFPFC_MODIFY_STRICT,
            "delete": self.__dp.ofproto.OFPFC_DELETE,
            "delete_strict": self.__dp.ofproto.OFPFC_DELETE_STRICT
        }

        mod_cmd = cmd_supported.get(cmd, None)

        if mod_cmd is None:
            raise ValueError("command not found")

        ofctl = supported_ofctl.get(self.__dp.ofproto.OFP_VERSION)
        ofctl.mod_flow_entry(self.__dp, flow, mod_cmd)

    def __get_match(self, **matchs):
        mtch = {}
        data = {}
        for k, v in matchs.items():
            data[k] = v

        mtch["match"] = data

        return mtch.copy()

    def __get_actions(self, *actions):
        act = {}
        data = []

        for v in actions:
            data.append(v)

        act["actions"] = data

        return act.copy()

    def __get_flow(self, match, actions, **attr):
        flow = {}

        for k, v in attr.items():
            flow[k] = v

        flow.update(match)
        flow.update(actions)

        return flow.copy()

    def __vlan_link(self, tport, vport, vlan, cmd):

        def egress():
            match = self.__get_match(in_port=tport, vlan_vid=vlan)
            actions = self.__get_actions({"type": "POP_VLAN"},
                                         {"type": "OUTPUT", "port": vport})
            flow = self.__get_flow(match, actions, flag=0)
            self.__mod_flow(flow=flow, cmd=cmd)

        def ingress():
            match = self.__get_match(in_port=vport)
            actions = self.__get_actions({"type": "PUSH_VLAN", "ethertype": 33024},
                                         {"type": "SET_FIELD", "field": "vlan_vid", "value": (int(vlan) + 0x1000)},
                                         {"type": "OUTPUT", "port": tport})
            flow = self.__get_flow(match, actions, flag=1)
            self.__mod_flow(flow=flow, cmd=cmd)

        if self.__status:
            egress()
            ingress()
            return True
        else:
            raise ValueError("The openflow switch cannot be reach")

    def add_link(self, tport, vport, encap, cmd, **kwargs):

        if encap is "vlan":
            vlan_id = kwargs.get("vlan_id")


    def get_status(self):
        return self.__status



class VSwitchManager(RyuApp):

    def __init__(self, *_args, **_kwargs):
        super(VSwitchManager, self).__init__(*_args, **_kwargs)

        self.vswitch = {}
        self.ovsdb = OvsdbController(self.CONF.ovsdb_controller, self.CONF.transport_switch)
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
