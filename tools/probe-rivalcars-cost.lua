-- rccost.lua -- RivalCars' time per call (entry to the return at rom:D719), in
-- scanlines, during racing; and the stage wait's idle per 6-frame cycle.
local M=(type(manager.machine)=="function") and manager:machine() or manager.machine
local cpu=M.devices[":maincpu"]
local mem=cpu.spaces["program"]
local ENT=tonumber(os.getenv("ENT"),16)
local LINE=1/(59.9224*262)
local t0,f=nil,0
local d={}
local idle,cyc,cycles={},0,{}
TAPS={}
TAPS[1]=mem:install_read_tap(ENT,ENT,"e",function(a,v) if cpu.state["PC"].value==ENT then t0=M.time:as_double() end return v end)
TAPS[2]=mem:install_read_tap(0xD719,0xD719,"r",function(a,v)
  local st=mem:read_u8(0x9D)
  if cpu.state["PC"].value==0xD719 and t0 and (st==2 or st==3) then d[#d+1]=(M.time:as_double()-t0)/LINE end
  t0=nil; return v end)
TAPS[3]=mem:install_read_tap(0xB8,0xB8,"s",function(a,v) if cpu.state["PC"].value>=0xEA28 and cpu.state["PC"].value<=0xEA2A then cyc=cyc+6 end return v end)
TAPS[4]=mem:install_read_tap(0xEA2C,0xEA2C,"c",function(a,v)
  local st=mem:read_u8(0x9D)
  if cpu.state["PC"].value==0xEA2C and (st==2 or st==3) then cycles[#cycles+1]=cyc end
  cyc=0; return v end)
emu.register_frame_done(function()
  f=f+1
  if f>=tonumber(os.getenv("FR")) then
    table.sort(d); table.sort(cycles)
    local zero=0 for _,c in ipairs(cycles) do if c==0 then zero=zero+1 end end
    local o=io.open(os.getenv("O"),"w")
    o:write(string.format("RivalCars: n=%d median %.1f p90 %.1f max %.1f lines | stage-wait idle per cycle: median %d, min %d cycles; cycles with none: %d of %d",
      #d,d[math.floor(#d/2)+1] or 0,d[math.floor(#d*0.9)+1] or 0,d[#d] or 0,cycles[math.floor(#cycles/2)+1] or 0,cycles[1] or 0,zero,#cycles)..string.char(10))
    o:close(); M:exit()
  end
end)
