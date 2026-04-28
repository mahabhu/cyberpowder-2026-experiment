set -ex
COMMIT_HASH=$1
BINDIR=`dirname $0`
ETCDIR=/local/repository/etc
source $BINDIR/common.sh

echo "installing deps"
sudo add-apt-repository -y ppa:ettusresearch/uhd
sudo apt-get update
sudo apt-get install -y libuhd-dev uhd-host

sudo apt install \
  cmake \
  doxygen \
  g++ \
  gir1.2-gtk-3.0 \
  git \
  libad9361-dev \
  libboost-all-dev \
  libcodec2-dev \
  libfftw3-dev \
  libgmp-dev \
  libgsl-dev \
  libgsm1-dev \
  libiio-dev \
  liblog4cpp5-dev \
  libqt5opengl5-dev \
  libqwt-qt5-dev \
  libsdl1.2-dev \
  libsndfile1-dev \
  libsoapysdr-dev \
  libspdlog-dev \
  libudev-dev \
  libusb-1.0-0 \
  libusb-1.0-0-dev \
  libzmq3-dev \
  pybind11-dev \
  python3-click \
  python3-click-plugins \
  python3-gi \
  python3-gi-cairo \
  python3-jsonschema \
  python3-lxml \
  python3-mako \
  python3-matplotlib \
  python3-numpy \
  python3-packaging \
  python3-pygccxml \
  python3-pyqt5 \
  python3-pyqtgraph \
  python3-qtpy \
  python3-scipy \
  python3-setuptools \
  python3-sphinx \
  python3-yaml \
  python3-zmq \
  soapysdr-tools

cd $SRCDIR
git clone --recursive https://github.com/gnuradio/volk.git
cd volk
mkdir build
cd build
cmake ../
make -j`nproc`
sudo make install
sudo ldconfig

cd $SRCDIR
git clone https://github.com/gnuradio/gnuradio.git
cd gnuradio
mkdir build
cd build
cmake -DCMAKE_BUILD_TYPE=Release ../
make -j`nproc`
sudo make install
sudo ldconfig

echo "building and installing GNU Radio"

touch $SRCDIR/gnuradio-setup-complete
