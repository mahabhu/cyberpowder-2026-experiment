#!/bin/bash
set -ex
BINDIR=`dirname $0`
source $BINDIR/common.sh

if [ $# -eq 0 ] || [ $# -gt 1 ]; then
    echo "usage: $0 [orch_host]"
    exit 1
fi

ORCH_HOST=$1
ORCH_FQDN=`geni-get slice_urn | awk -F ':' '{print $4}' | awk -v ohost="$ORCH_HOST" -F '+' '{print ohost "." $3 "." $1 ".emulab.net"}'`

echo "pulling mobile endpoints repo"
git clone https://gitlab.flux.utah.edu/dmaas/mobile-endpoints.git $MEREPODIR
cd $MEREPODIR
git checkout 6ebf537d9f256323c9fd2a179b558069faff9017

echo "Installing test tools"

HOSTNAME=$(hostname -s)
ARCH=$(dpkg --print-architecture)
PROMTAIL_URL=https://github.com/grafana/loki/releases/download/v2.8.3/promtail_2.8.3_$ARCH.deb

install_ue_deps () {
    sudo apt update && sudo apt install -y --no-install-recommends \
      gpsd-clients \
      iperf3 \
      python3-pip \
      python3-zmq
    sudo pip3 install -r $MEBINDIR/requirements.txt
}

install_ue_services () {
  python_scripts=$(ls $MEBINDIR/*.py)
  for script in $python_scripts; do
      sudo cp $script $SRCDIR
  done
  services=$(ls $MESRVDIR/*.service)
  for service in $services; do
      sudo cp $service /etc/systemd/system
      sudo systemctl daemon-reload
      sudo systemctl enable $(basename $service)
      sudo systemctl restart $(basename $service)
  done
}

install_promtail () {
    curl -L -o /tmp/promtail.deb "$PROMTAIL_URL"
    sudo dpkg --force-confold -i /tmp/promtail.deb
}

setup_promtail () {
    cat <<EOF > /tmp/promtail-config.yml
# Created on $(date)
server:
  http_listen_port: 9080
  grpc_listen_port: 0

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://$ORCH_FQDN:3100/loki/api/v1/push

scrape_configs:
- job_name: quectel-cm
  static_configs:
  - targets:
      - localhost
    labels:
      job: quectel-cm
      host: $HOSTNAME
      __path__: /var/log/quectel-cm.log
- job_name: ue-metrics
  static_configs:
  - targets:
      - localhost
    labels:
      job: ue-metrics
      host: $HOSTNAME
      __path__: /var/log/ue-metrics.log
- job_name: gps
  static_configs:
  - targets:
      - localhost
    labels:
      job: gps
      host: $HOSTNAME
      __path__: /var/log/gps.log
EOF
    sudo cp /tmp/promtail-config.yml /etc/promtail/config.yml
}

start_promtail () {
    sudo systemctl daemon-reload
    sudo systemctl enable promtail
    sudo systemctl restart promtail
}


install_ue_deps
install_ue_services
install_promtail
setup_promtail
start_promtail
