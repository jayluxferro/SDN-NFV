# Custom Mininet Topologies

## Running Custom Topologies

```bash
sudo mn --custom [python_file.py] --topo [topology_key] --mac --controller=remote,127.0.0.1,port=6653 --switch ovs,protocols=OpenFlow13
```
