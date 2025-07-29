# /usr/bin/env python3

from mininet.topo import Topo


class LinearTopology(Topo):
    def build(self):
        """
        k: number of switches
        n: number of hosts per switch
        """

        # Adding links
        self.addLink("s1", "s2")
        self.addLink("h1", "s1")
        self.addLink("h2", "s1")
