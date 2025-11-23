"""
Ryu controller (learning switch + monitor) cho bài Lab 4 - Câu 2.

Chức năng:
- Học địa chỉ MAC (SimpleSwitch13).
- Định kỳ gửi Flow/Port Stats Request tới mọi switch và in kết quả ra console.
- Chu kỳ poll có thể chỉnh bằng biến môi trường POLL_INTERVAL (mặc định 10 giây).

Chạy:
    ryu-manager q2_monitor.py
"""

import os
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, DEAD_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.lib import hub
from ryu.lib.packet import packet, ethernet, ether_types
from ryu.ofproto import ofproto_v1_3


class SimpleMonitor13(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.datapaths = {}
        self.flow_stats = {}
        self.port_stats = {}

        # Chu kỳ gửi request (giây), có thể override bằng biến môi trường.
        self.poll_interval = float(os.getenv("POLL_INTERVAL", "10"))

        # Luồng monitor chạy song song.
        self.monitor_thread = hub.spawn(self._monitor)

    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def _state_change_handler(self, ev):
        dp = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            if dp.id not in self.datapaths:
                self.logger.info("Register datapath: %016x", dp.id)
                self.datapaths[dp.id] = dp
        elif ev.state == DEAD_DISPATCHER:
            if dp.id in self.datapaths:
                self.logger.info("Unregister datapath: %016x", dp.id)
                del self.datapaths[dp.id]

    def _monitor(self):
        while True:
            for dp in list(self.datapaths.values()):
                self._request_stats(dp)
            hub.sleep(self.poll_interval)

    def _request_stats(self, datapath):
        ofp = datapath.ofproto
        parser = datapath.ofproto_parser

        self.logger.info("Send stats request to dp %016x", datapath.id)

        req_flow = parser.OFPFlowStatsRequest(datapath)
        datapath.send_msg(req_flow)

        req_port = parser.OFPPortStatsRequest(datapath, 0, ofp.OFPP_ANY)
        datapath.send_msg(req_port)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # Flow table miss: gửi về controller.
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

    def add_flow(self, datapath, priority, match, actions, buffer_id=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        if buffer_id:
            mod = parser.OFPFlowMod(
                datapath=datapath,
                buffer_id=buffer_id,
                priority=priority,
                match=match,
                instructions=inst,
            )
        else:
            mod = parser.OFPFlowMod(
                datapath=datapath,
                priority=priority,
                match=match,
                instructions=inst,
            )
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match["in_port"]

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        # Bỏ LLDP để tránh loop.
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        dst = eth.dst
        src = eth.src
        dpid = datapath.id
        self.mac_to_port.setdefault(dpid, {})

        # Học MAC nguồn.
        self.mac_to_port[dpid][src] = in_port

        # Tìm cổng ra.
        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            out_port = ofproto.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]

        # Thêm flow để giảm tải controller khi đã biết đích.
        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst, eth_src=src)
            if msg.buffer_id != ofproto.OFP_NO_BUFFER:
                self.add_flow(datapath, 1, match, actions, msg.buffer_id)
                return
            self.add_flow(datapath, 1, match, actions)

        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=data,
        )
        datapath.send_msg(out)

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def flow_stats_reply_handler(self, ev):
        datapath = ev.msg.datapath
        body = ev.msg.body
        self.flow_stats[datapath.id] = body

        self.logger.info("Flow stats for dp %016x:", datapath.id)
        for stat in sorted(
            [f for f in body if f.priority == 1],
            key=lambda f: (f.match.get("in_port", 0), f.match.get("eth_dst", "")),
        ):
            self.logger.info(
                " in_port=%s dst=%s packets=%d bytes=%d duration=%ds",
                stat.match.get("in_port"),
                stat.match.get("eth_dst"),
                stat.packet_count,
                stat.byte_count,
                stat.duration_sec,
            )

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def port_stats_reply_handler(self, ev):
        datapath = ev.msg.datapath
        body = ev.msg.body
        self.port_stats[datapath.id] = body

        self.logger.info("Port stats for dp %016x:", datapath.id)
        for stat in sorted(body, key=lambda s: s.port_no):
            self.logger.info(
                " port=%d rx-pkts=%d tx-pkts=%d rx-bytes=%d tx-bytes=%d rx-drops=%d tx-drops=%d",
                stat.port_no,
                stat.rx_packets,
                stat.tx_packets,
                stat.rx_bytes,
                stat.tx_bytes,
                stat.rx_dropped,
                stat.tx_dropped,
            )
