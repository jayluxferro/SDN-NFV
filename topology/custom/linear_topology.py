# /usr/bin/env python3

from mininet.topo import Topo


class LinearTopology(Topo):
    def build(self, k=2, n=2):
        """
        k: number of switches
        n: number of hosts per switch
        """

        # Adding switches
        for switch in range(1, k+1):
            self.addSwitch(f"s{switch}")

        # Adding hosts
        for host in range(1, n+1):
            self.addSwitch(f"h{host}")

        # Adding links
        self.addLink("s1", "s2")
        self.addLink("h1", "s1")
        self.addLink("h2", "s2")


topos = {"linear": LinearTopology}
