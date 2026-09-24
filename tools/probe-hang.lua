-- probe-hang.lua -- snapshots of where a stuck machine is: at each frame in AT
-- (space-separated), PC, SP, 10 stack bytes, game state, DLI index, $E5, $B8 and
-- the NMI count so far. Env: O, AT, FR. For "the clock froze"; a jump into
-- data is tools/probe-wild-fetch.lua.
local M=(type(manager.machine)=="function") and manager:machine() or manager.machine
local cpu=M.devices[":maincpu"]; local mem=cpu.spaces["program"]
local f=0; local o=io.open(os.getenv("O"),"w"); local nmi=0
T1=mem:install_read_tap(0xEBF6,0xEBF6,"n",function(a,d) nmi=nmi+1 return d end)
local AT={} for w in string.gmatch(os.getenv("AT"),"%d+") do AT[tonumber(w)]=true end
emu.register_frame_done(function() f=f+1
  if AT[f] then local sp=cpu.state["SP"].value; local st={} for i=1,10 do st[#st+1]=string.format("%02X",mem:read_u8(0x100+((sp+i)&0xFF))) end
    o:write(string.format("f%d pc=%04X sp=%02X st=%02X FF=%d E5=%02X 9C=%02X B8=%d busy=%d nmis=%d stk=%s\n",f,cpu.state["PC"].value,sp,mem:read_u8(0x9D),mem:read_u8(0xFF),mem:read_u8(0xE5),mem:read_u8(0x9C),mem:read_u8(0xB8),mem:read_u8(0x2737),nmi,table.concat(st," "))) nmi=0 end
  if f>=tonumber(os.getenv("FR")) then o:close(); M:exit() end end)
