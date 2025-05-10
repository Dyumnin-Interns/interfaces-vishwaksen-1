import os
import random
import cocotb
from cocotb.triggers import Timer, RisingEdge, FallingEdge, ReadOnly, NextTimeStep
from cocotb_coverage.coverage import CoverCross, CoverPoint, coverage_db
from cocotb_bus.monitors import BusMonitor
from cocotb_bus.drivers import BusDriver

# @cocotb.test()
# async def dut_test(dut):
#     assert 0, "Test not Implemented"

failed_tests = 0
expected_value = []

def sb_fn(actual_value):
    global expected_value, failed_tests
    if not expected_value:
        print("Warning: Unexpected output received")
        return
    expected = expected_value.pop(0)
    print(f"Expected: {expected}, Actual: {actual_value}", end=" ")
    if actual_value != expected:
        failed_tests += 1
        print("-> Err -- Mismatch!")
    else:
        print("-> OK")

@CoverPoint("top.a", xf=lambda x, y: x, bins=[0, 1])
@CoverPoint("top.b", xf=lambda x, y: y, bins=[0, 1])
@CoverCross("top.cross.ab", items=["top.a", "top.b"])
def ab_cover(a, b):
    pass

@CoverPoint("top.inputport.currentWrite", xf=lambda x: x.get('currentWrite'), bins=["IdleWrite", "TxnWrite"])  # only two states as write_rdy is always 1
@CoverPoint("top.inputport.previousWrite", xf=lambda x: x.get('previousWrite'), bins=["IdleWrite", "TxnWrite"])
@CoverCross("top.cross.input", items=["top.inputport.previousWrite", "top.inputport.currentWrite"])
def in_port_cover(TxnWrite_ds):
    pass

@CoverPoint("top.outputport.currentRead", xf=lambda x: x.get('currentRead'), bins=["IdleRead", "TxnRead"])  # only two states as read_rdy is always 1
@CoverPoint("top.outputport.previousRead", xf=lambda x: x.get('previousRead'), bins=["IdleRead", "TxnRead"])
@CoverCross("top.cross.output", items=["top.outputport.previousRead", "top.outputport.currentRead"])
def out_port_cover(TxnRead_ds):
    pass

@CoverPoint("top.read_address", xf=lambda x: x, bins=[0, 1, 2, 3])
def read_address_cover(address):
    pass

@cocotb.test()
async def dut_test(dut):
    global expected_value, failed_tests
    failed_tests = 0
    expected_value = []

    dut.RST_N.value = 1
    await Timer(20, 'ns')
    dut.RST_N.value = 0
    await Timer(20, 'ns')
    dut.RST_N.value = 1

    write_drv = InputDriver(dut, "", dut.CLK)
    read_drv = OutputDriver(dut, "", dut.CLK, sb_fn)
    InputMonitor(dut, "", dut.CLK, callback=in_port_cover)
    OutputMonitor(dut, "", dut.CLK, callback=out_port_cover)
    
    # Hit all read addresses 0–3 (initial condition)
    for addr in range(3):
        read_address_cover(addr)
        await read_drv._driver_sent(addr)
        
    # Random Tests
    for i in range(50):
        a = random.randint(0, 1)
        b = random.randint(0, 1)
        p = random.random()
        expected_value.append(a | b)

        await write_drv._driver_sent(4, a)
        await write_drv._driver_sent(5, b)
        ab_cover(a, b)

        # 100 cycles to complete the execution for delayed_dut
        for j in range(100):
            await RisingEdge(dut.CLK)
            await NextTimeStep()

        # Hit all read addresses 0–3 (normal working)
        for addr in range(4):
            read_address_cover(addr)
            await read_drv._driver_sent(addr)
            
    #Setting the fifo-a full flag
    await write_drv._driver_sent(4, a)
    await write_drv._driver_sent(4, a)
    await write_drv._driver_sent(4, a)
    for addr in range(3):
        read_address_cover(addr)
        await read_drv._driver_sent(addr)
        
    #Setting the fifo-b full flag
    await write_drv._driver_sent(5, b)
    await write_drv._driver_sent(5, b)
    await write_drv._driver_sent(5, b)
    for addr in range(3):
        read_address_cover(addr)
        await read_drv._driver_sent(addr)
        
    # Generate and save coverage report
    coverage_db.report_coverage(cocotb.log.info, bins=True)
    coverage_file = os.path.join(os.getenv("RESULT_PATH", "./"), 'coverage.xml')
    coverage_db.export_to_xml(filename=coverage_file)

    if failed_tests > 0:
        raise Exception(f"Tests failed: {failed_tests}")
    elif expected_value:
        raise Exception(f"Test completed but {len(expected_value)} expected values weren't checked")
    print("All test vectors passed successfully!")

class InputDriver(BusDriver):
    _signals = ["write_en", "write_address", "write_data", "write_rdy"]

    def __init__(self, dut, name, clk):
        super().__init__(dut, name, clk)
        self.bus.write_en.value = 0
        self.bus.write_address.value = 0
        self.bus.write_data.value = 0
        self.clk = clk

    async def _driver_sent(self, address, data, sync=True):
        for l in range(random.randint(1, 200)):
            await RisingEdge(self.clk)
        while not self.bus.write_rdy.value:
            await RisingEdge(self.clk)
        self.bus.write_en.value = 1
        self.bus.write_address.value = address
        self.bus.write_data.value = data
        await ReadOnly()
        await RisingEdge(self.clk)
        await NextTimeStep()
        self.bus.write_en.value = 0

class InputMonitor(BusMonitor):
    _signals = ["write_en", "write_address", "write_data", "write_rdy"]

    async def _monitor_recv(self):
        phasesW = {1: "IdleWrite", 3: "TxnWrite"} 
        prevW = "IdleWrite"
        while True:
            await FallingEdge(self.clock)
            await ReadOnly()
            TxnWrite = (int(self.bus.write_en.value) << 1) | int(self.bus.write_rdy.value)
            stateW = phasesW.get(TxnWrite)
            if stateW:
                in_port_cover({'previousWrite': prevW, 'currentWrite': stateW})
                prevW = stateW


class OutputDriver(BusDriver):
    _signals = ["read_en", "read_address", "read_data", "read_rdy"]

    def __init__(self, dut, name, clk, sb_callback):
        super().__init__(dut, name, clk)
        self.bus.read_en.value = 0
        self.bus.read_address.value = 0
        self.clk = clk
        self.callback = sb_callback

    async def _driver_sent(self, address, sync=True):
        for k in range(random.randint(1, 200)):
            await RisingEdge(self.clk)
        while not self.bus.read_rdy.value:
            await RisingEdge(self.clk)
        self.bus.read_en.value = 1
        self.bus.read_address.value = address
        await ReadOnly()

        # Check scoreboard for y_output (address 3)
        if self.callback and address == 3:
            self.callback(int(self.bus.read_data.value))
        elif address in [0, 1, 2]:
            cocotb.log.info(f"address={address}, value={int(self.bus.read_data.value)}")

        await RisingEdge(self.clk)
        await NextTimeStep()
        self.bus.read_en.value = 0

class OutputMonitor(BusMonitor):
    _signals = ["read_en", "read_address", "read_data", "read_rdy"]

    async def _monitor_recv(self):
        phasesR = {1: "IdleRead", 3: "TxnRead"}
        prevR = "IdleRead"
        while True:
            await FallingEdge(self.clock)
            await ReadOnly()
            TxnRead = (int(self.bus.read_en.value) << 1) | int(self.bus.read_rdy.value)
            stateR = phasesR.get(TxnRead)
            if stateR:
                out_port_cover({'previousRead': prevR, 'currentRead': stateR})
                prevR = stateR