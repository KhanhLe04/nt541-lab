from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, DEAD_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, ether_types
from ryu.lib import hub


class SimpleSwitchMonitor(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(SimpleSwitchMonitor, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.datapaths = {}
        self.statistics_interval = 10
        self.monitor_thread = hub.spawn(self._monitor_loop)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

    def add_flow(self, datapath, priority, match, actions, buffer_id=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]
        if buffer_id:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,
                                    priority=priority, match=match,
                                    instructions=inst)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    match=match, instructions=inst)
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        if ev.msg.msg_len < ev.msg.total_len:
            self.logger.debug("packet truncated: only %s of %s bytes",
                              ev.msg.msg_len, ev.msg.total_len)
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return
        dst = eth.dst
        src = eth.src
        dpid = datapath.id
        self.mac_to_port.setdefault(dpid, {})
        self.mac_to_port[dpid][src] = in_port
        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            out_port = ofproto.OFPP_FLOOD
        actions = [parser.OFPActionOutput(out_port)]
        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst, eth_src=src)
            if msg.buffer_id != ofproto.OFP_NO_BUFFER:
                self.add_flow(datapath, 1, match, actions, msg.buffer_id)
                return
            else:
                self.add_flow(datapath, 1, match, actions)
        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data
        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                  in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)

    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def _switch_state_handler(self, ev):
        dp = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            self.datapaths[dp.id] = dp
            self.logger.info("Switch connected: %s", dp.id)
        elif ev.state == DEAD_DISPATCHER:
            if dp.id in self.datapaths:
                del self.datapaths[dp.id]
                self.logger.info("Switch disconnected: %s", dp.id)

    def _monitor_loop(self):
        while True:
            for dp in self.datapaths.values():
                self._request_stats(dp)
            hub.sleep(self.statistics_interval)

    def _request_stats(self, datapath):
        parser = datapath.ofproto_parser
        ofp = datapath.ofproto
        datapath.send_msg(parser.OFPFlowStatsRequest(datapath))
        datapath.send_msg(parser.OFPPortStatsRequest(datapath, 0, ofp.OFPP_ANY))

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def _flow_stats_reply_handler(self, ev):
        dpid = ev.msg.datapath.id
        flows = [s for s in ev.msg.body if s.priority != 0]
        lines = []
        lines.append("=" * 66)
        lines.append(f"Flow Statistics for Switch: {dpid:016x}")
        lines.append("-" * 66)
        lines.append(f"{'in-port':<10}{'eth-dst':<22}{'packets':>10}{'bytes':>12}{'duration (s)':>14}")
        lines.append("-" * 66)
        for stat in sorted(flows, key=lambda s: (s.match.get("in_port", 0), s.match.get("eth_dst", ""))):
            in_port = stat.match.get("in_port", "-")
            eth_dst = stat.match.get("eth_dst", "-")
            duration = stat.duration_sec + stat.duration_nsec / 1e9
            lines.append(
                f"{in_port!s:<10}{eth_dst:<22}{stat.packet_count:>10}{stat.byte_count:>12}{duration:>14.2f}"
            )
        lines.append("-" * 66)
        self.logger.info("\n".join(lines))

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def _port_stats_reply_handler(self, ev):
        dpid = ev.msg.datapath.id
        lines = []
        lines.append("=" * 66)
        lines.append(f"Port Statistics for Switch: {dpid:016x}")
        lines.append("-" * 66)
        lines.append(f"{'Port':<8}|{'Rx-Pkts':>10}|{'Rx-Bytes':>12}|{'Tx-Pkts':>10}|{'Tx-Bytes':>12}|{'Errors':>8}")
        lines.append("-" * 66)
        for stat in sorted(ev.msg.body, key=lambda s: s.port_no):
            port_label = "LOCAL" if stat.port_no == ofproto_v1_3.OFPP_LOCAL else str(stat.port_no)
            errors = stat.rx_errors + stat.tx_errors
            lines.append(
                f"{port_label:<8}|{stat.rx_packets:>10}|{stat.rx_bytes:>12}|"
                f"{stat.tx_packets:>10}|{stat.tx_bytes:>12}|{errors:>8}"
            )
        lines.append("-" * 66)
        self.logger.info("\n".join(lines))