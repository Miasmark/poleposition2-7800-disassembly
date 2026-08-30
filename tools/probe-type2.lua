-- Photograph the type-2 object at close range, to see what it actually is.
local M=(type(manager.machine)=="function") and manager:machine() or manager.machine
local mem=M.devices[":maincpu"].spaces["program"]
local TYPE,ZLO,ZHI=0x19B4,0x19C4,0x19D4
local F,n,last=0,0,-999
emu.register_frame_done(function()
  F=F+1
  if F<6000 or n>=6 then if F>=11060 then M:exit() end return end
  for x=0,15 do
    if mem:read_u8(TYPE+x)%8==2 then
      local z=mem:read_u8(ZHI+x)*256+mem:read_u8(ZLO+x)
      if z>120 and z<300 and F-last>120 then
        n=n+1; last=F
        print(string.format("snap %d  f%d  slot %X  z=%d  lat=%d  playerx=$%02X",
              n,F,x,z,mem:read_u8(0x1A00+x),mem:read_u8(0x00D1)))
        M.video:snapshot()
        break
      end
    end
  end
  if F>=11060 then M:exit() end
end)
