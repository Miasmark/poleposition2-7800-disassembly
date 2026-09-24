-- probe-ram-coverage.lua -- per-address RAM read/write counts after frame 600 (env FR, COV_OUT); run with -playback
local M=(type(manager.machine)=="function") and manager:machine() or manager.machine
local cpu=M.devices[":maincpu"]; local mem=cpu.spaces["program"]; local f=0; TAPS={}
-- RAM coverage: per-address read and write counts after frame 600
local RC,WC={},{}
local function norm(a) if a<0x100 then return a+0x2000 elseif a<0x200 then return a+0x2000 end return a end
local function rtap(a,d) if f>600 then local k=norm(a); RC[k]=(RC[k] or 0)+1 end return d end
local function wtap(a,d) if f>600 then local k=norm(a); WC[k]=(WC[k] or 0)+1 end end
TAPS[90]=mem:install_read_tap(0x1800,0x27FF,"rcA",rtap)
TAPS[91]=mem:install_write_tap(0x1800,0x27FF,"wcA",wtap)
TAPS[92]=mem:install_read_tap(0x0040,0x00FF,"rcZ",rtap)
TAPS[93]=mem:install_write_tap(0x0040,0x00FF,"wcZ",wtap)
TAPS[94]=mem:install_read_tap(0x0140,0x01FF,"rcS",rtap)
TAPS[95]=mem:install_write_tap(0x0140,0x01FF,"wcS",wtap)
emu.register_frame_done(function() if f==tonumber(os.getenv("FR"))-1 then local o5=io.open(os.getenv("COV_OUT"),"w")
  for a=0x1800,0x27FF do o5:write(string.format("%04X,%d,%d",a,RC[a] or 0,WC[a] or 0)..string.char(10)) end o5:close() end end)
emu.register_frame_done(function() f=f+1; if f>=tonumber(os.getenv("FR")) then M:exit() end end)
