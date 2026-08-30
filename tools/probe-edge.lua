-- Track-limit behaviour, per sub_C4F7: PlayerX under 60 is on the road,
-- 60..103 is the verge, 104 is the hard clamp where $D0 (lateral velocity)
-- is zeroed.  Report every excursion and what speed did during it.
local M=(type(manager.machine)=="function") and manager:machine() or manager.machine
local mem=M.devices[":maincpu"].spaces["program"]
local function sx(v) return v>127 and v-256 or v end
local F,run=0,nil
emu.register_frame_done(function()
  F=F+1
  local x,s,d0=sx(mem:read_u8(0xD1)),mem:read_u8(0xCE),mem:read_u8(0xD0)
  local a=math.abs(x)
  if a>=60 then
    if not run then run={f=F,s0=s,mx=a,mns=s,clamp=0} end
    run.mx=math.max(run.mx,a); run.mns=math.min(run.mns,s)
    if a>=104 then run.clamp=run.clamp+1 end
    run.last,run.side=F,(x<0 and "L" or "R")
  elseif run then
    if run.last-run.f>=5 then
      print(string.format("f%-6d..%-6d %3d fr  %s  maxX %3d  clamped %3d fr  speed %3d -> %3d (min %3d)",
        run.f,run.last,run.last-run.f+1,run.side,run.mx,run.clamp,run.s0,s,run.mns))
    end
    run=nil
  end
  if F>=11941 then M:exit() end
end)
