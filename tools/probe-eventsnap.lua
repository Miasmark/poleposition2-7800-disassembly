-- Snapshot each event found by probe-events2, plus a look-ahead frame ~0.5s
-- earlier so the object is still up the road and identifiable.
local M=(type(manager.machine)=="function") and manager:machine() or manager.machine
local want={}
local ev={3132,6537,7263,7479,8379,9105,9747,10137,10965,11007}
for _,f in ipairs(ev) do want[f-30]=string.format("%06d_pre",f); want[f]=string.format("%06d_hit",f) end
local F,n=0,0
emu.register_frame_done(function()
  F=F+1
  local tag=want[F]
  if tag then
    n=n+1
    print(string.format("snap %02d -> frame %d %s", n, F, tag))
    M.video:snapshot()
  end
  if F>=11060 then M:exit() end
end)
