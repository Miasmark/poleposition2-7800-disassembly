-- Look at the raw bytes around each clock reset, rather than trusting a decode.
local M = (type(manager.machine)=="function") and manager:machine() or manager.machine
local mem = M.devices[":maincpu"].spaces["program"]
local F = 0
local W = {3396,3402,3408,3414, 6498,6504,6510,6516, 8808,8814,8820,8826}
local want = {}
for _,f in ipairs(W) do want[f]=true end
emu.register_frame_done(function()
  F = F + 1
  if not want[F] then if F>=8830 then M:exit() end return end
  local t = {}
  for a = 0xDB, 0xE2 do t[#t+1] = string.format("%02X", mem:read_u8(a)) end
  print(string.format("f%-6d  $DB-$E2: %s", F, table.concat(t, " ")))
  if F >= 8826 then M:exit() end
end)
