-- Speed is $CE, a single binary byte (saturates at 255). Sharp losses of speed
-- are events: a sign or car struck stops you dead, a puddle or a skid bleeds
-- speed off while you keep steering. Report every significant drop with the
-- clock and lap time, so they can be matched against what happened in the run.
local M=(type(manager.machine)=="function") and manager:machine() or manager.machine
local mem=M.devices[":maincpu"].spaces["program"]
local F,prev,lastrep=0,nil,-999
emu.register_frame_done(function()
  F=F+1
  local v=mem:read_u8(0xCE)
  if prev then
    local drop=prev-v
    if drop >= 25 and F-lastrep > 30 then
      print(string.format("f%-6d  speed %3d -> %3d  (-%3d)   clock=%02X%02X  lap=%02X%02X:%02X",
            F, prev, v, drop, mem:read_u8(0xDE), mem:read_u8(0xDF),
            mem:read_u8(0xBE), mem:read_u8(0xBD), mem:read_u8(0xBC)))
      lastrep=F
    end
  end
  prev=v
  if F>=11940 then M:exit() end
end)
