-- probe-overlay-shots.lua -- screenshots of player 2's highlights in player
-- 1's view: each frame, scan player 1's lists ($2200-$25FF) for a header with
-- palette 4 / 8 bytes ($98) and a page in the highlight column ($70-$7F), not
-- parked; snapshot up to six, 300+ frames apart. Loose match: stock headers
-- can pass too, so check the low byte is a lean ($00-$20). Env: O, END.
local M=(type(manager.machine)=="function") and manager:machine() or manager.machine
local mem=M.devices[":maincpu"].spaces["program"]
local f,last,shots,hits=0,-10000,0,0
local o=io.open(os.getenv("O"),"w")
emu.register_frame_done(function() f=f+1
  local found=nil
  for a=0x2200,0x25FC do
    if mem:read_u8(a+1)==0x98 then local h=mem:read_u8(a+2) if h>=0x70 and h<=0x7F and mem:read_u8(a+3)~=0xA1 then found=a break end end end
  if found then hits=hits+1
    if f-last>300 and shots<6 then last=f; shots=shots+1; M.video:snapshot()
      o:write(string.format("f%d at %04X lo=%02X hi=%02X x=%02X st=%02X\n",f,found,mem:read_u8(found),mem:read_u8(found+2),mem:read_u8(found+3),mem:read_u8(0x9D))) end end
  if f>=tonumber(os.getenv("END")) then o:write("hit frames "..hits.."\n") o:close() M:exit() end end)
