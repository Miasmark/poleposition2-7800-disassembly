-- probe-p2-objects-gap0.lua -- equality test: for player 2's object pass only, the camera gap
-- is forced to 0 (restored when the pass returns). Player 2's world entries
-- must then match player 1's list in row, bottom row, sprite page/low, and
-- palette/width -- everything but x, which is player 2's own camera.
-- env: START (hex, RcP2Objs), DONE (hex, P2ObDone's RTS), FR, O. The symbols
-- come from splitscreen._ext()[1].
local M=(type(manager.machine)=="function") and manager:machine() or manager.machine
local cpu=M.devices[":maincpu"]
local mem=cpu.spaces["program"]
local o=io.open(os.getenv("O"),"w")
local DONE=tonumber(os.getenv("DONE"),16)
local START=tonumber(os.getenv("START"),16)
local f,glo,ghi,objstart=0,0,0,0
local function pc() return cpu.state["PC"].value end
local function ent(i) return string.format("%02X/%02X/%02X%02X/%02X",mem:read_u8(0x1A94+i),mem:read_u8(0x1AA9+i),
  mem:read_u8(0x1ABE+i),mem:read_u8(0x1AD3+i),mem:read_u8(0x1BEA+i)) end
TAPS={}
TAPS[1]=mem:install_read_tap(START,START,"r",function(a,v)
  if pc()==START then
    local st=mem:read_u8(0x9D)
    if st==2 or st==3 then
      glo,ghi=mem:read_u8(0x275C),mem:read_u8(0x275D)
      objstart=mem:read_u8(0x274A)
      mem:write_u8(0x275C,0); mem:write_u8(0x275D,0)
    else objstart=-1 end
  end
  return v end)
TAPS[2]=mem:install_read_tap(DONE,DONE,"r",function(a,v)
  if pc()==DONE and objstart>=0 then
    mem:write_u8(0x275C,glo); mem:write_u8(0x275D,ghi)
    local dd,e=mem:read_u8(0xDD),mem:read_u8(0x274A)
    local p1,p2={},{}
    for i=1,dd-1 do p1[#p1+1]=ent(i)..":"..string.format("%02X",mem:read_u8(0x1A7F+i)) end
    for i=objstart,e-1 do p2[#p2+1]=ent(i) end
    o:write(string.format("f%d gap=%02X%02X P1 %s | P2 %s\n",f,ghi,glo,table.concat(p1," "),table.concat(p2," ")))
    objstart=-1
  end
  return v end)
emu.register_frame_done(function() f=f+1; if f>=tonumber(os.getenv("FR")) then o:close(); M:exit() end end)
