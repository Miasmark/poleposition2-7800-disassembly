-- walkchk.lua -- at the end of each complete walk, record its input snapshot,
-- the track tables and all 13 band outputs, for an independent recomputation.
local M=(type(manager.machine)=="function") and manager:machine() or manager.machine
local cpu=M.devices[":maincpu"]
local mem=cpu.spaces["program"]
local done=tonumber(os.getenv("W_DONE"),16)
local o=io.open(os.getenv("W_OUT"),"w")
local n,f=0,0
local function hex(a,len) local t={} for i=0,len-1 do t[#t+1]=string.format("%02X",mem:read_u8(a+i)) end return table.concat(t) end
TAPS={}
TAPS[1]=mem:install_read_tap(done,done,"wd",function(o_,d)
  if cpu.state["PC"].value==done and mem:read_u8(0x2756)==0 and n<400 then
    n=n+1
    o:write(string.format("%d %s %s %02X %s",f,hex(0x2750,3),hex(0x2760,13),mem:read_u8(0x00C1),
      hex(0x1800,512))..string.char(10))
  end
  return d end)
emu.register_frame_done(function() f=f+1; if f>=6000 then o:close(); M:exit() end end)
