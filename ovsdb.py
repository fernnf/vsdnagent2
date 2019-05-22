from ryu.lib.ovs.vsctl import VSCtlCommand


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
    return __get_ovs_attr(db, "Bridge", bridge, "datapath_id")


def bridge_exist(db, bridge):
    return __run_command(db, "br-exists", [bridge])


def get_port_num(db, port_name):
    return __get_ovs_attr(db, "Interface", port_name, "ofport")


def get_controller(db, brdige):
    return __run_command(db, "get-controller", [brdige])


def set_controller(db, bridge, controller):
    ret = __run_command(db, "set-controller", [bridge, controller])

    if ret is not None:
        raise ValueError("Cannot set controller to bridge")


def create_bridge(db, name, dpid=None, protocols=None):
    assert (name is not None), "The bridge name cannot be null"
    assert (bridge_exist(db, name)), "The bridge already has exist "

    ret = __run_command(db, "add-br", [name])

    if ret is None:
        if dpid is not None:
            ret = __set_ovs_attr(db, "Bridge", name, "other_config", dpid, "datapath_id")
            if ret is not None:
                raise ValueError(ret)
        if protocols is not None:
            assert (isinstance(protocols, list)), "the protocols must be a list object"
            ptr = ".".join(protocols)
            ret = __set_ovs_attr(db, "Bridge", name, "protocols", ptr)
            if ret is not None:
                raise ValueError(ret)
    else:
        raise Exception("It cannot create the bridge")


def remove_bridge(db, name):
    assert (name is not None), "The bridge name cannot be null"
    assert (bridge_exist(db, name)), "The bridge is not exist"

    ret = __run_command(db, "del-br", [name])
    if ret is not None:
        raise ValueError(ret)


def create_port(db, bridge_name, port_name, peer_name=None, type=None, ofport=None):
    assert (bridge_exist(db, bridge_name)), "The bridge name cannot be null"
    assert (port_name is not None), "The port name cannot be null"

    ret = __run_command(db, "add-port", [bridge_name, port_name])
    if ret is not None:
        raise ValueError(ret)

    if type is "patch":
        assert (peer_name is not None), "The peer name cannot be null"
        port = __set_ovs_attr(db, "Interface", port_name, "type", "patch")
        if port is not None:
            raise ValueError(port)
        peer = __set_ovs_attr(db, "Interface", port_name, "options", peer_name, "peer")
        if peer is not None:
            raise ValueError(peer)

    if ofport > 0:
        cfg = __set_ovs_attr(db, "Interface", port_name, "ofport_request", ofport)
        if cfg is not None:
            raise ValueError(cfg)


def delete_port(db, bridge_name, port_name):
    assert (bridge_name is not None), "The bridge name cannot be null"
    assert (port_name is not None), "The port name cannot be null"

    ret = __run_command(db, "del-port", [bridge_name, port_name])
    if ret is not None:
        raise ValueError(ret)


def count_ports(db, bridge_name):
    assert (bridge_name is not None), "The bridge name cannot be null"
    ret = __run_command(db, "list-ifaces", [bridge_name])
    return len(ret)
