#!/bin/bash
set -ex
TAG=$1
BINDIR=`dirname $0`
ETCDIR=/local/repository/etc
source $BINDIR/common.sh

if [ -z "$TAG" ]; then
    echo "usage: $0 <open5gs-git-tag>  (e.g. v2.7.7)"
    exit 1
fi

sudo sysctl -w net.ipv4.ip_forward=1
sudo iptables -t nat -A POSTROUTING -s 10.45.0.0/16 ! -o ogstun -j MASQUERADE

if [ -f $SRCDIR/open5gs-source-setup-complete ]; then
    echo "setup already ran; not running again"
    exit 0
fi

sudo apt update
sudo apt install -y software-properties-common gnupg
sudo add-apt-repository -y ppa:wireshark-dev/stable
echo "wireshark-common wireshark-common/install-setuid boolean false" | sudo debconf-set-selections
curl -fsSL https://pgp.mongodb.com/server-6.0.asc | \
    sudo gpg -o /usr/share/keyrings/mongodb-server-6.0.gpg --dearmor
echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-6.0.gpg ] https://repo.mongodb.org/apt/ubuntu $(lsb_release -cs)/mongodb-org/6.0 multiverse" | \
    sudo tee /etc/apt/sources.list.d/mongodb-org-6.0.list
sudo apt update
sudo apt install -y \
    mongodb-org \
    mongodb-mongosh \
    iperf3 \
    tshark \
    wireshark

sudo systemctl start mongod
sudo systemctl enable mongod

# --- Build Open5GS from source ---
sudo apt install -y --no-install-recommends \
    python3-pip python3-setuptools python3-wheel ninja-build \
    build-essential flex bison git cmake meson \
    libsctp-dev libgnutls28-dev libgcrypt-dev libssl-dev \
    libmongoc-dev libbson-dev libyaml-dev libnghttp2-dev libmicrohttpd-dev \
    libcurl4-gnutls-dev libtins-dev libtalloc-dev

# libidn package name varies across Ubuntu releases (per official docs)
if apt-cache show libidn-dev > /dev/null 2>&1; then
    sudo apt-get install -y --no-install-recommends libidn-dev
else
    sudo apt-get install -y --no-install-recommends libidn11-dev
fi

cd $SRCDIR
git clone $OPEN5GS_REPO open5gs-src
cd open5gs-src
git checkout $TAG

PATCHFILE=$ETCDIR/open5gs/open5gs.patch
if [ -f "$PATCHFILE" ] && grep -q '^---' "$PATCHFILE"; then
    echo "applying open5gs.patch..."
    git apply "$PATCHFILE"
else
    echo "no real open5gs.patch present (placeholder or missing); skipping"
fi

meson setup build \
    --prefix=/usr \
    --sysconfdir=/etc \
    --localstatedir=/var
ninja -C build
sudo ninja install -C build

# Create open5gs system user/group (PPA does this in postinst)
sudo groupadd -r open5gs 2>/dev/null || true
sudo useradd -r -g open5gs -s /sbin/nologin -d /var/log/open5gs open5gs 2>/dev/null || true

# Log directory ownership (PPA creates this)
sudo mkdir -p /var/log/open5gs
sudo chown open5gs:open5gs /var/log/open5gs

# Install systemd unit files (ninja install does NOT do this).
# meson generates them under build/configs/systemd with the configured paths
# substituted in (the configs/systemd/*.in files are templates).
sudo cp build/configs/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload

# Defensive: make sure /etc/open5gs exists for the config copy below
sudo mkdir -p /etc/open5gs

# Set up ogstun TUN device per official docs (idempotent).
# The UPF/SGW-U daemons can self-create this with CAP_NET_ADMIN, but
# the docs do it explicitly; doing it here removes any race.
if ! ip link show ogstun > /dev/null 2>&1; then
    sudo ip tuntap add name ogstun mode tun
fi
sudo ip addr replace 10.45.0.1/16 dev ogstun
sudo ip addr replace 2001:db8:cafe::1/48 dev ogstun
sudo ip link set ogstun up
# --- end of from-source block ---

sudo cp /local/repository/etc/open5gs/* /etc/open5gs/

sudo systemctl restart open5gs-mmed
sudo systemctl restart open5gs-sgwcd
sudo systemctl restart open5gs-smfd
sudo systemctl restart open5gs-amfd
sudo systemctl restart open5gs-sgwud
sudo systemctl restart open5gs-upfd
sudo systemctl restart open5gs-hssd
sudo systemctl restart open5gs-pcrfd
sudo systemctl restart open5gs-nrfd
sudo systemctl restart open5gs-ausfd
sudo systemctl restart open5gs-udmd
sudo systemctl restart open5gs-pcfd
sudo systemctl restart open5gs-nssfd
sudo systemctl restart open5gs-bsfd
sudo systemctl restart open5gs-udrd

# change default logrotate settings to weekly and allow reading by anyone (promtail)
cat <<EOF >> /tmp/open5gs-logrotate
/var/log/open5gs/*.log {
    weekly
    sharedscripts
    missingok
    compress
    rotate 14
    create 644 open5gs open5gs

    postrotate
        for i in nrfd scpd pcrfd hssd ausfd udmd udrd upfd sgwcd sgwud smfd mmed amfd; do
            systemctl reload open5gs-\$i
        done
    endscript
}
EOF
sudo mv /tmp/open5gs-logrotate /etc/logrotate.d/open5gs

cd $SRCDIR
wget https://raw.githubusercontent.com/open5gs/open5gs/main/misc/db/open5gs-dbctl
chmod +x open5gs-dbctl
./open5gs-dbctl add_ue_with_slice 999990000000141 00112233445566778899aabbccddeeff 0ed47545168eafe2c39c075829a7b61f internet 1 000001 # IMSI,K,OPC
./open5gs-dbctl type 999990000000141 1  # APN type IPV4
./open5gs-dbctl add_ue_with_slice 999990000000118 00112233445566778899aabbccddeeff 0ed47545168eafe2c39c075829a7b61f internet 1 000001 # IMSI,K,OPC
./open5gs-dbctl type 999990000000118 1  # APN type IPV4
touch $SRCDIR/open5gs-source-setup-complete