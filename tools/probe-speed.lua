-- Screen reads: f4200 speed 158, gear LO, UNIT 69, LAP 02:79
--               f10600 speed 241, gear HI, UNIT 11, LAP 180:62
-- Fingerprint speed under both plausible encodings, and find the gear as a
-- byte that holds one value at the first frame and another at the second.
local M=(type(manager.machine)=="function") and manager:machine() or manager.machine
local mem=M.devices[":maincpu"].spaces["program"]
local LO,HI=0x1800,0x27FF
local F,s1=0,nil
emu.register_frame_done(function()
  F=F+1
  if F==4200 then
    s1={} for a=LO,HI do s1[a]=mem:read_u8(a) end
  elseif F==10600 and s1 then
    print("=== speed as a single binary byte: $9E then $F1 ===")
    for a=LO,HI do
      if s1[a]==0x9E and mem:read_u8(a)==0xF1 then
        print(string.format("  $%04X   neighbours %02X %02X -> %02X %02X",
              a, s1[a-1], s1[a+1], mem:read_u8(a-1), mem:read_u8(a+1)))
      end
    end
    print("=== speed as two BCD bytes: 01 58 then 02 41 ===")
    for a=LO,HI-1 do
      if s1[a]==0x01 and s1[a+1]==0x58 and mem:read_u8(a)==0x02 and mem:read_u8(a+1)==0x41 then
        print(string.format("  $%04X-$%04X  hundreds+tens/units", a, a+1))
      end
      if s1[a]==0x58 and s1[a+1]==0x01 and mem:read_u8(a)==0x41 and mem:read_u8(a+1)==0x02 then
        print(string.format("  $%04X-$%04X  tens/units+hundreds (low first)", a, a+1))
      end
    end
    print("=== gear: differs between the two frames, few distinct values ===")
    local n=0
    for a=LO,HI do
      local x,y=s1[a],mem:read_u8(a)
      if x~=y and x<=3 and y<=3 then
        n=n+1
        if n<=12 then print(string.format("  $%04X   %d -> %d", a, x, y)) end
      end
    end
    print(string.format("  %d gear candidates", n))
    M:exit()
  end
end)
