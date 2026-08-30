-- $D2 is the skid flag ($FF while sliding), set at rom:C297 with sound 3 and
-- cleared at rom:C2AA.  While set, rom:C2A4 calls sub_C3B2: speed -= (speed>>5)&3.
local M=(type(manager.machine)=="function") and manager:machine() or manager.machine
local mem=M.devices[":maincpu"].spaces["program"]
local function sx(v) return v>127 and v-256 or v end
local F,run,tot,tv=0,nil,0,0
emu.register_frame_done(function()
  F=F+1
  local sk,s=mem:read_u8(0xD2),mem:read_u8(0xCE)
  local a=math.abs(sx(mem:read_u8(0xD1)))
  if sk~=0 and F>3200 then
    if not run then run={f=F,s0=s,v=0,n=0} end
    run.n=run.n+1; if a>=60 then run.v=run.v+1 end
    run.last,run.s1=F,s
    tot=tot+1; if a>=60 then tv=tv+1 end
  elseif run then
    if run.n>=8 then
      print(string.format("f%-6d..%-6d %4d fr  verge %3d fr (%3.0f%%)  speed %3d -> %3d  (%+d)",
        run.f,run.last,run.n,run.v,100*run.v/run.n,run.s0,run.s1,run.s1-run.s0))
    end
    run=nil
  end
  if F>=11941 then
    print(string.format("\ntotal skidding: %d frames, %d of them on the verge (%.0f%%)",tot,tv,100*tv/math.max(tot,1)))
    M:exit()
  end
end)
