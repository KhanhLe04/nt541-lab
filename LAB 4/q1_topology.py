from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import RemoteController, OVSKernelSwitch
from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import setLogLevel, info


class Lab4RingTopo(Topo):
    """
    Topology theo hình bài 1:
    - 4 switch s1-s4 kết nối vòng (ring)
    - Mỗi switch nối 4 host, tổng 16 host
    - Link host: 10Mb, 1ms; Link switch: 20Mb, 2ms
    """

    def build(self):
        # Switches
        s1 = self.addSwitch("s1")
        s2 = self.addSwitch("s2")
        s3 = self.addSwitch("s3")
        s4 = self.addSwitch("s4")

        # Hosts cho s1
        h1 = self.addHost("h1", ip="10.0.0.1/24")
        h2 = self.addHost("h2", ip="10.0.0.2/24")
        h3 = self.addHost("h3", ip="10.0.0.3/24")
        h4 = self.addHost("h4", ip="10.0.0.4/24")

        # Hosts cho s2
        h5 = self.addHost("h5", ip="10.0.0.5/24")
        h6 = self.addHost("h6", ip="10.0.0.6/24")
        h7 = self.addHost("h7", ip="10.0.0.7/24")
        h8 = self.addHost("h8", ip="10.0.0.8/24")

        # Hosts cho s3
        h9 = self.addHost("h9", ip="10.0.0.9/24")
        h10 = self.addHost("h10", ip="10.0.0.10/24")
        h11 = self.addHost("h11", ip="10.0.0.11/24")
        h12 = self.addHost("h12", ip="10.0.0.12/24")

        # Hosts cho s4
        h13 = self.addHost("h13", ip="10.0.0.13/24")
        h14 = self.addHost("h14", ip="10.0.0.14/24")
        h15 = self.addHost("h15", ip="10.0.0.15/24")
        h16 = self.addHost("h16", ip="10.0.0.16/24")

        # Liên kết host-switch (10Mb, 1ms)
        host_link = dict(bw=10, delay="1ms")
        self.addLink(h1, s1, **host_link)
        self.addLink(h2, s1, **host_link)
        self.addLink(h3, s1, **host_link)
        self.addLink(h4, s1, **host_link)

        self.addLink(h5, s2, **host_link)
        self.addLink(h6, s2, **host_link)
        self.addLink(h7, s2, **host_link)
        self.addLink(h8, s2, **host_link)

        self.addLink(h9, s3, **host_link)
        self.addLink(h10, s3, **host_link)
        self.addLink(h11, s3, **host_link)
        self.addLink(h12, s3, **host_link)

        self.addLink(h13, s4, **host_link)
        self.addLink(h14, s4, **host_link)
        self.addLink(h15, s4, **host_link)
        self.addLink(h16, s4, **host_link)

        # Liên kết switch-switch vòng (20Mb, 2ms)
        core_link = dict(bw=20, delay="2ms")
        self.addLink(s1, s2, **core_link)
        self.addLink(s2, s3, **core_link)
        self.addLink(s3, s4, **core_link)


def run(controller_ip="127.0.0.1", controller_port=6653):
    topo = Lab4RingTopo()
    net = Mininet(
        topo=topo,
        controller=None,
        link=TCLink,
        switch=OVSKernelSwitch,
        autoSetMacs=True,
    )
    net.addController(
        "c0", controller=RemoteController, ip=controller_ip, port=controller_port
    )

    info("*** Starting network\\n")
    net.start()
    info("*** Network started; enter CLI to test (pingall, iperf, ...)\\n")
    CLI(net)
    info("*** Stopping network\\n")
    net.stop()


if __name__ == "__main__":
    setLogLevel("info")
    run()
