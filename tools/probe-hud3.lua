-- Test two readings at once:
--   $19D4 is speed  -- should track the throttle and sit high while driving
--   $30 is the digit '0' -- if so the score is a run of digit CHARACTERS,
--   not packed BCD, and a scoring event moves one of these runs.
local M = (type(manager.machine)=="function") and manager:machine() or manager.machine
local mem = M.devices[":maincpu"].spaces["program"]
local F = 0
emu.register_frame_done(function()
  F = F + 1
  if F % 300 ~= 0 or F < 5400 or F > 11400 then return end
  local d = {}
  for a = 0x2078, 0x209B do d[#d+1] = string.format("%02X", mem:read_u8(a)) end
  print(string.format("f%-6d clock=%02X%02X speed($19D4)=%3d ($20B9)=%3d  $2078-$209B: %s",
        F, mem:read_u8(0xDE), mem:read_u8(0xDF),
        mem:read_u8(0x19D4), mem:read_u8(0x20B9), table.concat(d, " ")))
  if F >= 11400 then M:exit() end
end)
