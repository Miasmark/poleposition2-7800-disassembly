-- per-band slope of RowCurveOffset ($1A31, 78 rows), sampled every 6 frames
-- in the race: slope = x[6b+5]-x[6b] over 5 rows; also the step between the
-- band's sample row and the next band's (what the stair shows)
local M=(type(manager.machine)=="function") and manager:machine() or manager.machine
local mem=M.devices[":maincpu"].spaces["program"]
local f=0; local o=io.open(os.getenv("O"),"w")
local function s8(v) if v>=128 then return v-256 end return v end
emu.register_frame_done(function() f=f+1
  local st=mem:read_u8(0x9D)
  if (st==0x03 or st==0x02) and f%6==0 then
    local t={}
    for b=0,12 do
      local x0=mem:read_u8(0x1A31+6*b); local x5=mem:read_u8(0x1A31+6*b+5)
      t[#t+1]=tostring(s8((x5-x0)&0xFF))
    end
    o:write(table.concat(t," ").."\n")
  end
  if f>=tonumber(os.getenv("END")) then o:close() M:exit() end end)
