-- probe-far-slots.lua -- which object slots player 1's far bands (1-7) use:
-- per band, frames each of the 8 slots is in use (x not $A1), and how many
-- are in use at once, over states $02/$03. Env: O, END. Run with -playback.
local M=(type(manager.machine)=="function") and manager:machine() or manager.machine
local mem=M.devices[":maincpu"].spaces["program"]
local B={0x2326,0x234C,0x2372,0x2398,0x23BE,0x2400,0x2426}
local h={} for b=1,7 do h[b]={} for s=0,7 do h[b][s]=0 end end
local cnt={} for b=1,7 do cnt[b]={} end
local f=0
emu.register_frame_done(function() f=f+1
  local st=mem:read_u8(0x9D)
  if st==0x02 or st==0x03 then
    for b=1,7 do local n=0 for s=0,7 do local a=B[b]+4+4*s
      if mem:read_u8(a+3)~=0xA1 and (mem:read_u8(a+1)&0x1F)~=0x1F then h[b][s]=h[b][s]+1; n=n+1 end end
      cnt[b][n]=(cnt[b][n] or 0)+1 end end
  if f>=tonumber(os.getenv("END")) then local o=io.open(os.getenv("O"),"w")
    for b=1,7 do local t={} for s=0,7 do t[#t+1]=h[b][s] end local c={} for n=0,8 do c[#c+1]=(cnt[b][n] or 0) end
      o:write(string.format("band %d slots %s   count %s\n",b,table.concat(t," "),table.concat(c," "))) end o:close() M:exit() end end)
