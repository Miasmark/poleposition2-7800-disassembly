-- The race clock is a 16-bit BCD pair: $DE hundreds, $DF tens and units.
-- Print it only when it JUMPS UP (a reset) or reaches zero, so the lap
-- allowances the manual describes can be checked against what the game does.
local M = (type(manager.machine)=="function") and manager:machine() or manager.machine
local mem = M.devices[":maincpu"].spaces["program"]
local F, prev = 0, nil
local function bcd(h, l) return (h>>4)*1000 + (h&15)*100 + (l>>4)*10 + (l&15) end
emu.register_frame_done(function()
  F = F + 1
  if F % 6 ~= 0 then return end
  local v = bcd(mem:read_u8(0xDE), mem:read_u8(0xDF))
  if prev == nil then prev = v; return end
  if v > prev + 2 then
    print(string.format("f%-6d  clock RESET  %d -> %d", F, prev, v))
  elseif v == 0 and prev ~= 0 then
    print(string.format("f%-6d  clock reached ZERO (from %d)", F, prev))
  end
  prev = v
  if F >= 11942 then print("end of recording, clock = "..v); M:exit() end
end)
