#!/usr/bin/env python

import os

import geni.portal as portal
import geni.rspec.pg as pg
import geni.rspec.igext as ig
import geni.rspec.emulab.pnext as PN
import geni.rspec.emulab.spectrum as spectrum
import geni.rspec.emulab.route as route


tourDescription = """
### srsRAN 5G w/ Open5GS CN5G using the POWDER Dense Deployment

This profile deploys a 5G core and radio access network using the following components:

- Open5GS core network: All of the core network functions (AMF, SMF, UPF, etc.) are deployed to a single compute node with LAN connections to the gNodeBs in the experiment. The NFs are wrapped in system services and automatically started when you instantiate your experiment.

- One or more srsRAN gNodeBs: The gNB soft-modems are deployed to NUC i7 compute nodes paired with NI B210 SDRs. Each SDR is connected to a custom medium-power TDD RF front end capable of operating from 3358-3600 MHz.

- An orchestration node (optional): This node is currently used to aggregate time-coherent logs for all of the relevant processes in the 5G network. Promtail is used to push relevant logs from other nodes in this experiment to the Loki instance running on this node, and Grafana is used to present logs/data via a web interface.

It is designed to be used with this [Mobile Endpoints profile](https://www.powderwireless.net/show-profile.php?project=PowderTeam&profile=mobile-endpoints), which instantiates an experiment with 5G COTS UEs deployed to campus shuttles that operate in and around the Dense Deployment sites.

Note: This profile currently requires the use of the 3430-3450 MHz spectrum range and you need an approved reservation for this spectrum in order to use it. It's also strongly recommended that you include the following necessary resources in your reservation to gaurantee their availability at the time of your experiment:

- 2x d430 compute nodes to host the core network and orchestrator
- The set of the Dense Deployment sites you plan to use
- POWDER mobile endpoints

If you want your experiment to run for more than a single day, you'll need to make separate single-day reservations for the mobile endpoints, since the maximum reservation duration for those is one day.

Finally, the mobility of the campus shuttles that host the COTS UEs and the medium-power RF front ends used in the Dense Deployment mean that some links may be short-lived (< 30 s in duration); others may last a few minutes. Link quality and duration will depend on the shuttle route and Dense Deployment site in question. Some routes will not pass close enough to close links at every dense deployment site.

"""

# network-sdr/etc/srsran/*.patch

tourInstructions = """
Startup scripts will still be running when your experiment becomes ready. Since this profile is made to interact with POWDER mobile endpoints, you need to start a mobile endpoints experiment as well. You can do this while you are waiting for the startup scripts from this experiment to finish. Use [this profile](https://www.powderwireless.net/show-profile.php?project=PowderTeam&profile=mobile-endpoints). You'll need set the "Orchestrator Hostname" field to `{host-orch}` during the paramaterization step for this experiment, unless you disabled the orchestration node. (The rest of the instructions assume it is enabled.) Finally, watch the "Startup" column on the "List View" tab for both experiments and wait until all of the compute nodes show "Finished" before proceeding.

*After all startup scripts have finished* you can access the [Grafana web interface](http://{host-orch}:3000/) with username `admin` and password `{password-perExptPassword}`. The default Grafana dashboard includes panels for a variety of logs from relevant processes across the entire 5G experiment. The top panel tracks log events for every service of interest, and is helpful for navigating data from a long experiment, zooming in on the periods of activity you care about, etc. The other panels focus on specific processes, including:

(from this experiment)

- `cn5g` node: all of the Open5GS core network services (AMF, SMF, UPF, etc.)
- `gnb-*` nodes: the srsRAN gNB softmodem

(from the mobile endpoints experiment you supplied with the provided orchestrator hostname)

- `bus-*` nodes: GPS location, UE connection manager, UE metrics

Initially, the UE and gNodeB panels will be empty because this profile does not automatically start the gNodeB softmodems. Instead, we leave the orchestration of the base stations to the user. Note that, in order to make the panels readable, the UE, UE metrics, and Map panels only display data for the mobile endpoint (Bus) you select at the top of the Grafana dashboard using the `Bus` dropdown selector. (This dashboard is a starting point; you can add more panels and customize it to your liking.)

The gNodeB softmodem executables have been wrapped in system services for convenience. Starting the service is simple:

```
# on any of the gNodeB nodes
sudo systemctl restart srs-gnb.service
```

If the softmodem crashes for some reason, the service will take care of restarting it.

Note that running gNodeBs simultaneously at adjacent dense deploment sites (e.g., Moran and USTAR, Guesthouse and EBC, etc.) will create inter-cell interference, which may not be desired unless you are trying to study the effects of said interference. Assuming you want to minimize inter-cell interference, you could run simultaneous gNodeBs at, e.g., Mario, USTAR, and Guesthouse.

Also, if you want to monitor the logs of any service directly (e.g., if you disabled the orchestration node), you can use `journalctl` to do so:

```
# on any of the gNodeB nodes
sudo journalctl -u srs-gnb.service -f

# on the cn5g node
sudo journalctl -u open5gs-amfd.service -f

# on any of the mobile endpoints
sudo journalctl -u quectel-cm.service -f  # for the connection manager log
sudo journalctl -u ue-metrics.service -f  # for the UE metrics log
```

After you've started one or more gNodeBs and your mobile endpoints experiment is up and running, you shoulds start to see attaches in the UE, gNodeB, and Core Network panels as the shuttles move around the dense deployment sites. The UE panel will include connection manager logs showing, e.g., the IP address the UE gets, as well as the raw output of the `ue-metrics` service. The UE metrics panel in Grafana will plot a time series of some common channel metrics (RSRP, RSRQ, SINR) for each UE that attaches. You can hover over these data points to see where the bus/UE was at the time of the reading. The gNodeB panel will the softmodem output for all of the sites where you've started the `srs-gnb` service. The Core Network panel will include logs for all of Open5GS network functions, including, e.g., AMF entries that show the IMSIs of the UEs that attach to the network. The overall interface will look something like [this](https://gitlab.flux.utah.edu/dmaas/oai-outdoor-ota/-/blob/e92db33fe25130dcc2f6f87aa11c47c589b2d5e3/grafana-5g.png).

Of course, you can interact with the nodes in the experiments directly as well. For example, you can start a packet capture on the `cn5g` node to monitor traffic between the various network functions and the gNodeB:

```
# on the cn5g node
LANIF=`ip r | awk '/192\.168\.1\.0/{print $3}'`
sudo tshark -i $LANIF \
  -f "not arp and not port 53 and not host archive.ubuntu.com and not host security.ubuntu.com"
```

Or generate some traffic between the core network and the UE:

```
# in a terminal on cn5g
ping <IP address of UE>  # you can find the IP address of the UE in the connection manager logs for the UE in question
```


Known Issues:

- Until handover is implemented, the UE will not roam between gNodeBs. This means that if the shuttle moves from one dense deployment site to another, the UE will lose its connection to the network. The UE will re-attach to the network when it comes back into range of a gNodeB. This can lead to issues with the core network in some cases, e.g., when the UE is moving between two gNodeBs with overlapping coverage. Debug.

"""

BIN_PATH = "/local/repository/bin"
ETC_PATH = "/local/repository/etc"
UBUNTU_IMG = "urn:publicid:IDN+emulab.net+image+emulab-ops//UBUNTU22-64-STD"
COTS_UE_IMG = "urn:publicid:IDN+emulab.net+image+PowderTeam:cots-jammy-image"
COMP_MANAGER_ID = "urn:publicid:IDN+emulab.net+authority+cm"
DEFAULT_SRSRAN_HASH = "5e6f50a202c6efa671d5b231d7c911dc6c3d86ed"
DEFAULT_OPEN5GS_TAG = "v2.7.6"
SRSRAN_DEPLOY_SCRIPT = os.path.join(BIN_PATH, "deploy-srsran.sh")
OPEN5GS_DEPLOY_SCRIPT = os.path.join(BIN_PATH, "deploy-open5gs-source.sh")
TEST_TOOLS_DEPLOY_SCRIPT = os.path.join(BIN_PATH, "deploy-test-tools.sh")

def gnb_cn_pair(idx, dense_radio):
    node = request.RawPC("gnb-{}".format(dense_radio.device.split("-")[-1]))
    node.component_manager_id = COMP_MANAGER_ID
    node.component_id = dense_radio.device
    node.disk_image = UBUNTU_IMG
    nodeb_cn_if = node.addInterface("nodeb-cn-if")
    nodeb_cn_if.addAddress(pg.IPv4Address("192.168.1.{}".format(idx + 2), "255.255.255.0"))
    cn_link.addInterface(nodeb_cn_if)

    if params.deploy_srsran:
        if params.include_orch:
            cmd = "{} {}".format(TEST_TOOLS_DEPLOY_SCRIPT, "nodeb")
            node.addService(pg.Execute(shell="bash", command=cmd))

        cmd = "{} '{}'".format(SRSRAN_DEPLOY_SCRIPT, DEFAULT_SRSRAN_HASH)
        node.addService(pg.Execute(shell="bash", command=cmd))
        if params.start_gnbs:
            node.addService(pg.Execute(shell="bash", command="sudo systemctl restart srs-gnb.service"))

    if params.start_vnc_dense:
        node.startVNC()

def fixed_node(_, f_node_tuple):
    node = request.RawPC("{}-{}".format(f_node_tuple.fe_id, "nuc1"))
    agg_full_name = "urn:publicid:IDN+{}.powderwireless.net+authority+cm".format(f_node_tuple.fe_id)
    node.component_manager_id = agg_full_name
    node.component_id = "nuc1"
    node.disk_image = COTS_UE_IMG
    if params.start_vnc_fixed:
        node.startVNC()

pc = portal.Context()

node_types = [
    ("d430", "Emulab, d430"),
    ("d740", "Emulab, d740"),
    ("d760p", "Emulab, d760"),
    ("d760-gpu", "Emulab, d760 w/ GPU"),
]

pc.defineParameter(
    name="include_orch",
    description="Include orchestrator node for centralized logging (Grafana/Loki). Install logging" \
                "tools (Promtail) on all nodes.",
    typ=portal.ParameterType.BOOLEAN,
    defaultValue=True
)

pc.defineParameter(
    name="include_mobiles",
    description="Include mobile endpoints in the experiment. (Only enable if this experiment is" \
                "meant to last until the end of the day. Otherwise, instantiate a separate" \
                "experiment using the mobile endpoints profile.)",
    typ=portal.ParameterType.BOOLEAN,
    defaultValue=False
)

pc.defineParameter(
    name="dnn",
    description="DNN/APN for COTS UEs to connect to (if mobile endpoints are included).",
    typ=portal.ParameterType.STRING,
    defaultValue="internet",
    longDescription="DNN/APN that the connection manager will select for the UE."
)

pc.defineParameter(
    name="orch_nodetype",
    description="Type of compute node to use for Orch node (if included)",
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

dense_radios = [
    ("cnode-mario", "Mario"),
    ("cnode-moran", "Moran"),
    ("cnode-guesthouse", "Guesthouse"),
    ("cnode-ebc", "EBC"),
    ("cnode-ustar", "USTAR"),
]

pc.defineStructParameter(
    "dense_radios", "Dense Site Radios", [],
    multiValue=True,
    min=1,
    multiValueTitle="Dense Site NUC+B210 radios to allocate.",
    members=[
        portal.Parameter(
            "device",
            "SFF Compute + NI B210 device",
            portal.ParameterType.STRING,
            dense_radios[0], dense_radios,
            longDescription="A Small Form Factor compute with attached NI B210 device at the given" \
                            "Dense Deployment site will be allocated."
        ),
    ]
)

portal.context.defineStructParameter(
    "freq_ranges", "Frequency Ranges To Transmit In",
    defaultValue=[{"freq_min": 3430.0, "freq_max": 3450.0}],
    multiValue=True,
    min=0,
    multiValueTitle="Frequency ranges to be used for transmission.",
    members=[
        portal.Parameter(
            "freq_min",
            "Frequency Range Min",
            portal.ParameterType.BANDWIDTH,
            3430.0,
            longDescription="Values are rounded to the nearest kilohertz."
        ),
        portal.Parameter(
            "freq_max",
            "Frequency Range Max",
            portal.ParameterType.BANDWIDTH,
            3450.0,
            longDescription="Values are rounded to the nearest kilohertz."
        ),
    ]
)

pc.defineParameter(
    name="start_gnbs",
    description="Automatically start the srsRAN gNodeBs",
    typ=portal.ParameterType.BOOLEAN,
    defaultValue=False,
    advanced=True
)

pc.defineParameter(
    name="os_image",
    description="Mobile endpoints disk image",
    typ=portal.ParameterType.STRING,
    defaultValue=COTS_UE_IMG,
    longDescription="File system image for the node.",
    advanced=True
)

pc.defineParameter(
    name="deploy_srsran",
    description="Deploy srsRAN",
    typ=portal.ParameterType.BOOLEAN,
    defaultValue=True,
    advanced=True
)

pc.defineParameter(
    name="start_vnc_dense",
    description="enable noVNC on dense nodes",
    typ=portal.ParameterType.BOOLEAN,
    defaultValue=True,
    advanced=True
)

pc.defineParameter(
    name="start_vnc_mobile",
    description="enable noVNC on mobile endpoints",
    typ=portal.ParameterType.BOOLEAN,
    defaultValue=True,
    advanced=True
)

pc.defineParameter(
    name="start_vnc_fixed",
    description="enable noVNC on fixed endpoint nodes",
    typ=portal.ParameterType.BOOLEAN,
    defaultValue=True,
    advanced=True
)

fixed_radios = [
    ("web", "WEB, nuc1"),
    ("bookstore", "Bookstore, nuc1"),
    ("humanities", "Humanities, nuc1"),
    ("law73", "Law 73, nuc1"),
    ("ebc", "EBC, nuc1"),
    ("madsen", "Madsen, nuc1"),
    ("sagepoint", "Sage Point, nuc1"),
    ("moran", "Moran, nuc1"),
    ("cpg", "Central Parking Garage, nuc1"),
    ("guesthouse", "Guest House, nuc1"),
]

pc.defineStructParameter(
    "fixed_radios", "Fixed Endpoint Radios", [],
    multiValue=True,
    min=0,
    multiValueTitle="Fixed endpoint NUC+B210/COTSUE radios to allocate.",
    members=[
        portal.Parameter(
            "fe_id",
            "SFF Compute + NI B210 device + COTS UE",
            portal.ParameterType.STRING,
            fixed_radios[0], fixed_radios,
            longDescription="A small form factor compute with attached NI B210 and COTS UE the" \
                            "given Fixed Endpoint site will be allocated."
        ),
    ],
    advanced=True
)

params = pc.bindParameters()
pc.verifyParameters()
request = pc.makeRequestRSpec()

cn_node = request.RawPC("cn5g")
cn_node.component_manager_id = COMP_MANAGER_ID
cn_node.hardware_type = params.cn_nodetype
cn_node.disk_image = UBUNTU_IMG
cn_if = cn_node.addInterface("cn-if")
cn_if.addAddress(pg.IPv4Address("192.168.1.1", "255.255.255.0"))
cn_link = request.Link("cn-link")
cn_link.setNoBandwidthShaping()
cn_link.addInterface(cn_if)

if params.include_orch:
    cmd = "{} {}".format(TEST_TOOLS_DEPLOY_SCRIPT, "core")
    cn_node.addService(pg.Execute(shell="bash", command=cmd))

cmd = "{} '{}'".format(OPEN5GS_DEPLOY_SCRIPT, DEFAULT_OPEN5GS_TAG)
cn_node.addService(pg.Execute(shell="bash", command=cmd))

for idx, dense_radio in enumerate(params.dense_radios):
    gnb_cn_pair(idx, dense_radio)

for idx, fixed_radio in enumerate(params.fixed_radios):
    fixed_node(idx, fixed_radio)

for frange in params.freq_ranges:
    request.requestSpectrum(frange.freq_min, frange.freq_max, 0)

if params.include_orch:
    orch = request.RawPC("orch")
    orch.component_manager_id = COMP_MANAGER_ID
    orch.hardware_type = params.orch_nodetype
    orch.disk_image = UBUNTU_IMG
    orch_if = orch.addInterface("orch-if")
    orch_if.addAddress(
        pg.IPv4Address("192.168.1.{}".format(len(params.dense_radios) + 2),
                          "255.255.255.0")
    )
    cn_link.addInterface(orch_if)
    cmd = "{} {}".format(TEST_TOOLS_DEPLOY_SCRIPT, "orch")
    orch.addService(pg.Execute(shell="bash", command=cmd))


if params.include_mobiles:
    all_routes = request.requestAllRoutes()
    all_routes.disk_image = params.os_image
    if params.include_orch:
        all_routes.addService(
            pg.Execute(shell="bash", command="sudo /local/repository/bin/deploy_mobile_tools.sh orch")
        )
    all_routes.addService(
        pg.Execute(shell="bash", command="sudo /local/repository/bin/setup_cots_ue.sh {}".format(params.dnn))
    )

    if params.start_vnc_mobile:
        all_routes.startVNC()

tour = ig.Tour()
tour.Description(ig.Tour.MARKDOWN, tourDescription)
tour.Instructions(ig.Tour.MARKDOWN, tourInstructions)
request.addTour(tour)

# Password for grafana.
request.addResource(ig.Password("perExptPassword"))

pc.printRequestRSpec(request)