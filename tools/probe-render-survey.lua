-- survey.lua -- how does a 7800 racing game spend MARIA and the CPU?
--
-- Game-agnostic on purpose, so Pole Position II, Motor Psycho and Fatal Run
-- are measured by the same instrument. Per frame it counts:
--   DLIs    reads of the NMI vector at $FFFA (the CPU fetches it on every NMI)
--   WSYNC   writes to $24 (beam-racing kernels show up as hundreds a frame)
--   DPPH/L  and CTRL as last written (MARIA's registers are write-only)
-- and at the frames in SURVEY_DUMP it saves RAM $1800-$27FF plus a screenshot,
-- so the display lists can be walked offline.
--
-- Env: SURVEY_OUT (prefix), SURVEY_DUMP (comma frames), SURVEY_SHOTS (every N)
--      SURVEY_FRAMES (stop after)
local M=(type(manager.machine)=="function") and manager:machine() or manager.machine
local mem=M.devices[":maincpu"].spaces["program"]
local out=os.getenv("SURVEY_OUT") or "survey"
local every=tonumber(os.getenv("SURVEY_SHOTS") or "0")
local stop=tonumber(os.getenv("SURVEY_FRAMES") or "3600")
local dumps={}
for n in string.gmatch(os.getenv("SURVEY_DUMP") or "", "%d+") do dumps[tonumber(n)]=true end

local f, dli, wsync = 0, 0, 0
local dpph, dppl, ctrl = -1, -1, -1
TAPS={}
TAPS[1]=mem:install_read_tap(0xFFFA,0xFFFA,"nmi",function(o,d) dli=dli+1; return d end)
TAPS[2]=mem:install_write_tap(0x24,0x24,"wsync",function(o,d) wsync=wsync+1; return d end)
TAPS[3]=mem:install_write_tap(0x2C,0x2C,"dpph",function(o,d) dpph=d; return d end)
TAPS[4]=mem:install_write_tap(0x30,0x30,"dppl",function(o,d) dppl=d; return d end)
TAPS[5]=mem:install_write_tap(0x3C,0x3C,"ctrl",function(o,d) ctrl=d; return d end)

local log=io.open(out.."-frames.csv","w")
log:write("frame,dli,wsync,dpph,dppl,ctrl\n")

emu.register_frame_done(function()
  f=f+1
  log:write(string.format("%d,%d,%d,%d,%d,%d\n",f,dli,wsync,dpph,dppl,ctrl))
  dli, wsync = 0, 0
  if every>0 and f%every==0 then M.video:snapshot() end
  if dumps[f] then
    local b=io.open(string.format("%s-ram-%05d.bin",out,f),"wb")
    local t={}
    for a=0x1800,0x27FF do t[#t+1]=string.char(mem:read_u8(a)) end
    b:write(table.concat(t)); b:close()
    local m=io.open(string.format("%s-ram-%05d.txt",out,f),"w")
    m:write(string.format("dpph=%02X dppl=%02X ctrl=%02X\n",dpph,dppl,ctrl)); m:close()
    M.video:snapshot()
  end
  if f>=stop then log:close(); M:exit() end
end)
