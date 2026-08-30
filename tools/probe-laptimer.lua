-- The lap timer reads 80:62 at frame 7000 and 136:14 at frame 9000, straight
-- off the screen. That is an exact fingerprint: find the bytes holding $80/$62
-- at the first and $36/$14 at the second, with a hundreds digit going 0 -> 1.
local M=(type(manager.machine)=="function") and manager:machine() or manager.machine
local mem=M.devices[":maincpu"].spaces["program"]
local LO,HI=0x1800,0x27FF
local F,a1=0,nil
emu.register_frame_done(function()
  F=F+1
  if F==7000 then
    a1={}
    for a=LO,HI do a1[a]=mem:read_u8(a) end
  elseif F==9000 and a1 then
    print("=== bytes matching the lap timer's two readings ===")
    local n=0
    for a=LO,HI do
      local v=mem:read_u8(a)
      -- hundredths: $62 then $14
      if a1[a]==0x62 and v==0x14 then
        n=n+1
        print(string.format("  $%04X  hundredths  ($62 -> $14)   neighbours: %02X %02X | %02X %02X",
              a, a1[a-1], a1[a-2], mem:read_u8(a-1), mem:read_u8(a-2)))
      end
      -- seconds: $80 then $36
      if a1[a]==0x80 and v==0x36 then
        n=n+1
        print(string.format("  $%04X  seconds     ($80 -> $36)   next: %02X | %02X",
              a, a1[a+1], mem:read_u8(a+1)))
      end
    end
    print(string.format("  %d matches", n))
    M:exit()
  end
end)
