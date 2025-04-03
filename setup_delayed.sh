echo "set man-db/auto-update false" |sudo debconf-communicate
sudo dpkg-reconfigure man-db
sudo apt install -y --no-install-recommends iverilog
pip3 install cocotb cocotb-bus cocotb-coverage
cp hdl/delayed_dut.v hdl/dut.v
