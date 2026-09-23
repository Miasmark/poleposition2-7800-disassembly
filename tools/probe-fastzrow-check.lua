-- probe-fastzrow-check.lua -- every FastZRow result against the original linear
-- search, computed here from the ROM's distance table (read on first use: the
-- cart is not mapped yet when the script loads). env: RTS (hex, FastZRow's RTS),
-- FR (frames), O (output).
local M=(type(manager.machine)=="function") and manager:machine() or manager.machine
local cpu=M.devices[":maincpu"]
local mem=cpu.spaces["program"]
local RTS=tonumber(os.getenv("RTS"),16)
local T={}
local n,bad,f=0,0,0
TAPS={}
TAPS[1]=mem:install_read_tap(RTS,RTS,"r",function(a,v)
  if cpu.state["PC"].value==RTS then
    if T[0]==nil then for x=0,77 do T[x]=mem:read_u8(0xEB56+x)+256*mem:read_u8(0xEAB9+x) end; EX=string.format(" T0=%d T77=%d;",T[0],T[77]) end
    local z=mem:read_u8(0x48)+256*mem:read_u8(0x49)
    local want=0xFF
    for x=0x4D,0,-1 do if ((z-T[x]) & 0x8000)~=0 then want=x; break end end
    n=n+1; if cpu.state["X"].value~=want then bad=bad+1; if bad<=8 then EX=(EX or "")..string.format(" z=%d got=%d want=%d lo=%d hi=%d;",z,cpu.state["X"].value,want,mem:read_u8(0x278E),mem:read_u8(0x278F)) end end
  end
  return v end)
emu.register_frame_done(function() f=f+1; if f>=tonumber(os.getenv("FR")) then
  local o=io.open(os.getenv("O"),"w"); o:write(string.format("row searches %d, differing %d:%s",n,bad,EX or "")..string.char(10)); o:close(); M:exit() end end)
