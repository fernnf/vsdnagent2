import logging

from ryu import cfg
from ryu.base.app_manager import RyuApp
from ryu.controller.handler import set_ev_cls
from ryu.lib.ovs.vsctl import VSCtl, VSCtlCommand
from ryu.services.protocols.ovsdb import event

opts = (cfg.StrOpt("ovsport", default = "6641"),
        cfg.StrOpt("transport_switch", default = "tswitch0"))

cfg.CONF.register_opts(opts)

logger = logging.getLogger("ovsdb-controller")


class OvsdbController(RyuApp):

    def __init__(self, *_args, **_kwargs):
        super(OvsdbController, self).__init__(*_args, **_kwargs)
        logger.info("Initializing vSDNAgent ...")
        self.__systemid = None
        self.__transdpid = None
        self.__ovsdb = None

    @property
    def is_live(self):
        return self.__live

    @is_live.setter
    def is_live(self, value):
        self.__live = value

    @property
    def system_id(self):
        return self.__systemid

    @system_id.setter
    def system_id(self, value):
        self.__systemid = value

    @property
    def transport_dpid(self):
        return self.__transdpid

    @transport_dpid.setter
    def transport_dpid(self, value):
        self.__transdpid = value

    @property
    def ovsdb(self):
        return self.__ovsdb

    @ovsdb.setter
    def ovsdb(self, value):
        self.__ovsdb = VSCtl("tcp:{ip}:{port}".format(ip = value, port = self.CONF.ovsport))

    def get_dpid(self, bridge):
        assert self.is_live, "The OVSDB is not working"
        ret = self.__get_ovs_attr("Bridge", bridge, "datapath-id")
        return ret[0]

    def bridge_exist(self, bridge):
        assert self.is_live, "The OVSDB is not working"
        return self.__run_command("br-exists", [bridge])

    def create_bridge(self, name, dpid = None, protocols = None):
        assert (name is not None), "The bridge name cannot be null"
        assert self.is_live, "The OVSDB is not working"

        ret = self.__run_command("add-br", [name])
        if ret is None:
            if dpid is not None:
                self.__set_ovs_attr("Bridge", name, "other_config", dpid, "datapath-id")
            if protocols is not None:
                assert (isinstance(protocols, list)), "the protocols must be a list object"
                ptr = ",".join(protocols)
                self.__set_ovs_attr("Bridge", name, "protocols", ptr)
            return True
        else:
            raise ValueError("Cannot to create bridge")

    def remove_bridge(self, name):
        assert self.is_live, "The OVSDB is not working"
        assert (self.bridge_exist(name)), "The bridge is not exist"

        ret = self.__run_command("del-br", [name])
        if ret is None:
            return True
        else:
            raise ValueError(ret)

    def port_num(self, port_name):
        assert self.is_live, "The OVSDB is not working"
        ret = self.__get_ovs_attr("Interface", port_name, "ofport")
        return ret

    def delete_port(self, bridge_name, port_name):
        assert (bridge_name is not None), "The bridge name cannot be null"
        assert (port_name is not None), "The port name cannot be null"

        ret = self.__run_command("del-port", [bridge_name, port_name])
        if ret is None:
            return True
        else:
            raise ValueError(ret)

    def create_port(self, bridge_name, port_name, peer_name = None, type = None, ofport = None):
        assert (bridge_name is not None), "The bridge name cannot be null"
        assert (port_name is not None), "The port name cannot be null"
        assert self.is_live, "The OVSDB is not working"

        ret = self.__run_command("add-port", [bridge_name, port_name])

        if ret is None:
            if type is not None:
                if type is "patch":
                    assert (peer_name is not None), "The peer name cannot be null"
                    self.__set_ovs_attr("Interface", port_name, "type", "patch")
                    self.__set_ovs_attr("Interface", port_name, "options", peer_name, "peer")
                else:
                    raise ValueError("The port type is unknown")

            if ofport is not None:
                self.__set_ovs_attr("Interface", port_name, "ofport_request", ofport)

            return self.port_num(port_name)

        else:
            raise ValueError(ret)

    @set_ev_cls(event.EventNewOVSDBConnection)
    def __new_ovsdb_conn(self, ev):
        self.is_live = True
        self.system_id = str(ev.system_id).replace("-", "")
        self.ovsdb = ev.client.address[0]
        name_sw = self.CONF.transport_switch

        if self.bridge_exist(name_sw):
            self.transport_dpid = self.get_dpid(name_sw)
        else:
            logger.error("The transport bridge is not exist")

        logger.info(
            "new network element connected ({id}) from {ip}".format(id = self.system_id,
                                                                    ip = ev.client.address[0]))

    def __run_command(self, cmd, args):
        command = VSCtlCommand(cmd, args)
        self.ovsdb.run_command([command])
        return command.result

    def __get_ovs_attr(self, table, record, column, key = None):
        if key is not None:
            column = "{c}:{k}".format(c = column, k = key)
        if self.is_live:
            ret = self.__run_command("get", [table, record, column])
            return ret[0]
        else:
            raise ConnectionError("The OVSDB is not available")

    def __set_ovs_attr(self, table, record, column, value, key = None):
        if key is not None:
            column = "{c}:{k}".format(c = column, k = key)
        if self.is_live:
            self.__run_command("set", [table, record, "{c}={v}".format(c = column, v = value)])
            return True
        else:
            raise ConnectionError("The OVSDB is not available")
