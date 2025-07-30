# /usr/bin/env python3

from mininet.topo import Topo


class CustomTopology(Topo):
    def build(self, k=3, n=6):
        """
        k: number of switches
        n: number of hosts per switch
        """

        # Adding switches
        for switch in range(1, k+1):
            self.addSwitch(f"s{switch}")

        # Adding hosts
        for host in range(1, (n * k) + 1):
            self.addHost(f"h{host}")

        # For each switch, add hosts
        group_counter = 1
        for switch in range(1, k+1):
            for host in range(group_counter, n + group_counter):
                self.addLink(f"s{switch}", f"h{host}")
            group_counter += n

        # Connect the switches
        for switch in range(1, k+1):
            if switch < k:
                self.addLink(f"s{switch}", f"s{switch + 1}")


topos = {"custom": CustomTopology}
