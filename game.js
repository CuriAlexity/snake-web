(() => {
  'use strict';

  const canvas = document.getElementById('game');
  const ctx = canvas.getContext('2d');

  // Grid and visuals
  const CELL = 20;
  const GRID_W = 30;
  const GRID_H = 20;
  const HUD_H = 72; // px reserved on top (more space for pixel font)
  canvas.width = GRID_W * CELL;
  canvas.height = HUD_H + GRID_H * CELL;
  // Responsive scale to fit viewport while keeping aspect
  function fitCanvas() {
    const scale = Math.min(window.innerWidth / canvas.width * 0.96, window.innerHeight / canvas.height * 0.96);
    canvas.style.width = Math.floor(canvas.width * scale) + 'px';
    canvas.style.height = Math.floor(canvas.height * scale) + 'px';
  }
  window.addEventListener('resize', fitCanvas);
  fitCanvas();

  const COLOR_TEXT = '#e6e6e6';
  const COLOR_SNAKE = '#00c878';
  const COLOR_FOOD = '#dc505a';
  const COLOR_OBST = '#8ca0dc';
  const BORDER_COLOR = '#c83c3c';
  const BORDER_THICK = 3;
  const APPLE_MARGIN = 1;

  // Speed
  const BASE_FPS = 12;
  const MIN_FPS = 2;
  const MAX_FPS = 24;
  const START_FPS = Math.max(MIN_FPS, Math.floor(BASE_FPS / 5));

  // Game state
  let snake, dir, food, score, obstacles, pendingDir;
  let paused = false, gameOver = false, win = false, onMenu = true;
  let fps = START_FPS;
  let deathReason = '';

  const UP = [0, -1];
  const DOWN = [0, 1];
  const LEFT = [-1, 0];
  const RIGHT = [1, 0];

  function resetGame() {
    const start = [Math.floor(GRID_W / 2), Math.floor(GRID_H / 2)];
    snake = [start, [start[0] - 1, start[1]], [start[0] - 2, start[1]]];
    dir = RIGHT.slice();
    food = randomEmptyCell(new Set(cellsToKey(snake)));
    score = 0;
    pendingDir = dir.slice();
    obstacles = new Set();
  }

  function cellsToKey(cells) {
    return cells.map(([x, y]) => `${x},${y}`);
  }

  function randomEmptyCell(excludeSet) {
    const minX = APPLE_MARGIN;
    const maxX = GRID_W - 1 - APPLE_MARGIN;
    const minY = APPLE_MARGIN;
    const maxY = GRID_H - 1 - APPLE_MARGIN;
    const candidates = [];
    for (let y = minY; y <= maxY; y++) {
      for (let x = minX; x <= maxX; x++) {
        const key = `${x},${y}`;
        if (!excludeSet.has(key)) candidates.push([x, y]);
      }
    }
    if (!candidates.length) return null;
    return candidates[Math.floor(Math.random() * candidates.length)];
  }

  function spawnObstacles(n, excludeSet) {
    const minX = APPLE_MARGIN, maxX = GRID_W - 1 - APPLE_MARGIN;
    const minY = APPLE_MARGIN, maxY = GRID_H - 1 - APPLE_MARGIN;
    const all = [];
    for (let y = minY; y <= maxY; y++) {
      for (let x = minX; x <= maxX; x++) {
        const key = `${x},${y}`;
        if (!excludeSet.has(key)) all.push([x, y]);
      }
    }
    const k = Math.min(n, all.length);
    const chosen = new Set();
    while (chosen.size < k) {
      const c = all[Math.floor(Math.random() * all.length)];
      chosen.add(`${c[0]},${c[1]}`);
    }
    return chosen;
  }

  // Draw helpers
  function rectForCell([x, y]) {
    const inset = 3;
    return [x * CELL + inset, HUD_H + y * CELL + inset, CELL - inset * 2, CELL - inset * 2];
  }

  function drawGradient() {
    const g = ctx.createLinearGradient(0, 0, 0, canvas.height);
    g.addColorStop(0, '#22263a');
    g.addColorStop(1, '#0c0e14');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
  }

  function drawGlass(x, y, w, h) {
    ctx.save();
    ctx.fillStyle = 'rgba(255,255,255,0.19)';
    roundRect(ctx, x, y, w, h, 12);
    ctx.fill();
    ctx.strokeStyle = 'rgba(255,255,255,0.38)';
    roundRect(ctx, x, y, w, h, 12);
    ctx.stroke();
    const grad = ctx.createLinearGradient(0, y, 0, y + h / 2);
    grad.addColorStop(0, 'rgba(255,255,255,0.28)');
    grad.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = grad;
    ctx.fillRect(x, y, w, h / 2);
    ctx.restore();
  }

  function roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }

  function drawSnakeCell(c) {
    ctx.save();
    const [x, y, w, h] = rectForCell(c);
    ctx.fillStyle = 'rgba(0,0,0,0.35)';
    roundRect(ctx, x, y + 2, w, h, Math.floor(w / 3));
    ctx.fill();
    ctx.fillStyle = COLOR_SNAKE;
    roundRect(ctx, x, y, w, h, Math.floor(w / 3));
    ctx.fill();
    ctx.restore();
  }

  function drawFood(c) {
    const [x, y, w, h] = rectForCell(c);
    ctx.save();
    ctx.fillStyle = 'rgba(0,0,0,0.43)';
    ctx.beginPath(); ctx.ellipse(x + w/2, y + h/2 + 2, w/2, h/2, 0, 0, Math.PI*2); ctx.fill();
    ctx.fillStyle = COLOR_FOOD;
    ctx.beginPath(); ctx.ellipse(x + w/2, y + h/2, w/2, h/2, 0, 0, Math.PI*2); ctx.fill();
    ctx.fillStyle = 'rgba(255,255,255,0.35)';
    ctx.beginPath(); ctx.ellipse(x + w*0.45, y + h*0.35, w*0.23, h*0.18, 0, 0, Math.PI*2); ctx.fill();
    ctx.restore();
  }

  function drawObstacle(c) {
    const [x, y, w, h] = rectForCell(c);
    ctx.save();
    ctx.fillStyle = 'rgba(0,0,0,0.32)';
    roundRect(ctx, x, y + 2, w, h, Math.floor(w / 4));
    ctx.fill();
    ctx.fillStyle = COLOR_OBST;
    roundRect(ctx, x, y, w, h, Math.floor(w / 4));
    ctx.fill();
    ctx.restore();
  }

  function drawHUD() {
    const x = 8, y = 8, w = canvas.width - 16, h = HUD_H - 16;
    drawGlass(x, y, w, h);
    ctx.fillStyle = COLOR_TEXT;
    ctx.font = '14px "Press Start 2P", monospace';
    const hud1 = `SCORE ${String(score).padStart(3, '0')}  SPEED ${String(fps).padStart(2, '0')}`;
    ctx.fillText(hud1, x + 12, y + 28);
    ctx.font = '12px "Press Start 2P", monospace';
    const hud2 = 'ARROWS/WASD  +/- SPEED  SPACE PAUSE  R RESTART';
    ctx.fillText(hud2, x + 12, y + 52);
  }

  function drawBorder() {
    const x = 4, y = HUD_H, w = canvas.width - 8, h = canvas.height - HUD_H - 4;
    ctx.strokeStyle = BORDER_COLOR;
    ctx.lineWidth = BORDER_THICK;
    ctx.beginPath();
    roundRect(ctx, x, y, w, h, 8);
    ctx.stroke();
  }

  // Input
  window.addEventListener('keydown', (e) => {
    // Prevent page scroll on arrows/space
    if (['ArrowUp','ArrowDown','ArrowLeft','ArrowRight',' ','Spacebar'].includes(e.key)) e.preventDefault();
    const key = e.key.toLowerCase();
    if (onMenu) {
      if (key === ' ' || key === 'enter') { onMenu = false; resetGame(); paused = false; gameOver = false; win = false; fps = START_FPS; if (!musicMuted) musicPlay(); }
      return;
    }
    if (key === 'escape') { location.reload(); }
    if (gameOver || win) {
      if (key === 'r' || key === 'к') { onMenu = false; resetGame(); gameOver = false; win = false; paused = false; fps = START_FPS; if (!musicMuted) musicPlay(); }
      return;
    }
    if (key === ' ') { paused = !paused; if (paused) musicPause(); else if (!musicMuted) musicPlay(); return; }
    if (key === 'm' || key === 'ь') { musicToggleMute(); return; }
    if (e.key === '-' || e.key === '_') { fps = Math.max(MIN_FPS, fps - 1); return; }
    if (e.key === '=' || e.key === '+') { fps = Math.min(MAX_FPS, fps + 1); return; }
    const [dx, dy] = dir;
    if (e.key === 'ArrowUp' || key === 'w' || key === 'ц') { if (!(dx === 0 && dy === 1)) pendingDir = [0, -1]; }
    else if (e.key === 'ArrowDown' || key === 's' || key === 'ы') { if (!(dx === 0 && dy === -1)) pendingDir = [0, 1]; }
    else if (e.key === 'ArrowLeft' || key === 'a' || key === 'ф') { if (!(dx === 1 && dy === 0)) pendingDir = [-1, 0]; }
    else if (e.key === 'ArrowRight' || key === 'd' || key === 'в') { if (!(dx === -1 && dy === 0)) pendingDir = [1, 0]; }
  });

  // Simple WebAudio background loop
  const AudioCtx = window.AudioContext || window.webkitAudioContext;
  let actx = null, musicOsc = null, musicGain = null;
  let musicMuted = false;
  function ensureAudio() {
    if (actx) return;
    try {
      actx = new AudioCtx();
      musicOsc = actx.createOscillator();
      musicGain = actx.createGain();
      musicOsc.type = 'square';
      musicOsc.connect(musicGain);
      musicGain.connect(actx.destination);
      musicGain.gain.value = 0.0;
      musicOsc.start();
      // schedule simple repeating melody
      let t = actx.currentTime;
      // Short, punchy 16th-note groove (NES-like)
      const seq = [262, 330, 392, 494, 392, 330, 349, 392, 440, 392, 349, 330, 294, 330, 392, 440];
      const step = 0.14; // shorter note length
      function schedule() {
        if (!musicOsc) return;
        for (let i = 0; i < 96; i++) {
          for (const f of seq) {
            // Set pitch
            musicOsc.frequency.setValueAtTime(f, t);
            // Gate envelope per note (staccato)
            musicGain.gain.cancelScheduledValues(t);
            musicGain.gain.setValueAtTime(0.0, t);
            musicGain.gain.linearRampToValueAtTime(0.055, t + 0.01); // quick attack
            musicGain.gain.linearRampToValueAtTime(0.0, t + step * 0.7); // release before next
            t += step;
          }
        }
        setTimeout(schedule, 4000);
      }
      schedule();
    } catch (e) { /* ignore */ }
  }
  function musicPlay() { if (musicMuted) return; ensureAudio(); if (musicGain) musicGain.gain.setTargetAtTime(0.04, actx.currentTime, 0.03); }
  function musicPause() { if (musicGain && actx) musicGain.gain.setTargetAtTime(0.0, actx.currentTime, 0.03); }
  function musicToggleMute() { musicMuted = !musicMuted; if (musicMuted) musicPause(); else musicPlay(); }

  // Loop
  let last = performance.now();
  let acc = 0;
  function loop(ts) {
    const dt = (ts - last) / 1000; last = ts;
    acc += dt;
    const step = 1 / Math.max(1, fps);

    // Update
    while (acc >= step) {
      acc -= step;
      if (!onMenu && !paused && !gameOver && !win) tick();
    }

    // Render
    drawGradient();
    if (onMenu) drawMenu();
    else {
      drawHUD();
      drawBorder();
      obstacles.forEach(key => drawObstacle(key.split(',').map(Number)));
      if (!win) drawFood(food);
      snake.forEach(drawSnakeCell);
      if (paused && !gameOver && !win) drawCenterText('Paused');
      if (gameOver) drawCenterText(`Game Over (${deathReason}). Press R to restart.`);
      if (win) drawCenterText(`You Win! Score: ${score}. Press R to restart.`);
    }

    requestAnimationFrame(loop);
  }

  function drawCenterText(t) {
    ctx.fillStyle = COLOR_TEXT;
    // Auto-fit text to available width (inside border)
    const margin = 28;
    const maxW = canvas.width - margin * 2;
    let size = 16;
    ctx.font = `${size}px "Press Start 2P", monospace`;
    let w = ctx.measureText(t).width;
    while (w > maxW && size > 10) {
      size -= 1;
      ctx.font = `${size}px "Press Start 2P", monospace`;
      w = ctx.measureText(t).width;
    }
    ctx.fillText(t, (canvas.width - w) / 2, Math.floor(canvas.height / 2));
  }

  function computeStartButton() {
    const padX = 24, padY = 12;
    const maxW = canvas.width * 0.86;
    let size = 16;
    const t = 'Press Start';
    ctx.font = `${size}px "Press Start 2P", monospace`;
    let textW = ctx.measureText(t).width;
    while (textW + padX * 2 > maxW && size > 10) {
      size -= 1;
      ctx.font = `${size}px "Press Start 2P", monospace`;
      textW = ctx.measureText(t).width;
    }
    const w = textW + padX * 2;
    const h = size + padY * 2;
    const x = (canvas.width - w) / 2;
    const y = (canvas.height - h) / 2;
    return {x, y, w, h, size, padX, padY, t};
  }

  function drawMenu() {
    const btn = computeStartButton();
    // Title above the button
    ctx.fillStyle = COLOR_TEXT;
    ctx.font = '18px "Press Start 2P", monospace';
    const title = 'Snake';
    const tw = ctx.measureText(title).width;
    const ty = Math.max(24, btn.y - 24);
    ctx.fillText(title, (canvas.width - tw) / 2, ty);

    // Button with fitted text
    drawGlass(btn.x, btn.y, btn.w, btn.h);
    ctx.font = `${btn.size}px "Press Start 2P", monospace`;
    ctx.fillText(btn.t, btn.x + btn.padX, btn.y + btn.h - btn.padY);
  }

  canvas.addEventListener('mouseup', (e) => {
    if (!onMenu) return;
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left, my = e.clientY - rect.top;
    const b = computeStartButton();
    if (mx >= b.x && mx <= b.x + b.w && my >= b.y && my <= b.y + b.h) { onMenu = false; resetGame(); paused = false; gameOver = false; win = false; fps = START_FPS; if (!musicMuted) musicPlay(); }
  });

  function tick() {
    dir = pendingDir.slice();
    const head = snake[0];
    const nx = head[0] + dir[0], ny = head[1] + dir[1];
    if (!(0 <= nx && nx < GRID_W && 0 <= ny && ny < GRID_H)) { gameOver = true; deathReason = 'Hit wall'; return; }
    const newHead = [nx, ny];

    const willEat = (food && nx === food[0] && ny === food[1]);

    if (obstacles.has(`${nx},${ny}`)) { gameOver = true; deathReason = 'Hit obstacle'; return; }

    const bodyToCheck = willEat ? snake : snake.slice(0, -1);
    if (bodyToCheck.some(([x, y]) => x === nx && y === ny)) { gameOver = true; deathReason = 'Hit self'; return; }

    snake.unshift(newHead);
    if (willEat) {
      score += 1;
      const excl = new Set(cellsToKey(snake));
      food = randomEmptyCell(new Set([...excl, ...obstacles]));
      if (!food) { win = true; return; }
      fps = Math.min(MAX_FPS, fps + 1);
      // Respawn obstacles up to 3
      const excl2 = new Set([...excl, `${food[0]},${food[1]}`]);
      obstacles = spawnObstacles(3, excl2);
    } else {
      snake.pop();
    }
  }

  // Start
  resetGame();
  onMenu = true;
  requestAnimationFrame(loop);
})();
