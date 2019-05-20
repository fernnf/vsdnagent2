import logging

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
from ryu.lib.ofctl_utils import str_to_int

supported_ofctl = {
    ofproto_v1_0.OFP_VERSION: ofctl_v1_0,
    ofproto_v1_2.OFP_VERSION: ofctl_v1_2,
    ofproto_v1_3.OFP_VERSION: ofctl_v1_3,
    ofproto_v1_4.OFP_VERSION: ofctl_v1_4,
    ofproto_v1_5.OFP_VERSION: ofctl_v1_5
}


def __mod_flow(dp, flow, cmd):
    cmd_supported = {
        "add": dp.ofproto.OFPFC_ADD,
        "modify": dp.ofproto.OFPFC_MODIFY,
        "modify_strict": dp.ofproto.OFPFC_MODIFY_STRICT,
        "delete": dp.ofproto.OFPFC_DELETE,
        "delete_strict": dp.ofproto.OFPFC_DELETE_STRICT
    }

    mod_cmd = cmd_supported.get(cmd, None)

    if mod_cmd is None:
        raise ValueError("command not found")

    ofctl = supported_ofctl.get(dp.ofproto.OFP_VERSION)

    ofctl.mod_flow_entry(dp, flow, mod_cmd)


def __get_match(**matchs):
    mtch = {}
    data = {}
    for k, v in matchs.items():
        data[k] = v

    mtch["match"] = data

    return mtch.copy()


def __get_actions(*actions):
    act = {}
    data = []

    for v in actions:
        data.append(v)

    act["actions"] = data

    return act.copy()


def __get_flow(match, actions, **attr):
    flow = {}

    for k, v in attr.items():
        flow[k] = v

    flow.update(match)
    flow.update(actions)

    return flow.copy()


def __vlan_link(dp, tport, vport, vlan, cmd):
    def link_ingress():
        match = __get_match(in_port=tport, vlan_vid=vlan)
        actions = __get_actions({"type": "POP_VLAN"},
                                {"type": "OUTPUT", "port": vport})
        flow = __get_flow(match, actions, flag=0)

        __mod_flow(dp=dp, flow=flow, cmd=cmd)

    def link_egress():
        match = __get_match(in_port=vport)
        actions = __get_actions({"type": "PUSH_VLAN", "ethertype": 33024},
                                {"type": "SET_FIELD", "field": "vlan_vid", "value": (int(vlan) + 0x1000)},
                                {"type": "OUTPUT", "port": tport})
        flow = __get_flow(match, actions, flag=1)

        __mod_flow(dp=dp, flow=flow, cmd=cmd)

    link_egress()
    link_ingress()
    return True


def add_vlan_link(dp, tport, vport, vlan_id):
    return __vlan_link(dp, tport, vport, vlan_id, cmd="add")


def rem_vlan_link(dp, tport, vport, vlan_id):
    return __vlan_link(dp, tport, vport, vlan_id, cmd="delete_strict")
