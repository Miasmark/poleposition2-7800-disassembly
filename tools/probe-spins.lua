-- spins.lua -- exact cycles burnt in each known wait loop, per frame.
-- Each loop is "load flag / branch back", 6 cycles an iteration (zp load 3,
-- taken branch 3, same page); the vblank spin is BIT zp / BPL, also 6.
local M=(type(manager.machine)=="function") and manager:machine() or manager.machine
local cpu=M.devices[":maincpu"]
local mem=cpu.spaces["program"]
local out=os.getenv("IDLE_OUT") or "spins"
local a=tonumber(os.getenv("IDLE_FROM") or "1400")
local b=tonumber(os.getenv("IDLE_TO") or "3600")
local SPINS={ {name="stage wait  $EA28 (B8)",addr=0xB8,pc=0xEA28,cyc=6},
              {name="dl wait     $E709 (E5)",addr=0xE5,pc=0xE709,cyc=6},
              {name="vblank spin $DB8E (MSTAT)",addr=0x28,pc=0xDB8E,cyc=6},
              {name="tick spin   $D253 (B9)",addr=0xB9,pc=0xD253,cyc=9} }
local f=0
local cur, tot, frames = {}, {}, 0
TAPS={}
for i,s in ipairs(SPINS) do
  cur[i]=0; tot[i]={}
  TAPS[i]=mem:install_read_tap(s.addr,s.addr,"s"..i,function(o,d)
    if f>=a and f<=b then
      local pc=cpu.state["PC"].value
      if pc>=s.pc and pc<=s.pc+2 then cur[i]=cur[i]+1 end
    end
    return d
  end)
end
emu.register_frame_done(function()
  f=f+1
  if f>=a and f<=b then
    frames=frames+1
    for i=1,#SPINS do table.insert(tot[i],cur[i]); cur[i]=0 end
  else for i=1,#SPINS do cur[i]=0 end end
  if f>b then
    local o=io.open(out..".txt","w")
    local all={}
    for i,s in ipairs(SPINS) do
      local v=tot[i]; table.sort(v)
      local sum=0; for _,x in ipairs(v) do sum=sum+x end
      o:write(string.format("%-28s p10 %6d  median %6d  mean %7.0f cycles/frame",
        s.name, v[math.floor(#v*0.1)+1]*s.cyc, v[math.floor(#v/2)+1]*s.cyc, sum/#v*s.cyc)..string.char(10))
    end
    o:close(); M:exit()
  end
end)
