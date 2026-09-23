-- probe-world.lua -- at every return of RivalCars (rom:D719): the gap, both
-- players' object segments, and every live slot. Track tables once per track.
local M=(type(manager.machine)=="function") and manager:machine() or manager.machine
local cpu=M.devices[":maincpu"]; local mem=cpu.spaces["program"]
local o=io.open(os.getenv("O"),"w")
local f=0; local lastT=-1
local function s16(a) local v=mem:read_u8(a)+256*mem:read_u8(a+1); if v>=32768 then v=v-65536 end return v end
TAPS={}
TAPS[1]=mem:install_read_tap(0xD719,0xD719,"w",function(a,v)
  if cpu.state["PC"].value==0xD719 then
    local st=mem:read_u8(0x9D)
    if st==2 or st==3 then
      local t=mem:read_u8(0xC4)
      if t~=lastT then lastT=t; local n=mem:read_u8(0xC2); local q={}
        for i=0,n-1 do q[#q+1]=string.format("%02X:%d",mem:read_u8(0x18B4+i),mem:read_u8(0x18D7+i)+256*mem:read_u8(0x195A+i)) end
        o:write("T "..t.." "..table.concat(q," ")..string.char(10)) end
      local ae=mem:read_u8(0xAE)
      o:write(string.format("f%d %02X %d gap=%d A0=%d A2=%d B0=%d B2=%d act=%d |",f,st,t,s16(0x275C),s16(0xA0),mem:read_u8(0xA2),s16(0x2792),mem:read_u8(0x2794),mem:read_u8(0x2791)))
      if ae<16 then for i=0,ae do local s=mem:read_u8(0x19A4+i)
        o:write(string.format(" %d:%02X:%d",s,mem:read_u8(0x19B4+s),s16(0x19C4+s) and (mem:read_u8(0x19C4+s)+256*mem:read_u8(0x19D4+s)))) end end
      o:write(string.char(10))
    end
  end
  return v end)
emu.register_frame_done(function() f=f+1; if f>=tonumber(os.getenv("FR")) then o:close(); M:exit() end end)
