# /usr/bin/env python3

from mininet.topo import Topo


class LinearTopology(Topo):
    def build(self):
        """
        k: number of switches
        n: number of hosts per switch
        """

        # Adding switches
        self.addSwitch("s1")
        self.addSwitch("s2")

        # Adding hosts
        self.addHost("h1")
        self.addHost("h2")

        # Adding links
        self.addLink("s1", "s2")
        self.addLink("h1", "s1")
        self.addLink("h2", "s2")


topos = {"linear": LinearTopology}
