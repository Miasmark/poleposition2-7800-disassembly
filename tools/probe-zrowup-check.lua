-- probe-zrowup-check.lua -- ZRowUp vs rom:CE3E: at each ZRowUp return (env RTS,
-- hex addresses of its two RTSes), recompute the stock linear search and compare Y.
-- at each ZRowUp return: recompute rom:CE3E's linear search, compare Y
local M=(type(manager.machine)=="function") and manager:machine() or manager.machine
local cpu=M.devices[":maincpu"]; local mem=cpu.spaces["program"]
local T=nil; local n,bad=0,0; local f=0; local o=io.open(os.getenv("O"),"w")
local function tab() T={} for y=0,77 do T[y]=mem:read_u8(0xEB56+y)+256*mem:read_u8(0xEAB9+y) end end
local function check()
  if not T then tab() end
  local z=mem:read_u8(0x47)+256*mem:read_u8(0x48)
  local want=0x4E
  for y=0,0x4D do if ((z-T[y])&0x8000)==0 then want=y break end end
  local got=cpu.state["Y"].value; n=n+1
  if got~=want then bad=bad+1 if bad<10 then o:write(string.format("f%d z=%04X got %02X want %02X\n",f,z,got,want)) end end
end
ZT={}
for a in string.gmatch(os.getenv("RTS"),"%x+") do local ad=tonumber(a,16)
  ZT[#ZT+1]=mem:install_read_tap(ad,ad,"zu"..a,function(o2,d) if cpu.state["PC"].value==ad then check() end return d end) end
emu.register_frame_done(function() f=f+1 if f>=tonumber(os.getenv("END")) then o:write(string.format("searches %d, differences %d\n",n,bad)) o:close() M:exit() end end)
