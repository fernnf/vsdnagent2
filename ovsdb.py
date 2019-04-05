import logging

from ryu import cfg
from ryu.base.app_manager import RyuApp
from ryu.controller.handler import set_ev_cls
from ryu.services.protocols.ovsdb import event
from ryu.services.protocols.ovsdb import api as ovsapi

from ryu.lib.ovs.vsctl import VSCtl, VSCtlCommand

opts = (cfg.StrOpt("ovsport", default="6640"),
        cfg.StrOpt("transport_switch", default="tswitch0"))

cfg.CONF.register_opts(opts)

logger = logging.getLogger("ovsdb-controller")


class OvsdbController (RyuApp):

    def __init__(self, *_args, **_kwargs):
        super(OvsdbController, self).__init__(*_args, **_kwargs)
        logger.info("Initializing vSDNAgent ...")
        self.__systemid = None
        self.__transdpid = None

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

    @set_ev_cls(event.EventNewOVSDBConnection)
    def new_ovsdb_conn(self, ev):
        self.is_live = True
        self.system_id = str(ev.system_id).replace("-", "")
        self.ovsdb = VSCtl("tcp:{ip}:{port}".format(ip=ev.client.address[0], port=self.CONF.ovsport))
        name_sw = self.CONF.transport_switch

        if self.bridge_exist(name_sw):
            print(self.get_dpid(name_sw))
        else:
            logger.error("The transport bridge is not exist")

        logger.info("new network element connected ({id}) from {ip}".format(id=self.system_id, ip=ev.client.address[0]))

    def get_dpid(self, bridge):
        assert self.is_live, "The OVSDB is not working"
        ret = self.__get_ovs_attr("Bridge", bridge, "datapath_id")
        return ret[0]

    def bridge_exist(self, bridge):
        assert self.is_live, "The OVSDB is not working"
        ret = self.__run_command("br-exists", [bridge])
        return ret[0]

    def __run_command(self, cmd, args):
        command = VSCtlCommand(cmd, args)
        self.ovsdb.run_command([command])
        return command.result

    def __get_ovs_attr(self, table, record, column, key=None):
        if key is not None:
            column = "{c}:{k}".format(c=column, k=key)
        if self.is_live:
            ret = self.__run_command("get", [table, record, column])
            return ret[0]
        else:
            raise ConnectionError("The OVSDB is not available")

    def __set_ovs_attr(self, table, record, column, value, key=None):
        if key is not None:
            column = "{c}:{k}".format(c=column, k=key)
        if self.is_live:
            self.__run_command("set", [table, record, "{c}={v}".format(c=column, v=value)])
        else:
            raise ConnectionError("The OVSDB is not available")








