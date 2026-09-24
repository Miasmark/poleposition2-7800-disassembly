local tlast=-1; local tsn=0; local tent=0
local function bcd3(a) return string.format("%02X%02X%02X",mem:read_u8(a),mem:read_u8(a+1),mem:read_u8(a+2)) end
emu.register_frame_done(function() local st=mem:read_u8(0x9D)
 local tal=(st==0x0F or st==0x08 or st==0x0D or st==0x0A)
 if st~=tlast and (tal or tlast==0x0F or tlast==0x08) then tent=f
   o:write(string.format("TS f%d st=%02X AC=%02X AB=%02X p2tbs=%02X p2cars=%02X%02X s1=%s s2=%s p1out=%d p2rst=%d",f,st,mem:read_u8(0xAC),mem:read_u8(0xAB),mem:read_u8(0x202D),mem:read_u8(0x273B),mem:read_u8(0x273A),bcd3(0x1CA5),bcd3(0x2770),mem:read_u8(0x2736),mem:read_u8(0x2734))..string.char(10)) end
 if (st==0x0F or st==0x08) and (f-tent)==40 and tsn<8 then tsn=tsn+1; M.video:snapshot() end
 if (st==0x0D) and (f-tent)==30 and tsn<9 then tsn=tsn+1; M.video:snapshot() end
 tlast=st end)
