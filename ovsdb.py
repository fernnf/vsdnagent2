import logging

from ryu.base.app_manager import RyuApp
from ryu.controller.handler import set_ev_cls
from ryu.services.protocols.ovsdb import event


logger = logging.getLogger("ovsdb-controller")


class OvsdbController (RyuApp):

    def __init__(self, *_args, **_kwargs):
        super().__init__(*_args, **_kwargs)
        logger.info("Initalized vSDNAgent ...")
        self.__systemid = None
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
    def ovsdb(self):
        return self.__ovsdb

    @ovsdb.setter
    def ovsdb(self, value):
        pass

    @set_ev_cls(event.EventNewOVSDBConnection)
    def _new_ovsdb_conn(self, ev):

        self.is_live = True
        self.system_id = str(ev.system_id).replace("-", "")
        logger.info("new network element connected ({id})".format(id=self.system_id))















