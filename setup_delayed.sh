echo "set man-db/auto-update false" | debconf-communicate
dpkg-reconfigure man-db
sudo apt install -y --no-install-recommends iverilog
pip3 install cocotb cocotb-bus cocotb-coverage
cp hdl/delayed_dut.v hdl/dut.v
