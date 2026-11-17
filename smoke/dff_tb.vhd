-- Testbench em VHDL-2008, para o GHDL sem cocotb.
library ieee;
use ieee.std_logic_1164.all;

entity dff_tb is
end entity dff_tb;

architecture sim of dff_tb is
  signal clk : std_logic := '0';
  signal d   : std_logic := '0';
  signal q   : std_logic;
begin
  dut : entity work.dff
    port map (clk => clk, d => d, q => q);

  clk <= not clk after 5 ns;

  process
  begin
    d <= '1';
    wait for 10 ns;
    if q /= '1' then
      report "SMOKE_FAIL q=" & std_logic'image(q);
    else
      report "SMOKE_OK";
    end if;
    std.env.finish;
  end process;
end architecture sim;
