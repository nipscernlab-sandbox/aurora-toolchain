#!/usr/bin/env python3
"""Roda os seis fluxos contra o bundle: o portão de toda release.

    python scripts/smoke.py dist/msys

Icarus, Verilator, GHDL e o cocotb com cada um, sobre o flip-flop de smoke/
(dff.v para os de Verilog, dff.vhd para o GHDL), com só o bundle no PATH
(mais o System32). Um fluxo passa quando termina sem erro e imprime
SMOKE_OK. Sai com erro se algum falhar, mostrando o fim da saída dele.

Roda no Windows, depois do trim.py: é ele que diz se o enxugamento cortou
demais.
"""

import argparse
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from common import SMOKE, bundle_env, bundle_python, require_windows, say


def flow(name: str, cmd: list, cwd: Path, env: dict, smoke_ok: bool = True) -> bool:
    """Roda um passo. O que simula tem que imprimir SMOKE_OK (`smoke_ok`); o
    que só compila (iverilog, verilator --binary) basta sair com 0."""
    print(f"  {name}: " + " ".join(str(c) for c in cmd), flush=True)
    result = subprocess.run(
        [str(c) for c in cmd],
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
    )
    ok = result.returncode == 0 and (not smoke_ok or "SMOKE_OK" in result.stdout)
    if not ok:
        tail = "\n".join(result.stdout.splitlines()[-40:])
        print(f"----- {name}: código {result.returncode} -----\n{tail}\n-----", flush=True)
    return ok


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("bundle", type=Path, help="a pasta do bundle (dist/msys)")
    args = parser.parse_args()
    require_windows("O smoke")
    bundle = args.bundle.resolve()
    bin_dir = bundle / "ucrt64" / "bin"
    env = bundle_env(bundle)

    # O caminho longo: o %TEMP% do runner vem com o nome curto do Windows
    # (C:\Users\RUNNER~1), e o script do Verilator troca o ~ por \~.
    work = Path(tempfile.mkdtemp(prefix="lace-smoke-")).resolve()
    for f in SMOKE.iterdir():
        if f.is_file():
            shutil.copy2(f, work)

    results = {}
    (work / "icarus").mkdir()
    results["icarus"] = flow(
        "icarus",
        [bin_dir / "iverilog.exe", "-g2012", "-o", "sim.vvp", work / "dff.v", work / "dff_tb.v"],
        work / "icarus",
        env,
        smoke_ok=False,
    ) and flow("icarus", [bin_dir / "vvp.exe", "-n", "sim.vvp"], work / "icarus", env)

    # Como o Lace roda o Verilator: o script pelo Perl, que chama o
    # verilator_bin ao lado dele; o --binary chama o make (o da camada MSYS),
    # que roda o g++ do bundle.
    (work / "verilator").mkdir()
    results["verilator"] = flow(
        "verilator",
        [
            bin_dir / "perl.exe",
            bin_dir / "verilator",
            "--binary",
            # As opções de aviso do Lace (simulate.rs): sem elas, um módulo
            # sem `timescale ao lado de um que tem para o build.
            "-Wno-fatal",
            "-Wno-TIMESCALEMOD",
            "--top-module",
            "dff_tb",
            "-Mdir",
            "obj",
            work / "dff.v",
            work / "dff_tb.v",
        ],
        work / "verilator",
        env,
        smoke_ok=False,
    ) and flow("verilator", [work / "verilator" / "obj" / "Vdff_tb.exe"], work / "verilator", env)

    # Como a AURORA roda o GHDL: VHDL-2008 em todos os passos (o mcode
    # elabora de novo no -r) e a biblioteca de trabalho numa pasta própria,
    # que o GHDL não cria sozinho. O -r grava a onda em GHW.
    ghdl = [bin_dir / "ghdl.exe"]
    (work / "ghdl" / "work").mkdir(parents=True)
    common = ["--std=08", "--workdir=work"]
    results["ghdl"] = (
        flow("ghdl", [*ghdl, "-a", *common, work / "dff.vhd", work / "dff_tb.vhd"], work / "ghdl", env, smoke_ok=False)
        and flow("ghdl", [*ghdl, "-e", *common, "dff_tb"], work / "ghdl", env, smoke_ok=False)
        and flow("ghdl", [*ghdl, "-r", *common, "dff_tb", "--wave=dff_tb.ghw"], work / "ghdl", env)
        and (work / "ghdl" / "dff_tb.ghw").is_file()
    )

    # O Python do bundle roda o runner do cocotb, que chama o simulador e
    # carrega a VPI. PYTHONHOME como no smoke da AURORA, que passou assim.
    for sim in ("icarus", "verilator", "ghdl"):
        language = "vhdl" if sim == "ghdl" else "verilog"
        cocotb_env = dict(env, SIM=sim, TOPLEVEL_LANG=language, PYTHONHOME=str(bundle / "ucrt64"))
        if sim == "ghdl":
            # A VPI do cocotb para o GHDL carrega a libghdlvpi.dll, que o
            # pacote põe em ucrt64/lib, não em ucrt64/bin; o Makefile.ghdl do
            # cocotb também a põe no PATH.
            cocotb_env["PATH"] = os.pathsep.join([str(bundle / "ucrt64" / "lib"), env["PATH"]])
        results[f"cocotb-{sim}"] = flow(
            f"cocotb-{sim}",
            [bundle_python(bundle), work / "run_cocotb.py"],
            work,
            cocotb_env,
        )

    shutil.rmtree(work, ignore_errors=True)
    for name, ok in results.items():
        print(f"  {'PASSOU' if ok else 'FALHOU'}  {name}")
    passed = sum(results.values())
    say(f"{passed} de {len(results)} fluxos passaram")
    if passed != len(results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
