
class DriverOvs(object):

    def __init__(self, ovsdb, ofctl):
        self.__db = ovsdb
        self.__of = ofctl

    def add_switch(self, name, **kwargs):

        return



    def add_port(self, name, sw_name, **kwargs):
        pass

    def del_switch(self, name):
        pass

    def del_port(self, name, sw_name, **kwargs):
        pass
