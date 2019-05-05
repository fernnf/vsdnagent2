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

logger = logging.getLogger("Openflow")

supported_ofctl = {
    ofproto_v1_0.OFP_VERSION: ofctl_v1_0,
    ofproto_v1_2.OFP_VERSION: ofctl_v1_2,
    ofproto_v1_3.OFP_VERSION: ofctl_v1_3,
    ofproto_v1_4.OFP_VERSION: ofctl_v1_4,
    ofproto_v1_5.OFP_VERSION: ofctl_v1_5
}


class OpenflowController(RyuApp):

    def __init__(self, *_args, **_kwargs):
        super(OpenflowController, self).__init__(*_args, **_kwargs)
        self.is_live = False

    @property
    def is_live(self):
        return self.__is_live

    @is_live.setter
    def is_live(self, value):
        self.__is_live = value

    @property
    def openflow(self):
        return self.__openflow

    @openflow.setter
    def openflow(self, value):
        self.__openflow = value

    @set_ev_cls(event.EventSwitchEnter)
    def __switch_enter(self, ev):
        self.openflow = ev.switch.dp
        self.is_live = True
        logger.info(
            "Transport Switch DPID ({id}) configured to OpenFlow Controller".format(id=dpid_to_str(self.openflow.id)))

    @set_ev_cls(event.EventSwitchLeave)
    def _switch_leave(self, ev):
        self.is_live = False
        self.openflow = None
        logger.info("The openflow switch ({v}) is disconnected".format(v=dpid_to_str(ev.switch.dp.id)))

    def __mod_flow(self, dp, flow, cmd):
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

    def _vlan_link(self, dp, tport, vport, vlan, cmd):

        def link_ingress():
            match = self.__get_match(in_port=tport, vlan_vid=vlan)
            actions = self.__get_actions({"type": "POP_VLAN"},
                                         {"type": "OUTPUT", "port": vport})
            flow = self.__get_flow(match, actions, flag=0)
            self.__mod_flow(dp=dp, flow=flow, cmd=cmd)

        def link_egress():
            match = self.__get_match(in_port=vport)
            actions = self.__get_actions({"type": "PUSH_VLAN", "ethertype": 33024},
                                         {"type": "SET_FIELD", "field": "vlan_vid", "value": (int(vlan) + 0x1000)},
                                         {"type": "OUTPUT", "port": tport})
            flow = self.__get_flow(match, actions, flag=1)
            self.__mod_flow(dp=dp, flow=flow, cmd=cmd)

        try:
            link_egress()
            link_ingress()
            logger.info("New virtual port encap vlan")
            return True
        except Exception as ex:
            logger.error(ex)
            return False

    def virtual_link(self, tport, vport, type_encap, cmd, **kwargs):
        if type_encap is "vlan":
            vlan_id = kwargs.get("vlan_id")

            if vlan_id is None:
                raise ValueError("vlan_id is not configured")

            return self._vlan_link(self.openflow, tport, vport, vlan_id, cmd)
