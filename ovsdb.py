from ryu.lib.ovs.vsctl import VSCtlCommand, VSCtl


def __run_command(db, cmd, args):
    command = VSCtlCommand(cmd, args)
    db.run_command([command])
    return command.result


def __get_ovs_attr(db, table, record, column, key=None):
    if key is not None:
        column = "{c}:{k}".format(c=column, k=key)

    return __run_command(db, "get", [table, record, column])


def __set_ovs_attr(db, table, record, column, value, key=None):
    if key is not None:
        column = "{c}:{k}".format(c=column, k=key)

    return __run_command(db, "set", [table, record, "{c}={v}".format(c=column, v=value)])


def get_dpid(db, bridge):
    return __get_ovs_attr(db, "Bridge", bridge, "datapath_id")[0]


def bridge_exist(db, bridge):
    return __run_command(db, "br-exists", [bridge])


def get_port_num(db, port_name):
    return __get_ovs_attr(db, "Interface", port_name, "ofport")[0]


def get_controller(db, bridge):
    return __run_command(db, "get-controller", [bridge])[0]


def set_controller(db, bridge, controller):
    ret = __run_command(db, "set-controller", [bridge, controller])

    if ret is not None:
        raise ValueError("Cannot set controller to bridge")

def get_name(db, dpid):

    return __run_command(db, "find", ["Bridge", "datapath_id={d}".format(d=dpid)])[0].name



def create_bridge(db, name, **kwargs):
    assert (name is not None), "The bridge name cannot be null"

    dpid = kwargs.get("dpid", None)
    protocols = kwargs.get("protocols", None)

    if bridge_exist(db, name):
        raise ValueError("The bridge name already exists")

    ret = __run_command(db, "add-br", [name])

    if ret is not None:
        raise ValueError(ret[0])

    if dpid is not None:
        ret = __set_ovs_attr(db, "Bridge", name, "other_config", dpid, "datapath-id")
        if ret is not None:
            raise ValueError(ret[0])
    if protocols is not None:
        assert (isinstance(protocols, list)), "the protocols must be a list object"
        ptr = ".".join(protocols)
        ret = __set_ovs_attr(db, "Bridge", name, "protocols", ptr)
        if ret is not None:
            raise ValueError(ret[0])


def remove_bridge(db, name):
    assert (name is not None), "The bridge name cannot be null"

    if not bridge_exist(db, name):
        raise ValueError("The bridge does not exist")

    ret = __run_command(db, "del-br", [name])
    if ret is not None:
        raise ValueError(ret)


def create_port(db, name, bridge, **kwargs):
    assert (name is not None), "The port name cannot be null"

    peer_name = kwargs.get("peer_name", None)
    type = kwargs.get("type", None)
    ofport = kwargs.get("ofport", None)

    if not bridge_exist(db, bridge):
        raise ValueError("The bridge does not exist")

    ret = __run_command(db, "add-port", [bridge, name])
    if ret is not None:
        raise ValueError(ret)

    if type is not None:
        if type is "patch":
            port = __set_ovs_attr(db, "Interface", name, "type", type)
            if port is not None:
                raise ValueError(port)

            if peer_name is not None:
                peer = __set_ovs_attr(db, "Interface", name, "options", peer_name, "peer")
                if peer is not None:
                    raise ValueError(peer)
            else:
                raise ValueError("the peer_name is necessary with patch port")
        else:
            raise ValueError("type is not valid")

    if ofport is not None:
        of = __set_ovs_attr(db, "Interface", name, "ofport_request", ofport)
        if of is not None:
            raise ValueError(of)


def delete_port(db, bridge, name):
    assert (name is not None), "The port name cannot be null"

    if not bridge_exist(db, bridge):
        raise ValueError("The bridge does not exist")

    ret = __run_command(db, "del-port", [bridge, name])
    if ret is not None:
        raise ValueError(ret)


def count_ports(db, bridge):
    ret = __run_command(db, "list-ifaces", [bridge])
    return len(ret)

