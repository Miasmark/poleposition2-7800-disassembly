-- cover.lua -- per-byte ROM coverage, tagged by game state ($9D).
-- A read tap over the whole cart sees CPU fetches, data reads and MARIA's DMA
-- alike. Nothing counts until the cart's own reset code runs, so the BIOS's
-- boot-time signature scan (which reads every byte) is excluded.
-- Env: C_OUT (file), C_FRAMES, C_RESET (hex entry point)
local M=(type(manager.machine)=="function") and manager:machine() or manager.machine
local cpu=M.devices[":maincpu"]
local mem=cpu.spaces["program"]
local reset=tonumber(os.getenv("C_RESET"),16)
local stop=tonumber(os.getenv("C_FRAMES") or "8000")
ARMED=false
STATE=0
HIT={}
for s=0,255 do HIT[s]={} end
TAPS={}
TAPS[1]=mem:install_read_tap(reset,reset,"arm",function(o,d)
  if not ARMED and cpu.state["PC"].value==reset then ARMED=true end
  return d end)
TAPS[2]=mem:install_read_tap(0x8000,0xFFFF,"cov",function(o,d)
  if ARMED then HIT[mem:read_u8(0x9D)][o]=true end
  return d end)
local f=0
-- Pick a different track for each demo: while the title shows (state 00),
-- hold TrackIndex ($C4) at the next track in turn. The demo runs on the
-- selected track, so this walks it through all four.
local cycle, prev, log = 0, -1, {}
emu.register_frame_done(function()
  f=f+1
  STATE=mem:read_u8(0x9D)
  if STATE==0 and prev~=0 then cycle=cycle+1 end
  if STATE==0 then mem:write_u8(0xC4,cycle%4) end
  if STATE==1 and prev~=1 then log[#log+1]=string.format("f%d demo on TrackIndex %d",f,mem:read_u8(0xC4)) end
  prev=STATE
  if f>=stop then
    local o=io.open(os.getenv("C_OUT"),"w")
    for s=0,255 do
      local t=HIT[s]
      local ks={}
      for a,_ in pairs(t) do ks[#ks+1]=a end
      if #ks>0 then
        table.sort(ks)
        -- write as ranges: state lo hi
        local lo,hi=ks[1],ks[1]
        for i=2,#ks do
          if ks[i]==hi+1 then hi=ks[i]
          else o:write(s.." "..lo.." "..hi..string.char(10)); lo,hi=ks[i],ks[i] end
        end
        o:write(s.." "..lo.." "..hi..string.char(10))
      end
    end
    for _,l in ipairs(log) do o:write("# "..l..string.char(10)) end
    o:close(); M:exit()
  end
end)
