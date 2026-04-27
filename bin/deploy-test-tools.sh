set -ex
BINDIR=`dirname $0`
source $BINDIR/common.sh
TMPDIR=/var/tmp

if [ $# -eq 0 ] || [ $# -gt 1 ]; then
    echo "usage: $0 [orch|core|nodeb]"
    exit 1
fi

ROLE=$1

echo "installing test tools"
echo "role: $ROLE"
HOSTNAME=$(hostname -s)
ORCH_HOST=orch
GRAFANA_URL=https://dl.grafana.com/oss/release/grafana_10.4.1_amd64.deb
LOKI_URL=https://github.com/grafana/loki/releases/download/v2.8.3/loki_2.8.3_amd64.deb
LOGCLI_URL=https://github.com/grafana/loki/releases/download/v2.8.3/logcli_2.8.3_amd64.deb
PROMTAIL_URL=https://github.com/grafana/loki/releases/download/v2.8.3/promtail_2.8.3_amd64.deb
DASHBOARDS_PATH=/var/lib/grafana/dashboards

get_emulab_vars () {
    echo "getting emulab vars"
    GENIUSER=`geni-get user_urn | awk -F+ '{print $4}'`
    if [ $USER != $GENIUSER ]; then
        sudo -u $GENIUSER $SCRIPTNAME
        exit $?
    fi

    if [ ! -e $TMPDIR/manifest.xml ]; then
        geni-get manifest > $TMPDIR/manifest.xml
        cat $TMPDIR/manifest.xml | grep -q emulab:password
    fi

    # Geni key decrypts the password.
    if [ ! -e $TMPDIR/geni.key ]; then
        geni-get key > $TMPDIR/geni.key
        cat $TMPDIR/geni.key | grep -q END\ .\*\PRIVATE\ KEY
    fi

    # Suck out the key from the manifest
    if [ ! -e $TMPDIR/encrypted_admin_pass ]; then
        cat $TMPDIR/manifest.xml | perl -e '@lines = <STDIN>; $all = join("",@lines); if ($all =~ /^.+<[^:]+:password\s+name=\"perExptPassword\"[^>]*>([^<]+)<\/[^:]+:password>.+/igs) { print $1; }' > $TMPDIR/encrypted_admin_pass
    fi

    # And decrypt to get the password in plain text.
    if [ ! -e $TMPDIR/decrypted_admin_pass -a -s $TMPDIR/encrypted_admin_pass ]; then
        openssl smime -decrypt -inform PEM -inkey $TMPDIR/geni.key -in $TMPDIR/encrypted_admin_pass -out $TMPDIR/decrypted_admin_pass
    fi
    password=`/bin/cat $TMPDIR/decrypted_admin_pass`
}

install_loki () {
    echo "installing loki"
    curl -L -o /tmp/loki.deb "$LOKI_URL"
    sudo dpkg --force-confold -i /tmp/loki.deb
    curl -L -o /tmp/logcli.deb "$LOGCLI_URL"
    sudo dpkg --force-confold -i /tmp/logcli.deb
    sudo cp $CFGDIR/grafana/loki-config.yaml /etc/loki/config.yml
    mkdir $TMPDIR/loki
    sudo chown -R loki /var/tmp/loki
    sudo systemctl enable loki
    sudo systemctl restart loki
}

add_loki_datasouce () {
    echo "adding loki datasource"
    cat <<EOF > /tmp/loki-datasource.yml
apiVersion: 1
datasources:
  - name: Loki
    type: loki
    uid: P8E80F9AEF21F6940
    access: proxy
    url: http://localhost:3100
    jsonData:
      maxLines: 1000
EOF
    sudo cp /tmp/loki-datasource.yml /etc/grafana/provisioning/datasources/
}

install_grafana () {
    echo "installing grafana"
    # if [ ! -e /etc/apt/trusted.gpg.d/grafana.gpg ]; then
    #     wget -q -O - https://apt.grafana.com/gpg.key | gpg --dearmor | sudo tee /etc/apt/trusted.gpg.d/grafana.gpg > /dev/null
    # fi
    # if [ ! -e /etc/apt/sources.list.d/grafana.list ]; then
    #     echo "deb [signed-by=/etc/apt/trusted.gpg.d/grafana.gpg] https://apt.grafana.com stable main" | sudo tee -a /etc/apt/sources.list.d/grafana.list
    # fi

    # use the deb package instead of the apt repo, since the repo only has enterprise nightly atm
    sudo apt-get update
    sudo apt-get install -y sqlite crudini
    curl -L -o /tmp/grafana.deb "$GRAFANA_URL"
    sudo apt install -y --no-install-recommends /tmp/grafana.deb
    sudo crudini --set /etc/grafana/grafana.ini security admin_password $password
    sudo grafana-cli --config /etc/grafana/grafana.ini admin reset-admin-password $password
    sudo crudini --set /etc/grafana/grafana.ini dashboards default_home_dashboard_path $DASHBOARDS_PATH/dashboard.json
    add_loki_datasouce
    sudo grafana-cli plugins install pr0ps-trackmap-panel
    sudo mkdir -p $DASHBOARDS_PATH
    sudo cp $CFGDIR/grafana/dashboard.json $DASHBOARDS_PATH/dashboard.json
    sudo chown -R grafana:grafana /var/lib/grafana
    sudo chown -R grafana:grafana /var/log/grafana
    sudo systemctl enable grafana-server
    sudo systemctl start grafana-server
    echo "waiting for grafana to start"
    sleep 10
}

install_gnb_service () {
    echo "installing srs-gnb service"
    sudo cp $SERVICESDIR/srs-gnb.service /etc/systemd/system/
    sudo systemctl daemon-reload
    ## We don't necessarily want to start the service right away
    # sudo systemctl enable srs-gnb
    # sudo systemctl restart srs-gnb
}

install_promtail () {
    echo "installing promtail"
    curl -L -o /tmp/promtail.deb "$PROMTAIL_URL"
    sudo dpkg --force-confold -i /tmp/promtail.deb
}

setup_promtail () {
    echo "setting up promtail"
    cat <<EOF > /tmp/promtail-config.yml
# Created on $(date)
server:
  http_listen_port: 9080
  grpc_listen_port: 0

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://$ORCH_HOST:3100/loki/api/v1/push
EOF

    if [ $ROLE == "core" ]; then
        cat <<EOF >> /tmp/promtail-config.yml
scrape_configs:
- job_name: open5gs
  static_configs:
  - targets:
      - localhost
    labels:
      job: open5gs
      host: $HOSTNAME
      __path__: /var/log/open5gs/*.log
EOF
    elif [ $ROLE == "nodeb" ]; then
        echo "setting up promtail for gnb"
        cat <<EOF >> /tmp/promtail-config.yml
scrape_configs:
- job_name: srs-gnb
  static_configs:
  - targets:
      - localhost
    labels:
      job: srs-gnb
      host: $HOSTNAME
      __path__: /var/log/srs-gnb.log
- job_name: srs-gnb-trace
  static_configs:
  - targets:
      - localhost
    labels:
      job: srs-gnb-trace
      host: $HOSTNAME
      __path__: /tmp/gnb-trace.log
- job_name: srs-gnb-log
  static_configs:
  - targets:
      - localhost
    labels:
      job: srs-gnb-log
      host: $HOSTNAME
      __path__: /tmp/gnb.log
EOF
    fi
    sudo cp /tmp/promtail-config.yml /etc/promtail/config.yml
}

start_promtail () {
    sudo systemctl daemon-reload
    sudo systemctl enable promtail
    sudo systemctl restart promtail
}

if [ $ROLE == "orch" ]; then
    get_emulab_vars
    install_loki
    install_grafana
elif [ $ROLE == "core" ] || [ $ROLE == "nodeb" ]; then
    install_promtail
    setup_promtail
    start_promtail
fi

if [ $ROLE == "nodeb" ]; then
    install_gnb_service
fi
