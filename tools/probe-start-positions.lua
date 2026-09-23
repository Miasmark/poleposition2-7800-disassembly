-- probe-start-positions.lua -- both players' lateral positions (player 1's terms), the
-- gap and both speeds 1, 30 and 90 frames into each of states $10, $11, $02,
-- $03 (the banners and the drives). env: O, FR.
local M=(type(manager.machine)=="function") and manager:machine() or manager.machine
local mem=M.devices[":maincpu"].spaces["program"]
local o=io.open(os.getenv("O"),"w"); local f=0; local prev=-1; local mark=nil
local function s8(v) if v>=128 then return v-256 end return v end
emu.register_frame_done(function() f=f+1
  local st=mem:read_u8(0x9D)
  if st~=prev then prev=st; if st==0x10 or st==0x11 or st==2 or st==3 then mark=f end end
  if mark and (f-mark==1 or f-mark==30 or f-mark==90) then
    local g=mem:read_u8(0x275C)+256*mem:read_u8(0x275D); if g>=32768 then g=g-65536 end
    o:write(string.format("f%d state %02X +%d: player 1 x %d, player 2 x %d (P2_LATERAL %d), gap %d, speeds %d %d\n",f,st,f-mark,s8(mem:read_u8(0xD1)),-s8(mem:read_u8(0x2702)),s8(mem:read_u8(0x2702)),g,mem:read_u8(0xCE),mem:read_u8(0x2753))) end
  if f>=tonumber(os.getenv("FR")) then o:close(); M:exit() end end)
