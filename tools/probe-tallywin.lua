-- Locate the tally precisely: an arcade end-of-race count drains the clock
-- into the score, so the signature is $DF falling far faster than its normal
-- one-per-30-frames.
local M = (type(manager.machine)=="function") and manager:machine() or manager.machine
local mem = M.devices[":maincpu"].spaces["program"]
local F, prev, run = 0, nil, 0
emu.register_frame_done(function()
  F = F + 1
  if F < 9000 then return end
  local v = mem:read_u8(0xDF)
  if prev ~= nil and v ~= prev then
    print(string.format("f%-6d  $DF %02X -> %02X", F, prev, v))
  end
  prev = v
  if F >= 11940 then M:exit() end
end)
