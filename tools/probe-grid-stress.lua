-- stress.lua -- start player 1 at grid position POS; through the rolling start
-- and the race, after each emitter pass (rom:E7E8) check player 1's own car
-- slot in bands 7-11 still holds player 1's car, count cap drops, note whether
-- player 2's car was listed, and take screenshots at SHOTS frames into the race.
local M=(type(manager.machine)=="function") and manager:machine() or manager.machine
local cpu=M.devices[":maincpu"]
local mem=cpu.spaces["program"]
local CF=tonumber(os.getenv("CF"),16)
local o=io.open(os.getenv("O"),"w")
local shots={}
for w in string.gmatch(os.getenv("SHOTS") or "", "%d+") do shots[tonumber(w)]=true end
local f,start=0,nil
local passes,bad,drops,listed,inview=0,0,0,0,0
local worstband=0
TAPS={}
TAPS[1]=mem:install_read_tap(CF,CF,"cf",function(a,d) if cpu.state["PC"].value==CF then drops=drops+1 end return d end)
TAPS[2]=mem:install_read_tap(0xE7E8,0xE7E8,"end",function(a,d)
  local st=mem:read_u8(0x9D)
  if cpu.state["PC"].value==0xE7E8 and (st==3 or st==0x11) then
    passes=passes+1
    -- player 1's car entry is entry 0: its bands are those of rows $1A94[0]..$1AA9[0]
    local lo,pw,x=mem:read_u8(0x1AD3),mem:read_u8(0x1BEA),mem:read_u8(0x1AE8)
    local b1=mem:read_u8(0xBB7E+mem:read_u8(0x1AA9)); local b0=mem:read_u8(0xBB7E+mem:read_u8(0x1A94))
    for b=b1,b0 do
      local p=mem:read_u8(0x9DDD+b)+256*mem:read_u8(0x9DD0+b)
      if mem:read_u8(p+21)~=pw or mem:read_u8(p+23)~=x then bad=bad+1 end
    end
    local n=mem:read_u8(0xDD)
    if n>0 and mem:read_u8(0x1A7F+n-1)==4 then
      -- is the last entry player 2's car? compare with the staged OC values
      if mem:read_u8(0x1A94+n-1)==mem:read_u8(0x2719) and mem:read_u8(0x1AE8+n-1)==mem:read_u8(0x271E) then listed=listed+1 end
    end
    -- per band class-4 count
    local per={}
    for k=0,n-1 do
      if mem:read_u8(0x1A7F+k)==4 then
        local t=mem:read_u8(0xBB7E+mem:read_u8(0x1A94+k)); local u=mem:read_u8(0xBB7E+mem:read_u8(0x1AA9+k))
        for b=u,t do per[b]=(per[b] or 0)+1; if per[b]>worstband then worstband=per[b] end end
      end
    end
  end
  return d end)
emu.register_frame_done(function()
  f=f+1
  local st=mem:read_u8(0x9D)
  if st==0x0E or st==0x07 or st==0x05 then mem:write_u8(0xA6,tonumber(os.getenv("POS"))) end
  if (st==0x11 or st==3) and not start then start=f end
  if start and os.getenv("HOLD") then
    local g=-(60 + ((f-start)*3) % 700)                  -- 60..760 ahead
    g=g & 0xFFFF
    mem:write_u8(0x275C,g & 0xFF); mem:write_u8(0x275D,g >> 8)
    local lane=({0x20,0xE0,0x00,0x30})[(math.floor((f-start)/47)%4)+1]
    mem:write_u8(0x2702,lane)
  end
  if start and shots[f-start] then M.video:snapshot() end
  if f>=tonumber(os.getenv("FR")) then
    o:write(string.format("POS %s: emitter passes %d, most cars in one band (incl. player 2's) %d, player 2's car listed on %d, rival slices capped %d, player 1's car slot overwritten %d times",
      os.getenv("POS"),passes,worstband,listed,drops,bad)..string.char(10))
    o:close(); M:exit()
  end
end)
