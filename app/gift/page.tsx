"use client";

import { useEffect, useRef, useState } from "react";

const GREETING_TEXT = "祝小郭每天都开心";

export default function GiftPage() {
  const [opened, setOpened] = useState(false);
  const [showMsg, setShowMsg] = useState(false);
  const floatersRef = useRef<HTMLDivElement>(null);
  const burstRef = useRef<HTMLDivElement>(null);
  const greetingRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = floatersRef.current;
    if (!container) return;
    const timers: number[] = [];
    const spawn = () => {
      const el = document.createElement("div");
      el.className = "floater";
      el.textContent = Math.random() > 0.5 ? "❤" : "✦";
      el.style.left = Math.random() * 100 + "vw";
      el.style.fontSize = 14 + Math.random() * 22 + "px";
      el.style.animationDuration = 7 + Math.random() * 8 + "s";
      el.style.animationDelay = Math.random() * 4 + "s";
      if (Math.random() > 0.5) el.style.color = "rgba(255,160,190,0.5)";
      container.appendChild(el);
      timers.push(window.setTimeout(() => el.remove(), 16000));
    };
    for (let i = 0; i < 8; i++) spawn();
    const interval = window.setInterval(spawn, 650);
    return () => {
      window.clearInterval(interval);
      timers.forEach((t) => window.clearTimeout(t));
    };
  }, []);

  const burstHearts = () => {
    const burst = burstRef.current;
    if (!burst) return;
    const symbols = ["❤", "💕", "✦", "✿", "❀", "♥"];
    const colors = ["#ff5c8a", "#ff9bb3", "#ffd6a0", "#ff4d7d", "#ffb3cd"];
    const N = 46;
    for (let i = 0; i < N; i++) {
      const p = document.createElement("span");
      p.className = "particle";
      p.textContent = symbols[Math.floor(Math.random() * symbols.length)];
      p.style.color = colors[Math.floor(Math.random() * colors.length)];
      p.style.fontSize = 16 + Math.random() * 26 + "px";
      burst.appendChild(p);
      const angle = (Math.PI * 2 * i) / N + Math.random() * 0.4;
      const dist = 160 + Math.random() * 320;
      const dx = Math.cos(angle) * dist;
      const dy = Math.sin(angle) * dist - 60;
      const rot = (Math.random() - 0.5) * 360;
      const dur = 1100 + Math.random() * 900;
      p.animate(
        [
          { transform: "translate(-50%,-50%) translate(0,0) rotate(0deg) scale(0.3)", opacity: 1 },
          { transform: `translate(-50%,-50%) translate(${dx}px, ${dy}px) rotate(${rot}deg) scale(1)`, opacity: 1, offset: 0.7 },
          { transform: `translate(-50%,-50%) translate(${dx * 1.1}px, ${dy * 1.1 + 40}px) rotate(${rot}deg) scale(0.6)`, opacity: 0 },
        ],
        { duration: dur, easing: "cubic-bezier(.15,.7,.3,1)", fill: "forwards" }
      );
      window.setTimeout(() => p.remove(), dur + 50);
    }
  };

  const revealGreeting = () => {
    const g = greetingRef.current;
    if (!g) return;
    g.innerHTML = "";
    Array.from(GREETING_TEXT).forEach((c, i) => {
      const s = document.createElement("span");
      s.className = "ch";
      s.textContent = c;
      s.style.animationDelay = 0.5 + i * 0.13 + "s";
      g.appendChild(s);
    });
  };

  const open = () => {
    if (opened) return;
    setOpened(true);
    burstHearts();
    window.setTimeout(() => {
      setShowMsg(true);
      revealGreeting();
    }, 480);
  };

  const reset = () => {
    setOpened(false);
    setShowMsg(false);
  };

  return (
    <main className={"gift-body" + (opened ? " opened" : "")}>
      <link rel="preconnect" href="https://fonts.googleapis.com" />
      <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      <link
        href="https://fonts.googleapis.com/css2?family=Ma+Shan+Zheng&family=Noto+Serif+SC:wght@400;600;700&display=swap"
        rel="stylesheet"
      />
      <style>{CSS}</style>
      <div className="floaters" ref={floatersRef} />
      <div className="stage">
        {!opened && (
          <>
            <div className="heart-wrap" onClick={open} role="button" aria-label="点击打开">
              <svg className="heart-svg" viewBox="0 0 32 29.6" xmlns="http://www.w3.org/2000/svg">
                <defs>
                  <linearGradient id="hg" x1="0" y1="0" x2="1" y2="1">
                    <stop offset="0%" stopColor="#ff9bb3" />
                    <stop offset="55%" stopColor="#ff5c8a" />
                    <stop offset="100%" stopColor="#ff2d6f" />
                  </linearGradient>
                </defs>
                <path
                  d="M23.6,0c-3.4,0-6.3,2.7-7.6,5.6C14.7,2.7,11.8,0,8.4,0C3.8,0,0,3.8,0,8.4c0,9.4,9.5,11.9,16,21.2 c6.1-9.3,16-12.1,16-21.2C32,3.8,28.2,0,23.6,0z"
                  fill="url(#hg)"
                />
              </svg>
            </div>
            <div className="hint">
              点击打开我的心意
              <small>—— for 小郭</small>
            </div>
          </>
        )}
        {showMsg && (
          <div className="message show">
            <div className="greeting" ref={greetingRef} />
            <div className="sub">
              <span className="line">愿你眼里有光，心中有暖</span>
              <br />
              <span className="line">每一天都被温柔以待 ❤</span>
            </div>
            <div className="replay" onClick={reset}>
              再打开一次
            </div>
          </div>
        )}
      </div>
      <div className="burst" ref={burstRef} />
    </main>
  );
}

const CSS = `
:root { --ink: #7a2b46; }
* { margin: 0; padding: 0; box-sizing: border-box; }

.gift-body {
  position: relative;
  min-height: 100vh;
  width: 100%;
  overflow: hidden;
  font-family: "Noto Serif SC", "Songti SC", serif;
  background: radial-gradient(circle at 20% 20%, #ffe3ec 0%, #ffd0e0 35%, #ffc2d6 70%, #ffb3cd 100%);
  color: var(--ink);
  -webkit-tap-highlight-color: transparent;
  user-select: none;
  transition: background 1.4s ease;
}
.gift-body.opened {
  background:
    radial-gradient(circle at 18% 25%, #fff0f5 0%, transparent 45%),
    radial-gradient(circle at 82% 30%, #ffe0ec 0%, transparent 50%),
    radial-gradient(circle at 50% 85%, #ffd6e6 0%, transparent 55%),
    linear-gradient(160deg, #fff5f8 0%, #ffe6f0 50%, #ffd9ea 100%);
}

.floaters { position: fixed; inset: 0; pointer-events: none; z-index: 1; overflow: hidden; }
.floater {
  position: absolute;
  bottom: -60px;
  font-size: 20px;
  opacity: 0;
  animation: rise linear infinite;
  color: rgba(255, 107, 138, 0.55);
}
@keyframes rise {
  0%   { transform: translateY(0) rotate(0deg) scale(0.6); opacity: 0; }
  15%  { opacity: 0.7; }
  85%  { opacity: 0.6; }
  100% { transform: translateY(-110vh) rotate(220deg) scale(1); opacity: 0; }
}

.stage {
  position: relative;
  z-index: 5;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.heart-wrap {
  cursor: pointer;
  transition: transform 0.5s ease, opacity 0.6s ease;
  animation: floaty 3.2s ease-in-out infinite;
}
@keyframes floaty {
  0%, 100% { transform: translateY(0); }
  50%      { transform: translateY(-14px); }
}

.heart-svg {
  width: 200px;
  height: 200px;
  filter: drop-shadow(0 0 22px rgba(255, 77, 125, 0.55));
  animation: beat 1.15s ease-in-out infinite;
}
@keyframes beat {
  0%, 100% { transform: scale(1); }
  15%      { transform: scale(1.12); }
  30%      { transform: scale(1); }
  45%      { transform: scale(1.08); }
  60%      { transform: scale(1); }
}
.heart-wrap:hover .heart-svg { filter: drop-shadow(0 0 34px rgba(255, 77, 125, 0.8)); }

.hint {
  margin-top: 28px;
  font-size: 17px;
  letter-spacing: 4px;
  color: var(--ink);
  opacity: 0.85;
  animation: breathe 2.4s ease-in-out infinite;
}
.hint small { display: block; margin-top: 8px; font-size: 13px; letter-spacing: 2px; opacity: 0.7; }
@keyframes breathe { 0%, 100% { opacity: 0.45; } 50% { opacity: 0.95; } }

.burst { position: fixed; inset: 0; pointer-events: none; z-index: 8; }
.particle { position: absolute; left: 50%; top: 50%; font-size: 22px; will-change: transform, opacity; }

.message {
  position: relative;
  z-index: 6;
  opacity: 0;
  transform: translateY(20px) scale(0.96);
  transition: opacity 0.9s ease 0.2s, transform 0.9s cubic-bezier(.2,.8,.3,1) 0.2s;
  max-width: 90vw;
}
.message.show { opacity: 1; transform: translateY(0) scale(1); }

.greeting {
  font-family: "Ma Shan Zheng", "Noto Serif SC", serif;
  font-size: clamp(38px, 9vw, 76px);
  line-height: 1.25;
  color: var(--ink);
  text-shadow: 0 3px 18px rgba(255, 120, 160, 0.35);
}
.greeting .ch {
  display: inline-block;
  opacity: 0;
  transform: translateY(16px) rotate(-6deg);
  animation: pop 0.6s forwards;
}
@keyframes pop { to { opacity: 1; transform: translateY(0) rotate(0); } }

.sub { margin-top: 22px; font-size: clamp(14px, 3.6vw, 19px); letter-spacing: 3px; color: rgba(122, 43, 70, 0.75); }
.sub .line { display: inline-block; }

.replay {
  margin-top: 40px;
  display: inline-block;
  border: 1.5px solid rgba(255, 107, 138, 0.6);
  background: rgba(255, 255, 255, 0.35);
  color: var(--ink);
  padding: 10px 26px;
  border-radius: 999px;
  font-size: 14px;
  letter-spacing: 2px;
  cursor: pointer;
  backdrop-filter: blur(4px);
  transition: all 0.25s ease;
  opacity: 0;
  pointer-events: none;
}
.replay.show { opacity: 1; pointer-events: auto; animation: fadeIn 1s ease 1.6s both; }
.replay:hover { background: rgba(255, 107, 138, 0.15); transform: translateY(-2px); }
@keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
`;
