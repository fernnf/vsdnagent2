from ryu.ofproto import ofproto_v1_3, ofproto_v1_3_parser


proto = ofproto_v1_3
parser = ofproto_v1_3_parser

cmd_supported = {
    "add": proto.OFPFC_ADD,
    "modify": proto.OFPFC_MODIFY,
    "modify_strict": proto.OFPFC_MODIFY_STRICT,
    "delete": proto.OFPFC_DELETE,
    "delete_strict": proto.OFPFC_DELETE_STRICT
}


def __send_mod(dp, out_port, match, inst, cmd):
    cookie = cookie_mask = 0
    table_id = 0
    idle_timeout = hard_timeout = 0
    priority = 0
    buffer_id = proto.OFP_NO_BUFFER
    out_group = proto.OFPG_ANY
    flags = 0

    req = parser.OFPFlowMod(dp, cookie, cookie_mask, table_id,
                            cmd, idle_timeout, hard_timeout, priority,
                            buffer_id, out_port, out_group, flags,
                            match, inst)
    return dp.send_msg(req)


def link_vlan(dp, in_port, out_port, vlan_id, cmd):
    mod_cmd = cmd_supported.get(cmd, None)

    if mod_cmd is None:
        raise ValueError("Command not found")

    def ingress():
        actions = [parser.OFPActionPopVlan(),
                   parser.OFPActionOutput(port=int(out_port))]
        inst = [parser.OFPInstructionActions(proto.OFPIT_APPLY_ACTIONS, actions)]
        match = parser.OFPMatch(in_port=int(in_port), vlan_vid=(int(vlan_id) + 0x1000))

        return __send_mod(dp, int(out_port), match, inst, mod_cmd)



    def egress():
        ethertype = 33024

        match = parser.OFPMatch(in_port=int(out_port))
        actions = [parser.OFPActionPushVlan(ethertype),
                   parser.OFPActionSetField(vlan_vid=(int(vlan_id) + 0x1000)),
                   parser.OFPActionOutput(port=int(in_port))]

        ints = [parser.OFPInstructionActions(proto.OFPIT_APPLY_ACTIONS, actions)]

        return __send_mod(dp, int(in_port), match, ints, mod_cmd)

    return egress() and ingress()


def add_vlan_link(dp, in_port, out_port, vlan_id):
    return link_vlan(dp, in_port, out_port, vlan_id, cmd="add")


def rem_vlan_link(dp, tport, vport, vlan_id):
    return link_vlan(dp, tport, vport, vlan_id, cmd="delete")
