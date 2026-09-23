-- pcprof.lua -- a sampling CPU profiler that needs no timer.
-- MARIA reads the DLL at every zone boundary, at an even beam position; a read
-- tap there fires with the 6502 halted mid-program, so its PC is a fair sample
-- of where the CPU is spending the visible frame. Vblank is not sampled.
-- Env: PROF_DLL (hex), PROF_LEN, PROF_OUT, PROF_FROM, PROF_TO
local M=(type(manager.machine)=="function") and manager:machine() or manager.machine
local cpu=M.devices[":maincpu"]
local mem=cpu.spaces["program"]
local dll=tonumber(os.getenv("PROF_DLL"),16)
local len=tonumber(os.getenv("PROF_LEN") or "120")
local out=os.getenv("PROF_OUT") or "pcprof"
local a=tonumber(os.getenv("PROF_FROM") or "1400")
local b=tonumber(os.getenv("PROF_TO") or "3600")
local f, n = 0, 0
local hist = {}
TAPS={}
TAPS[1]=mem:install_read_tap(dll,dll+len-1,"dll",function(o,d)
  if f>=a and f<=b then
    local pc=cpu.state["PC"].value
    hist[pc]=(hist[pc] or 0)+1; n=n+1
  end
  return d
end)
emu.register_frame_done(function()
  f=f+1
  if f>b then
    local o=io.open(out..".csv","w")
    for pc,c in pairs(hist) do o:write(pc..","..c..string.char(10)) end
    o:close(); M:exit()
  end
end)
