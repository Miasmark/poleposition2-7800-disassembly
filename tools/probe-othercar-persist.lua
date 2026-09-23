-- ocpersist.lua -- once a pass says it drew player 2's car into a slot of
-- player 1's view (P1_OC_LAST), that slot must still hold it at every frame end.
local M=(type(manager.machine)=="function") and manager:machine() or manager.machine
local mem=M.devices[":maincpu"].spaces["program"]
local P1SLOT={0x2304,0x232A,0x2350,0x2376,0x239C,0x23C2,0x2404,0x242A,0x2454,0x2476,0x2498,0x24BA,0x24DC}
local f,drawn,wiped,racing=0,0,0,0
local o=io.open(os.getenv("O"),"w")
emu.register_frame_done(function()
  f=f+1
  local st=mem:read_u8(0x9D)
  if st==2 or st==3 then
    racing=racing+1
    local last=mem:read_u8(0x2741)
    if last<13 then
      drawn=drawn+1
      if mem:read_u8(P1SLOT[last+1]+3)==0xA1 then
        wiped=wiped+1
        if wiped<=5 then o:write(string.format("f%d slot for band %d reads parked",f,last)..string.char(10)) end
      end
    end
  end
  if f>=6000 then
    o:write(string.format("racing frames %d, car claimed drawn %d, found wiped %d",racing,drawn,wiped)..string.char(10))
    o:close(); M:exit()
  end
end)
