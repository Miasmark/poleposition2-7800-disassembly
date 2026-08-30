-- After each reset, does $DE stay put while $DF counts down (so $DE is not
-- part of the clock), or do they move together as a pair?
local M = (type(manager.machine)=="function") and manager:machine() or manager.machine
local mem = M.devices[":maincpu"].spaces["program"]
local F = 0
emu.register_frame_done(function()
  F = F + 1
  local show = (F >= 3400 and F <= 3700) or (F >= 6500 and F <= 6800)
  if not show or F % 30 ~= 0 then if F > 6800 then M:exit() end return end
  print(string.format("f%-6d  $DD=%02X  $DE=%02X  $DF=%02X", F,
        mem:read_u8(0xDD), mem:read_u8(0xDE), mem:read_u8(0xDF)))
  if F > 6800 then M:exit() end
end)
