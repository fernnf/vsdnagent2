import logging
from uuid import uuid4

from ryu import cfg
from ryu.base.app_manager import RyuApp
from ryu.lib.ovs.vsctl import VSCtl

import openflow as ofctl
import ovsdb as ovsctl

opts = (cfg.StrOpt("ovsdb_controller", default="tcp:127.0.0.1:6641"),
        cfg.StrOpt("transport_switch", default="tswitch0"),
        cfg.StrOpt("openflow_controller", default="tcp:127.0.0.1:6653"))

cfg.CONF.register_opts(opts)

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


class OvsdbController(object):
    logger = logging.getLogger("OvsdbController")

    def __init__(self, db):
        self.__ovsdb = VSCtl(db)
        self.__status = False

    def set_status(self, v):
        self.__status = v

    def get_status(self):
        return self.__status

    def get_dpid(self, br_name):
        assert self.get_status(), "the ovsdb connection is not working"
        return ovsctl.get_dpid(self.__ovsdb, br_name)

    def get_portnum(self, v):
        assert self.get_status(), "the ovsdb connection is not working"
        return ovsctl.get_port_num(self.__ovsdb, v)

    def br_exist(self, name):
        assert self.get_status(), "the ovsdb connection is not working"
        return ovsctl.bridge_exist(self.__ovsdb, name)

    def add_br(self, name, dpid=None, protocols=None):
        assert self.get_status(), "the ovsdb connection is not working"
        ovsctl.create_bridge(self.__ovsdb, name, dpid, protocols)

    def rem_br(self, name):
        assert self.get_status(), "the ovsdb connection is not working"
        ovsctl.remove_bridge(self.__ovsdb, name)

    def add_port(self, br_name, port_name, peer_name=None, type=None, ofport=None):
        assert self.get_status(), "the ovsdb connection is not working"
        return ovsctl.create_port(self.__ovsdb, br_name, port_name, peer_name, type, ofport)

    def rem_port(self, br_name, port_name):
        assert self.get_status(), "the ovsdb connection is not working"
        ovsctl.delete_port(self.__ovsdb, br_name, port_name)


class OpenflowController(object):
    logger = logging.getLogger("OpenFlowController")

    def __init__(self, dp):
        self.__dp = dp
        self.__status = False

    def get_status(self):
        return self.__status

    def set_status(self, v):
        self.__status = v
        self.logger.info("the openflow switch on ({i})".format(i=self.__status))

    def add_link(self, tport, vport, type, **kwargs):
        assert self.get_status(), "the openflow connection is not working"
        if type is "vlan":
            vid = kwargs.get("vlan_id", None)
            if vid is None:
                raise ValueError("The vlan id cannot be null")
            return ofctl.add_vlan_link(self.__dp, tport, vport, vid)
        else:
            self.logger.error("The type link value is unknown")

    def rem_link(self, tport, vport, type, **kwargs):
        assert self.get_status(), "the openflow connection is not working"
        if type is "vlan":
            vid = kwargs.get("vlan_id", None)
            if vid is None:
                raise ValueError("The vlan id cannot be null")
            return ofctl.rem_vlan_link(self.__dp, tport, vport, vid)
        else:
            self.logger.error("The type link value is unknown")


class VSwitchManager(RyuApp):
    logger = logging.getLogger("VSwitchManager")

    def __init__(self, *_args, **_kwargs):
        super(VSwitchManager, self).__init__(*_args, **_kwargs)

        self.vswitch = {}
        self.ovsdb = OvsdbController(self.CONF.ovsdb_controller)
        self.openflow = OpenflowController(self.CONF.openflow_controller)

    def create_vswitch(self, name, dpid, protocols):

        def add():
            self.ovsdb.add_br(name, dpid, protocols)
            self.logger.info(
                "New virtual switch ({s}) dpid ({d}) has created".format(s=name, d=self.ovsdb.get_dpid(name)))

        def register():
            vswitch = vswitch_default.copy()
            vswitch["name"] = name
            vswitch["dpid"] = (dpid if dpid is not None else self.ovsdb.get_dpid(name))
            vswitch["protocols"] = protocols
            self.vswitch.update({name: vswitch})

        if not self.ovsdb.br_exist(name):
            try:
                add()
                register()
                return [(True, None)]
            except Exception as ex:
                self.logger.error(ex)
                return [(False, ex)]
        else:
            self.logger.error("the vswitch already has exist")
            return [(False, "the vswitch already has exist")]

    def count_vswitch(self):
        return len(self.vswitch)

    def delete_vswitch(self, name):

        def rem():
            self.ovsdb.rem_br(name)
            self.logger.info(
                "the virtual switch ({s}) dpid ({d}) has removed".format(s=name, d=self.ovsdb.get_dpid(name)))

    def add_port(self, name, vswitch_name, vport_num, tport_num, type):
        pass

    def del_port(self, vswitch_name, vport_num):
        pass
