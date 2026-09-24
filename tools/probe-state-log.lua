local M=(type(manager.machine)=="function") and manager:machine() or manager.machine
local mem=M.devices[":maincpu"].spaces["program"]
local f,last=0,-1; local o=io.open(os.getenv("O"),"w")
emu.register_frame_done(function() f=f+1; local st=mem:read_u8(0x9D)
  if st~=last then o:write(string.format("f%d st=%02X clk=%02X%02X spd=%d p2spd=%d a7=%d\n",f,st,mem:read_u8(0xDE),mem:read_u8(0xDF),mem:read_u8(0xCE),mem:read_u8(0x2753),mem:read_u8(0xA7))); last=st end
  if f>=12000 then o:close(); M:exit() end end)
