-- entries.lua -- the moment sub_E286 returns (rom:D719), record the drawable
-- entry list it built and the world data behind it, for a model to reproduce.
local M=(type(manager.machine)=="function") and manager:machine() or manager.machine
local cpu=M.devices[":maincpu"]
local mem=cpu.spaces["program"]
local o=io.open(os.getenv("O"),"w")
local n,f=0,0
local function hx(a,len) local t={} for i=0,len-1 do t[#t+1]=string.format("%02X",mem:read_u8(a+i)) end return table.concat(t) end
TAPS={}
TAPS[1]=mem:install_read_tap(0xD719,0xD719,"e",function(o_,d)
  if cpu.state["PC"].value==0xD719 and n<600 and f>1500 then
    local st=mem:read_u8(0x9D)
    if st==2 or st==3 then
      n=n+1
      -- zero page $40-$FF (folded at $2040), entry arrays $1A7F-$1BFF, world $19A4-$1A7E, road $1A2E-$1A7E
      o:write(string.format("%d %s %s %s",f,hx(0x2040,0xC0),hx(0x1900,0x300),hx(0x1C00,0x100))..string.char(10))
    end
  end
  return d end)
emu.register_frame_done(function() f=f+1; if f>=25000 then o:close(); M:exit() end end)
