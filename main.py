import coloredlogs, logging
from uuid import uuid4

from ryu import cfg
from ryu.base.app_manager import RyuApp
from ryu.lib.ovs.vsctl import VSCtl
from ryu.controller.handler import set_ev_cls
from ryu.services.protocols.ovsdb import event as evt_ovs
from ryu.topology import event as evt_ofl
from ryu.topology.switches import dpid_to_str
from autobahn.twisted.wamp import Application

import openflow as ofctl
import ovsdb as ovsctl

opts = (cfg.StrOpt("ovsdb_controller", default="tcp:127.0.0.1:6641"),
        cfg.StrOpt("transport_switch", default="tswitch0"),
        cfg.StrOpt("openflow_controller", default="tcp:127.0.0.1:6653"))

cfg.CONF.register_opts(opts)

vswitch_default = {
    "name": None,
    "dpid": None,
    "tenant": None,
    "protocols": [],
    "vports": {}
}

vport_default = {
    "name": None,
    "peer": None,
    "port_num": None,
    "peer_num": None,
    "type": None,
}

wampapp = Application()

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

    def get_controller(self, br_name):
        assert self.get_status(), "the ovsdb connection is not working"
        return ovsctl.get_controller(self.__ovsdb, br_name)

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

    def amount_ports(self, br_name):
        assert self.get_status(), "the ovsdb connection is not working"
        return ovsctl.count_ports(self.__ovsdb, br_name)

    def set_controllers(self, br_name, ctls):
        assert self.get_status(), "the ovsdb connection is not working"
        ovsctl.set_controller(self.__ovsdb, br_name, ctls)


class OpenflowController(object):
    logger = logging.getLogger("OpenFlowController")


    def __init__(self, dp):
        self.__dp = dp
        self.__status = False

    def get_status(self):
        return self.__status

    def set_status(self, v):
        self.__status = v

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
    coloredlogs.install(logger=logger)

    def __init__(self, *_args, **_kwargs):
        super(VSwitchManager, self).__init__(*_args, **_kwargs)

        self.vswitch = {}
        self.ovsdb = OvsdbController(self.CONF.ovsdb_controller)
        self.openflow = OpenflowController(self.CONF.openflow_controller)


    def count_vswitch(self):
        return len(self.vswitch)


    def create_vswitch(self, tenant, dpid=None, protocols=None):

        def rnd_dpid():
            return str(uuid4()).replace("-", "")[:16]

        def rnd_vswitch_name():
            return "vnet{t}.{d}".format(t=tenant, d=dpid)

        if dpid is None:
            dpid = rnd_dpid()

        name = rnd_vswitch_name()

        def add():
            self.ovsdb.add_br(name, dpid, protocols)
            self.logger.info(
                "New virtual switch ({s}) dpid ({d}) has created".format(s=name, d=self.ovsdb.get_dpid(name)))

        def register():
            vswitch = vswitch_default.copy()
            vswitch["name"] = name
            vswitch["dpid"] = dpid
            vswitch["protocols"] = protocols
            vswitch["tenant"] = tenant
            self.vswitch.update({name: vswitch})

        try:
            add()
            register()
            return [(True, name)]
        except Exception as ex:
            self.logger.error(ex)
            return [(False, ex)]

    def delete_vswitch(self, name):

        def rem():
            self.ovsdb.rem_br(name)
            self.logger.info(
                "the virtual switch ({s}) dpid ({d}) has removed".format(s=name, d=self.ovsdb.get_dpid(name)))

        def unregister():
            del (self.vswitch[name])
            self.logger.info("the virtual switch ({s}) has unregistred".format(s=name))

        if self.ovsdb.br_exist(name):
            try:
                rem()
                unregister()
                return [(True, None)]
            except Exception as ex:
                return [(False, ex)]
        else:
            self.logger.info("the virtual switch ({s}) not exists".format(s=name))

    def add_vport(self, vswitch_name, tport_num, type):

        tswitch_name = self.CONF.transport_switch
        if type is "vlan":
            vid = vswitch_name.split(".")[0][4:]

        def register_vport(cfg):
            self.vswitch[vswitch_name]["vports"].update(cfg)

        def get_port_config():
            vnet = vswitch_name.split(".")[0]
            vsw_id = vswitch_name.split(".")[1]
            tsw_id = self.ovsdb.get_dpid(tswitch_name)
            vsw = self.vswitch.get(vswitch_name, None)

            if vsw is not None:
                id = len(vsw["vports"])
                vport = vport_default.copy()
                port_id = id + 1
                peer_id = id + 50
                vport["name"] = "{v}.{vd}.{td}.p{i}".format(v=vnet, vd=vsw_id, td=tsw_id, i=port_id)
                vport["peer"] = "{v}.{td}.{vd}.p{i}".format(v=vnet, vd=vsw_id, td=tsw_id, i=peer_id)
                vport["port_num"] = port_id
                vport["peer_num"] = peer_id
                vport["tport_num"] = tport_num
                vport["type"] = {type: vid}
                return vport.copy()
            else:
                raise ValueError("the vswitch not found")

        def add_link(cfg):
            ingress = self.ovsdb.add_port(br_name=tswitch_name,
                                          port_name=cfg["peer"],
                                          peer_name=cfg["name"],
                                          type="patch",
                                          ofport=cfg["peer_num"])
            if ingress is not None:
                raise ValueError(ingress)

            egress = self.ovsdb.add_port(br_name=vswitch_name,
                                         port_name=cfg["name"],
                                         peer_name=cfg["peer"],
                                         type="patch",
                                         ofport=cfg["port_num"])

            if egress is not None:
                raise ValueError(egress)

            if self.openflow.add_link(tport_num, cfg["peer_num"], "vlan", vlan_id=vid):
                self.logger.info("new port has added on vswitch {v}".format(v=vswitch_name))

        try:
            cfg = get_port_config()
            add_link(cfg)
            register_vport(cfg)
            return [(True, None)]
        except Exception as ex:
            self.logger.error(ex)
            return [(False, ex)]

    def del_vport(self, vswitch_name, vport_num):

        tswitch_name = self.CONF.transport_switch

        def unregister_port(cfg):
            del (self.vswitch[vswitch_name]["vports"][cfg])

        def get_config_port():
            vports = self.vswitch.get(vswitch_name, None)
            if vports is not None:
                for port in vports:
                    if port["port_num"] == vport_num:
                        return port

            else:
                raise ValueError("the vswitch is not registred")

        def rem_link(cfg):

            self.ovsdb.rem_port(br_name=tswitch_name, port_name=cfg["peer"])
            self.ovsdb.rem_port(br_name=vswitch_name, port_name=cfg["name"])
            ret = self.openflow.rem_link(cfg["tport_num"], cfg["peer_num"], "vlan", vlan_id=cfg["type"]["vlan"])
            if ret:
                self.logger.info("the port ({p}) has removed from vswitch {v}".format(p=cfg["name"], v=vswitch_name))

        try:
            cfg = get_config_port()
            rem_link(cfg)
            unregister_port(cfg)
            return [(True, None)]
        except  Exception as ex:
            self.logger.error(ex)
            return [(False, ex)]

    @set_ev_cls(evt_ovs.EventNewOVSDBConnection)
    def __ovsdb_connection(self, ev):
        self.ovsdb.set_status(True)
        tswitch = self.CONF.transport_switch
        self.wampapp = Application("vsdnagent.node.{d}".format(d=self.ovsdb.get_dpid(tswitch)))
        self.wampapp.session

        self.logger.info(
            "new ovsdb connection from {i} and system-id:{s} to vSDNAgent".format(i=ev.client.address[0],
                                                                                  s=ev.system_id))

        def transport_exist():
            if not self.ovsdb.br_exist(tswitch):
                self.logger.error("the transport switch is not exists, please configure a tswitch")
                return False
            else:
                ports = self.ovsdb.amount_ports(tswitch)
                self.logger.info("new transport switch was found with {f} physical ports".format(f=ports))
                return True

        def ctl_config():
            ctl = self.CONF.openflow_controller
            ctls = self.ovsdb.get_controller(tswitch)

            if ctl not in ctls:
                ctls.append(ctl)
                self.ovsdb.set_controllers(tswitch, ctls)
            else:
                self.logger.info("the transport switch already has a controller connection")

        try:
            if transport_exist():
                ctl_config()
        except Exception as ex:
            self.logger.error(ex)

    @set_ev_cls(evt_ofl.EventSwitchEnter)
    def __tswitch_connection(self, ev):
        self.openflow.set_status(True)
        self.logger.info(
            "transport switch dpid {id} has connected to vSDNAgent".format(id=dpid_to_str(ev.switch.dp.id)))
