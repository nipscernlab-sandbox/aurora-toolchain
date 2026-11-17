# Compila e roda o test_dff.py pelo runner do cocotb, no simulador de $SIM:
# o dff.v no Icarus e no Verilator, o dff.vhd no GHDL.
import os
from pathlib import Path

from cocotb_tools.runner import get_runner

here = Path(__file__).parent
sim = os.environ["SIM"]
build_dir = Path.cwd() / f"sim_{sim}"
runner = get_runner(sim)
if sim == "ghdl":
    # O GHDL usa o 93c sem --std; o mcode elabora de novo no -r, que precisa
    # da mesma opção da análise. O runner roda o -r na pasta do teste, e a
    # biblioteca ficou na do build: o --workdir diz onde ela está.
    runner.build(
        sources=[here / "dff.vhd"],
        hdl_toplevel="dff",
        build_dir=build_dir,
        build_args=["--std=08"],
        always=True,
        waves=True,
    )
    test_args = ["--std=08", f"--workdir={build_dir}"]
else:
    runner.build(
        sources=[here / "dff.v"],
        hdl_toplevel="dff",
        build_dir=build_dir,
        build_args=["-g2012"] if sim == "icarus" else [],
        timescale=("1ns", "1ps"),
        always=True,
        waves=True,
    )
    test_args = []
runner.test(
    hdl_toplevel="dff",
    test_module="test_dff",
    build_dir=build_dir,
    test_dir=here,
    test_args=test_args,
    waves=True,
)
print(f"SMOKE_OK cocotb-{sim}")
