#!/usr/bin/env python

import os

import geni.portal as portal
import geni.rspec.pg as pg
import geni.rspec.igext as ig
import geni.rspec.emulab.pnext as pn
import geni.rspec.emulab as emulab


tourDescription = """
### srsRAN 5G Handover using the Programmable Attenuator Matrix

This profile instantiates a 5G network with srsRAN and Open5GS on POWDER in a conducted RF evironment with programmable attenuators for emulating handover scenarios.

The following will be deployed:
- Open5GS CN node (Dell R430)
- srsRAN CU/DU node (Dell R740 + USRP X310 w/ 2x UBX-160 daughter cards)
  - the two daughter cards will be used for separate DU/RU pairs and intra-gNB handover
- UL monitoring node (Dell R430 + USRP N300)
- 2 UE nodes (Intel NUC w/ COTS UE)

"""

tourInstructions = """

Startup scripts will still be running when your experiment becomes ready. Watch the "Startup" column on the "List View" tab for your experiment and wait until all of the compute nodes show "Finished" before proceeding.

Once the experiment is ready, you can log into the Open5GS CN node (`cn5g`) and monitor the AMF and SMF logs:

```
# on the cn5g node
sudo journalctl -u open5gs-amfd -u open5gs-smfd -f --output cat
```

Next, in a session on the srsRAN Project CU/DU node (`cudu`), start the srsRAN
gNB:

```
# on the cudu node
sudo numactl --membind 0 --cpubind 0 \
  /var/tmp/srsRAN_Project/build/apps/gnb/gnb -c /var/tmp/etc/srsran/gnb_rf_x310_ho.yml
```

In a session on the `ue1` node, start the UE connection manager with the target DNN `internet` in `ipv4` mode:

```
# on the ue node
sudo quectel-CM -s internet -4
```

In aother session on the `ue1` node, bring the COTS UE out of airplane mode:

```
# on the ue node
/local/repository/bin/module-on.sh
```

At this point the UE should attach to the gNB via the first DU/RU pair. (This profile initializes the state of the programmable attenuators such that the paths between DU/RU 1 and the COTS UE have the minimum attenuation, while the paths terminating at DU/RU 2 have the maximum attenuation.) The physical cell ID (PCI) for this DU/RU pair is 1, as indicated in the output of the srsRAN gNB process...

```
# output of srsran gnb process on cudu node
          |--------------------DL---------------------|-------------------------UL------------------------------
 pci rnti | cqi  ri  mcs  brate   ok  nok  (%)  dl_bs | pusch  rsrp  mcs  brate   ok  nok  (%)    bsr    ta  phr
   1 4604 |  15   1   27   4.8k    5    0   0%      0 |  37.5  -5.0   28    17k    4    0   0%      0   0us   24
   1 4604 |  15   1   28   4.2k    4    0   0%      0 |  37.9  -5.0   28    13k    3    0   0%      0   0us   24
   1 4604 |  15   1   27   4.8k    5    0   0%      0 |  35.8  -4.9   28    17k    4    0   0%      0   0us   24
   1 4604 |  15   1   27   4.8k    5    0   0%      0 |  36.8  -5.1   28    17k    4    0   0%      0   0us   24
   1 4604 |  15   1   27   4.8k    5    0   0%      0 |  36.3  -5.0   28    22k    5    0   0%      0   0us   24
```

In a session on the `ue1` node, start a ping process pointed at the core network UPF, so we can verify that traffic still passes throughout the handover process:

```
# on ue node
ping 10.45.0.1
```

Now that there is some traffic being generated, lets trigger an intra-gNB handover by incrementally adjusting the attenuations such that the paths between DU/RU 1 and the UE become more attenuated, while the paths terminating at CU/DU 2 become less attenuated, eventully resulting in a higher quality channel between the UE and DU/RU 2. You can use the included helper script to do this:

```
# on any node in the experiment
/local/repository/bin/handover ue1 ru2
```

You should see the PCI for the attached UE change to 2 in the output of the gNB process, indicating a handover to DU/RU...

```
          |--------------------DL---------------------|-------------------------UL------------------------------
 pci rnti | cqi  ri  mcs  brate   ok  nok  (%)  dl_bs | pusch  rsrp  mcs  brate   ok  nok  (%)    bsr    ta  phr
   2 5601 |  15   1   27   4.7k    5    0   0%      0 |  35.9  -3.0   28    17k    4    0   0%      0   n/a   24
   2 5601 |  15   1   27   4.7k    5    0   0%      0 |  36.5  -4.0   28    17k    4    0   0%      0   n/a   24
   2 5601 |  15   1   27   4.7k    5    0   0%      0 |  37.0  -4.0   28    17k    4    0   0%      0   n/a   24
   2 5601 |  15   1   27   4.7k    5    0   0%      0 |  36.6  -4.0   28    17k    4    0   0%      0   n/a   24
   2 5601 |  15   1   27   4.7k    5    0   0%      0 |  37.0  -4.0   28    17k    4    0   0%      0   n/a   24
   2 5601 |  15   1   27   4.7k    5    0   0%      0 |  36.4  -4.0   28    17k    4    0   0%      0   n/a   24
```

...while the ping traffic continues uninterrupted. You can trigger a handover back to DU/RU #1 if you like:

```
# on any node in the experiment
/local/repository/bin/handover ue1 ru1
```

The `uemncmp` node and acompanying SDR is included to allow for, e.g.:

- realtime monitoring of 5G transmissions
- injecting interference in the DL path
- recording samples of UL transmissions for data gathering purposes

GnuRadio and UHD tools are installed on this nodes.


"""

BIN_PATH = "/local/repository/bin"
ETC_PATH = "/local/repository/etc"
UBUNTU_IMG = "urn:publicid:IDN+emulab.net+image+emulab-ops//UBUNTU22-64-STD"
COTS_UE_IMG = "urn:publicid:IDN+emulab.net+image+PowderTeam:cots-jammy-image"
COMP_MANAGER_ID = "urn:publicid:IDN+emulab.net+authority+cm"
DEFAULT_SRSRAN_HASH = "release_25_10"
OPEN5GS_DEPLOY_SCRIPT = os.path.join(BIN_PATH, "deploy-open5gs.sh")
SRSRAN_DEPLOY_SCRIPT = os.path.join(BIN_PATH, "deploy-srsran.sh")
NODE_IDS = {
    "sdru": "x310-1",
    "uemon": "n300-2",
    "ue1": "nuc27",
    "ue2": "nuc22",
}
MATRIX_GRAPH = {
    "sdru": ["ue1", "ue2"],
    "uemon": ["ue1", "ue2"],
    "ue1": ["sdru", "uemon"],
    "ue2": ["sdru", "uemon"],
}
MATRIX_INPUTS = ["sdru", "uemon"]
RF_IFACES = {}
RF_LINK_NAMES = {}
for k, v in MATRIX_GRAPH.items():
    RF_IFACES[k] = {}
    for node in (v):
        RF_IFACES[k][node] = "{}_{}_rf".format(k, node)
        if k in MATRIX_INPUTS:
            RF_LINK_NAMES["rflink_{}_{}".format(k, node)] = []

for k, v in MATRIX_GRAPH.items():
    if k in MATRIX_INPUTS:
        for node in (v):
            RF_LINK_NAMES["rflink_{}_{}".format(k, node)].append(RF_IFACES[k][node])
            RF_LINK_NAMES["rflink_{}_{}".format(k, node)].append(RF_IFACES[node][k])

pc = portal.Context()
node_types = [
    ("d430", "Emulab, d430"),
    ("d740", "Emulab, d740"),
]

pc.defineParameter(
    name="sdru_nodetype",
    description="Type of compute node paired with the RU SDR",
    typ=portal.ParameterType.STRING,
    defaultValue=node_types[1],
    legalValues=node_types
)

pc.defineParameter(
    name="mon_nodetype",
    description="Type of compute node paired with the monitoring SDR",
    typ=portal.ParameterType.STRING,
    defaultValue=node_types[0],
    legalValues=node_types
)

pc.defineParameter(
    name="cn_nodetype",
    description="Type of compute node to use for CN node",
    typ=portal.ParameterType.STRING,
    defaultValue=node_types[0],
    legalValues=node_types
)

pc.defineParameter(
    name="sdr_compute_image",
    description="Image to use for compute connected to SDRs",
    typ=portal.ParameterType.STRING,
    defaultValue="",
    advanced=True
)

pc.defineParameter(
    name="srsran_commit_hash",
    description="Commit hash for srsRAN",
    typ=portal.ParameterType.STRING,
    defaultValue="",
    advanced=True
)

params = pc.bindParameters()
pc.verifyParameters()
request = pc.makeRequestRSpec()

role = "cn5g"
cn_node = request.RawPC(role)
cn_node.component_manager_id = COMP_MANAGER_ID
cn_node.hardware_type = params.cn_nodetype
cn_node.disk_image = UBUNTU_IMG
cn_if = cn_node.addInterface("{}-if".format(role))
cn_if.addAddress(pg.IPv4Address("192.168.1.1", "255.255.255.0"))
cn_link = request.Link("{}-link".format(role))
cn_link.setNoBandwidthShaping()
cn_link.addInterface(cn_if)
cn_node.addService(pg.Execute(shell="bash", command=OPEN5GS_DEPLOY_SCRIPT))

# collect node objects for RF matrix
matrix_nodes = {}

node_name = "cudu"
cudu = request.RawPC(node_name)
cudu.component_manager_id = COMP_MANAGER_ID
cudu.hardware_type = params.sdru_nodetype
if params.sdr_compute_image:
    cudu.disk_image = params.sdr_compute_image
else:
    cudu.disk_image = UBUNTU_IMG
cudu_cn_if = cudu.addInterface("{}-cn-if".format(node_name))
cudu_cn_if.addAddress(pg.IPv4Address("192.168.1.2", "255.255.255.0"))
cn_link.addInterface(cudu_cn_if)
node_sdr_if = cudu.addInterface("usrp_if")
node_sdr_if.addAddress(pg.IPv4Address("192.168.30.1", "255.255.255.0"))
sdr_link = request.Link("{}-sdr-link".format(node_name))
sdr_link.bandwidth = 10*1000*1000
sdr_link.addInterface(node_sdr_if)
if params.srsran_commit_hash:
    srsran_hash = params.srsran_commit_hash
else:
    srsran_hash = DEFAULT_SRSRAN_HASH
cmd = "{} '{}'".format(SRSRAN_DEPLOY_SCRIPT, srsran_hash)
cudu.addService(pg.Execute(shell="bash", command=cmd))
cudu.addService(pg.Execute(shell="bash", command="/local/repository/bin/tune-sdr-iface.sh"))
cudu.addService(pg.Execute(shell="bash", command="/local/repository/bin/update-attens ru1ue1 0"))
cudu.addService(pg.Execute(shell="bash", command="/local/repository/bin/update-attens ru2ue1 95"))
cudu.addService(pg.Execute(shell="bash", command="/local/repository/bin/update-attens ru1ue2 95"))
cudu.addService(pg.Execute(shell="bash", command="/local/repository/bin/update-attens ru2ue2 95"))

node_name = "sdru"
sdru = request.RawPC("{}-sdr".format(node_name))
sdru.component_id = NODE_IDS[node_name]
sdr_link.addNode(sdru)
sdru.Desire("rf-controlled", 1)
matrix_nodes[node_name] = sdru

node_name = "uemncmp"
uemncmp = request.RawPC(node_name)
uemncmp.component_manager_id = COMP_MANAGER_ID
uemncmp.hardware_type = params.mon_nodetype
if params.sdr_compute_image:
    uemncmp.disk_image = params.sdr_compute_image
else:
    uemncmp.disk_image = UBUNTU_IMG
node_sdr_if = uemncmp.addInterface("{}-sdr-if".format(node_name))
node_sdr_if.addAddress(pg.IPv4Address("192.168.10.1", "255.255.255.0"))
sdr_link = request.Link("{}-sdr-link".format(node_name))
sdr_link.bandwidth = 10*1000*1000
sdr_link.addInterface(node_sdr_if)
uemncmp.addService(pg.Execute(shell="bash", command="/local/repository/bin/tune-sdr-iface.sh"))
uemncmp.addService(pg.Execute(shell="bash", command="/local/repository/bin/deploy-gnuradio.sh"))
uemncmp.addService(pg.Execute(shell="bash", command="/local/repository/bin/update-attens uemon 0"))

node_name = "uemon"
uemon = request.RawPC("{}-sdr".format(node_name))
uemon.component_id = NODE_IDS[node_name]
sdr_link.addNode(uemon)
uemon.Desire("rf-controlled", 1)
matrix_nodes[node_name] = uemon

# ue nodes with COTS UE and B210
node_name = "ue1"
ue1 = request.RawPC(node_name)
ue1.component_manager_id = COMP_MANAGER_ID
ue1.component_id = NODE_IDS[node_name]
ue1.disk_image = COTS_UE_IMG
ue1.Desire("rf-controlled", 1)
ue1.addService(pg.Execute(shell="bash", command="/local/repository/bin/module-airplane.sh"))
ue1.addService(pg.Execute(shell="bash", command="/local/repository/bin/setup-cots-ue.sh internet"))
matrix_nodes[node_name] = ue1

node_name = "ue2"
ue2 = request.RawPC(node_name)
ue2.component_manager_id = COMP_MANAGER_ID
ue2.component_id = NODE_IDS[node_name]
ue2.disk_image = COTS_UE_IMG
ue2.Desire("rf-controlled", 1)
ue2.addService(pg.Execute(shell="bash", command="/local/repository/bin/module-airplane.sh"))
ue2.addService(pg.Execute(shell="bash", command="/local/repository/bin/setup-cots-ue.sh internet"))
matrix_nodes[node_name] = ue2

rf_ifaces = {}
for node_name, node in matrix_nodes.items():
    for rf_iface_name in RF_IFACES[node_name].values():
        rf_ifaces[rf_iface_name] = node.addInterface(rf_iface_name)

for rf_link_name, rf_iface_names in RF_LINK_NAMES.items():
    rf_link = request.RFLink(rf_link_name)
    for iface_name in rf_iface_names:
        rf_link.addInterface(rf_ifaces[iface_name])


tour = ig.Tour()
tour.Description(ig.Tour.MARKDOWN, tourDescription)
tour.Instructions(ig.Tour.MARKDOWN, tourInstructions)
request.addTour(tour)

pc.printRequestRSpec(request)
