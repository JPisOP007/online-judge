/*
 * Thiran offline game — "Stack Frames".
 *
 * Shown when the browser reports the connection has dropped, so a lost network
 * during a contest is a few seconds of something to do rather than a dead page.
 *
 * The game: a call frame slides above your stack, one key drops it, and only
 * the part that overlaps the frame below survives. Misalign and your frames get
 * narrower until one misses entirely — at which point you have, correctly, a
 * StackOverflowError with a truncated trace. Your score is recursion depth.
 *
 * Deliberately cheap: this file registers two connection listeners at load and
 * does nothing else. No canvas, no DOM, no timers and no images exist until the
 * connection actually drops, and the loop stops when the overlay closes or the
 * tab is hidden. Everything drawn is a rectangle or a glyph, so there are no
 * assets to fetch — which matters, because by the time it runs there is no
 * network to fetch them over.
 *
 * The page has to be open already. A refresh while offline gets the browser's
 * own error page; serving our own would need a service worker caching an
 * offline route, which is a larger change with real staleness risk on
 * authenticated pages.
 */
(function () {
  'use strict';

  var BEST_KEY = 'thiran.offline.best';

  var INK = '#000000';
  var PAPER = '#FFFEF2';
  var YELLOW = '#FFD600';
  var RED = '#EF4444';
  var GREEN = '#22C55E';
  var MUTED = '#6B7280';
  var MONO = "'Space Mono', 'Courier New', monospace";

  var W = 720;              // logical canvas size; the element scales to fit
  var H = 300;
  var GUTTER = 116;         // left column holding the stack trace
  var PLAY_L = GUTTER + 10;
  var PLAY_R = W - 16;
  var ROW_H = 26;
  var ROW_GAP = 3;
  var BASE_Y = H - 34;      // top edge of the bottom frame
  var VISIBLE_ROWS = 7;     // frames kept on screen before the view scrolls
  var HOVER_GAP = 8;        // gap between the moving frame and the stack top
  var PERFECT_TOLERANCE = 3;
  var START_W = 240;
  var START_SPEED = 190;    // px/s
  var MAX_SPEED = 520;

  // Frame labels, in the order a plausible recursive solution would nest.
  var ROOT_LABELS = ['main()', 'solve()', 'read_input()'];
  var DEEP_LABELS = ['dfs(', 'backtrack(', 'memo(', 'divide(', 'merge('];

  var ui = null;            // built lazily on the first offline event
  var game = null;
  var rafId = 0;
  var lastFrame = 0;
  var visible = false;

  // ---------------------------------------------------------------- helpers

  function el(tag, styles, text) {
    var node = document.createElement(tag);
    if (styles) {
      for (var key in styles) {
        if (Object.prototype.hasOwnProperty.call(styles, key)) {
          node.style[key] = styles[key];
        }
      }
    }
    if (text) {
      node.textContent = text;
    }
    return node;
  }

  function readBest() {
    try {
      return parseInt(window.localStorage.getItem(BEST_KEY), 10) || 0;
    } catch (err) {
      return 0;   // private mode, or storage disabled
    }
  }

  function writeBest(value) {
    try {
      window.localStorage.setItem(BEST_KEY, String(value));
    } catch (err) {
      /* not worth interrupting a game over */
    }
  }

  function labelFor(depth) {
    if (depth < ROOT_LABELS.length) {
      return ROOT_LABELS[depth];
    }
    var name = DEEP_LABELS[(depth * 7) % DEEP_LABELS.length];
    return name + (depth - ROOT_LABELS.length + 1) + ')';
  }

  // ---------------------------------------------------------------- the game

  function Game() {
    this.best = readBest();
    this.reset();
  }

  Game.prototype.reset = function () {
    this.state = 'ready';       // ready | running | over
    this.frames = [{
      x: (W + GUTTER) / 2 - START_W / 2,
      w: START_W,
      label: labelFor(0),
      perfect: false
    }];
    this.slices = [];           // trimmed pieces, falling away
    this.moving = null;
    this.speed = START_SPEED;
    this.direction = 1;
    this.flash = 0;             // frames of "perfect" highlight
    this.shake = 0;
    this.overflowAt = 0;
  };

  Game.prototype.depth = function () {
    return this.frames.length - 1;
  };

  Game.prototype.start = function () {
    this.reset();
    this.state = 'running';
    this.spawn();
  };

  Game.prototype.spawn = function () {
    var top = this.frames[this.frames.length - 1];
    this.speed = Math.min(MAX_SPEED, START_SPEED + this.depth() * 11);
    this.direction = Math.random() < 0.5 ? 1 : -1;
    this.moving = {
      x: this.direction > 0 ? PLAY_L : PLAY_R - top.w,
      w: top.w,
      label: labelFor(this.frames.length)
    };
  };

  Game.prototype.drop = function () {
    if (this.state === 'ready' || this.state === 'over') {
      this.start();
      return;
    }
    if (!this.moving) {
      return;
    }

    var top = this.frames[this.frames.length - 1];
    var cur = this.moving;
    var offset = cur.x - top.x;

    if (Math.abs(offset) <= PERFECT_TOLERANCE) {
      // Snap a near-perfect drop and hand a sliver of width back, so a good
      // run is rewarded rather than merely punished more slowly.
      cur.x = top.x;
      cur.w = Math.min(START_W, top.w + 3);
      this.flash = 14;
      this.frames.push({ x: cur.x, w: cur.w, label: cur.label, perfect: true });
      this.moving = null;
      this.spawn();
      return;
    }

    var left = Math.max(cur.x, top.x);
    var right = Math.min(cur.x + cur.w, top.x + top.w);
    var overlap = right - left;

    if (overlap <= 0) {
      this.slices.push({
        x: cur.x, y: this.hoverY(), w: cur.w, vy: -60, vx: this.direction * 40, label: cur.label
      });
      this.moving = null;
      this.gameOver();
      return;
    }

    // Whatever hung over the edge is trimmed off and falls away.
    if (cur.x < left) {
      this.slices.push({
        x: cur.x, y: this.hoverY(), w: left - cur.x, vy: 0, vx: -70, label: ''
      });
    }
    if (cur.x + cur.w > right) {
      this.slices.push({
        x: right, y: this.hoverY(), w: cur.x + cur.w - right, vy: 0, vx: 70, label: ''
      });
    }

    this.frames.push({ x: left, w: overlap, label: cur.label, perfect: false });
    this.moving = null;
    this.shake = 5;
    this.spawn();
  };

  Game.prototype.hoverY = function () {
    return this.rowY(this.frames.length) - HOVER_GAP;
  };

  // Screen y for a frame at the given depth, with the view following the top.
  Game.prototype.rowY = function (index) {
    var scroll = Math.max(0, this.frames.length - VISIBLE_ROWS);
    return BASE_Y - (index - scroll) * (ROW_H + ROW_GAP);
  };

  Game.prototype.update = function (dt) {
    var i;

    for (i = this.slices.length - 1; i >= 0; i--) {
      var s = this.slices[i];
      s.vy += 1500 * dt;
      s.y += s.vy * dt;
      s.x += s.vx * dt;
      if (s.y > H + 60) {
        this.slices.splice(i, 1);
      }
    }

    if (this.flash > 0) {
      this.flash -= 1;
    }
    if (this.shake > 0) {
      this.shake -= 1;
    }

    if (this.state !== 'running' || !this.moving) {
      return;
    }

    var cur = this.moving;
    cur.x += this.direction * this.speed * dt;
    if (cur.x <= PLAY_L) {
      cur.x = PLAY_L;
      this.direction = 1;
    } else if (cur.x + cur.w >= PLAY_R) {
      cur.x = PLAY_R - cur.w;
      this.direction = -1;
    }
  };

  Game.prototype.gameOver = function () {
    this.state = 'over';
    this.overflowAt = this.depth();
    this.shake = 12;
    if (this.overflowAt > this.best) {
      this.best = this.overflowAt;
      writeBest(this.best);
    }
  };

  // ---------------------------------------------------------------- drawing

  Game.prototype.draw = function (ctx) {
    ctx.save();
    if (this.shake > 0) {
      ctx.translate((Math.random() - 0.5) * this.shake, (Math.random() - 0.5) * this.shake);
    }

    ctx.fillStyle = PAPER;
    ctx.fillRect(-20, -20, W + 40, H + 40);

    this.drawGutter(ctx);
    this.drawSlices(ctx);
    this.drawStack(ctx);
    this.drawMoving(ctx);
    this.drawHud(ctx);
    this.drawBanner(ctx);

    ctx.restore();
  };

  Game.prototype.drawGutter = function (ctx) {
    ctx.strokeStyle = '#D7D9DE';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(GUTTER, 8);
    ctx.lineTo(GUTTER, H - 8);
    ctx.stroke();

    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    ctx.font = '11px ' + MONO;

    // Depth numbers beside each visible frame, like a stack trace's line column.
    var start = Math.max(0, this.frames.length - VISIBLE_ROWS);
    for (var i = start; i < this.frames.length; i++) {
      var y = this.rowY(i) + ROW_H / 2;
      ctx.fillStyle = i === this.frames.length - 1 ? INK : MUTED;
      ctx.fillText('#' + i, GUTTER - 12, y);
    }
  };

  Game.prototype.drawFrame = function (ctx, frame, y, filled) {
    ctx.fillStyle = filled;
    ctx.fillRect(frame.x, y, frame.w, ROW_H);
    ctx.strokeStyle = INK;
    ctx.lineWidth = 3;
    ctx.strokeRect(frame.x, y, frame.w, ROW_H);

    if (frame.w < 46 || !frame.label) {
      return;
    }
    ctx.save();
    ctx.beginPath();
    ctx.rect(frame.x, y, frame.w, ROW_H);
    ctx.clip();
    ctx.fillStyle = INK;
    ctx.font = 'bold 12px ' + MONO;
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    ctx.fillText(frame.label, frame.x + 8, y + ROW_H / 2 + 1);
    if (frame.perfect && frame.w > 118) {
      ctx.fillStyle = GREEN;
      ctx.font = 'bold 11px ' + MONO;
      ctx.textAlign = 'right';
      ctx.fillText('inlined', frame.x + frame.w - 8, y + ROW_H / 2 + 1);
    }
    ctx.restore();
  };

  Game.prototype.drawStack = function (ctx) {
    var start = Math.max(0, this.frames.length - VISIBLE_ROWS);
    for (var i = start; i < this.frames.length; i++) {
      var y = this.rowY(i);
      var isTop = i === this.frames.length - 1;
      var fill = this.frames[i].perfect ? GREEN : YELLOW;
      if (!isTop) {
        // Older frames fade back so the live edge reads clearly.
        ctx.globalAlpha = Math.max(0.35, 1 - (this.frames.length - 1 - i) * 0.13);
      }
      this.drawFrame(ctx, this.frames[i], y, fill);
      ctx.globalAlpha = 1;
    }

    if (start > 0) {
      // In the gutter, not the play area: the tower drifts and would collide.
      ctx.fillStyle = MUTED;
      ctx.font = '11px ' + MONO;
      ctx.textAlign = 'left';
      ctx.textBaseline = 'middle';
      ctx.fillText('+' + start + ' frames', 14, BASE_Y + 22);
    }
  };

  Game.prototype.drawMoving = function (ctx) {
    if (!this.moving) {
      return;
    }
    var y = this.hoverY();
    this.drawFrame(ctx, this.moving, y, this.flash > 0 ? GREEN : YELLOW);

    // A dropped-shadow guide showing where it would land.
    ctx.setLineDash([5, 5]);
    ctx.strokeStyle = MUTED;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(this.moving.x + 1, y + ROW_H + 4);
    ctx.lineTo(this.moving.x + 1, this.rowY(this.frames.length - 1) - 3);
    ctx.moveTo(this.moving.x + this.moving.w - 1, y + ROW_H + 4);
    ctx.lineTo(this.moving.x + this.moving.w - 1, this.rowY(this.frames.length - 1) - 3);
    ctx.stroke();
    ctx.setLineDash([]);
  };

  Game.prototype.drawSlices = function (ctx) {
    ctx.lineWidth = 2;
    for (var i = 0; i < this.slices.length; i++) {
      var s = this.slices[i];
      ctx.fillStyle = RED;
      ctx.fillRect(s.x, s.y, s.w, ROW_H);
      ctx.strokeStyle = INK;
      ctx.strokeRect(s.x, s.y, s.w, ROW_H);
    }
  };

  Game.prototype.drawHud = function (ctx) {
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';
    ctx.font = 'bold 13px ' + MONO;
    ctx.fillStyle = INK;
    ctx.fillText('DEPTH ' + this.depth(), 14, 14);
    ctx.font = '11px ' + MONO;
    ctx.fillStyle = MUTED;
    ctx.fillText('BEST ' + this.best, 14, 32);
  };

  Game.prototype.drawBanner = function (ctx) {
    if (this.state === 'running') {
      return;
    }

    var boxW = 340;
    var boxH = this.state === 'ready' ? 84 : 116;
    var boxX = (W + GUTTER) / 2 - boxW / 2;
    var boxY = 26;

    // Offset shadow, as everywhere else on the site: without it the panel
    // collides with the frames behind rather than sitting over them.
    ctx.fillStyle = INK;
    ctx.fillRect(boxX + 6, boxY + 6, boxW, boxH);
    ctx.fillStyle = PAPER;
    ctx.fillRect(boxX, boxY, boxW, boxH);
    ctx.strokeStyle = INK;
    ctx.lineWidth = 3;
    ctx.strokeRect(boxX, boxY, boxW, boxH);

    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';

    if (this.state === 'ready') {
      ctx.fillStyle = INK;
      ctx.font = 'bold 15px ' + MONO;
      ctx.fillText('BUILD THE CALL STACK', boxX + boxW / 2, boxY + 16);
      ctx.font = '11px ' + MONO;
      ctx.fillStyle = MUTED;
      ctx.fillText('space drops a frame · only the overlap survives',
                   boxX + boxW / 2, boxY + 40);
      ctx.fillStyle = INK;
      ctx.font = 'bold 12px ' + MONO;
      ctx.fillText('press space to recurse', boxX + boxW / 2, boxY + 60);
      return;
    }

    ctx.fillStyle = RED;
    ctx.font = 'bold 15px ' + MONO;
    ctx.fillText('RE · StackOverflowError', boxX + boxW / 2, boxY + 14);

    ctx.fillStyle = MUTED;
    ctx.font = '11px ' + MONO;
    ctx.textAlign = 'left';
    var traceX = boxX + 18;
    var shown = Math.min(2, this.frames.length);
    for (var i = 0; i < shown; i++) {
      var frame = this.frames[this.frames.length - 1 - i];
      ctx.fillText('at ' + frame.label, traceX, boxY + 38 + i * 15);
    }
    if (this.frames.length > shown) {
      ctx.fillText('... ' + (this.frames.length - shown) + ' more frames',
                   traceX, boxY + 38 + shown * 15);
    }

    ctx.textAlign = 'center';
    ctx.fillStyle = INK;
    ctx.font = 'bold 12px ' + MONO;
    ctx.fillText('depth ' + this.overflowAt + ' · space to unwind',
                 boxX + boxW / 2, boxY + boxH - 24);
  };

  // ---------------------------------------------------------------- overlay

  function buildUI() {
    var backdrop = el('div', {
      position: 'fixed',
      inset: '0',
      zIndex: '2147483000',
      background: 'rgba(0, 0, 0, 0.72)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '16px'
    });
    backdrop.setAttribute('role', 'dialog');
    backdrop.setAttribute('aria-modal', 'true');
    backdrop.setAttribute('aria-label', 'You are offline');

    var panel = el('div', {
      width: '100%',
      maxWidth: '780px',
      background: PAPER,
      border: '3px solid ' + INK,
      boxShadow: '8px 8px 0 ' + INK,
      padding: '18px'
    });

    var head = el('div', {
      display: 'flex',
      alignItems: 'baseline',
      justifyContent: 'space-between',
      gap: '12px',
      flexWrap: 'wrap',
      marginBottom: '12px'
    });

    var title = el('div', {
      fontFamily: MONO,
      fontWeight: '700',
      fontSize: '18px',
      textTransform: 'uppercase',
      color: INK
    }, 'Offline · stack frames');

    var status = el('div', {
      fontFamily: MONO,
      fontSize: '12px',
      color: MUTED
    }, 'The judge is unreachable. Recurse until it comes back.');

    head.appendChild(title);
    head.appendChild(status);

    var canvas = el('canvas', {
      display: 'block',
      width: '100%',
      border: '3px solid ' + INK,
      background: PAPER,
      touchAction: 'manipulation'
    });

    var foot = el('div', {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: '12px',
      flexWrap: 'wrap',
      marginTop: '12px'
    });

    var hint = el('div', {
      fontFamily: MONO,
      fontSize: '12px',
      color: MUTED
    }, 'Space or tap to drop · Esc to close');

    var buttons = el('div', { display: 'flex', gap: '8px', flexWrap: 'wrap' });

    var reload = el('button', {
      fontFamily: MONO,
      fontWeight: '700',
      fontSize: '12px',
      textTransform: 'uppercase',
      padding: '8px 14px',
      border: '3px solid ' + INK,
      background: YELLOW,
      color: INK,
      cursor: 'pointer',
      display: 'none'
    }, 'Back online — reload');
    reload.type = 'button';

    var close = el('button', {
      fontFamily: MONO,
      fontWeight: '700',
      fontSize: '12px',
      textTransform: 'uppercase',
      padding: '8px 14px',
      border: '3px solid ' + INK,
      background: PAPER,
      color: INK,
      cursor: 'pointer'
    }, 'Close');
    close.type = 'button';

    buttons.appendChild(reload);
    buttons.appendChild(close);
    foot.appendChild(hint);
    foot.appendChild(buttons);

    panel.appendChild(head);
    panel.appendChild(canvas);
    panel.appendChild(foot);
    backdrop.appendChild(panel);

    close.addEventListener('click', hide);
    reload.addEventListener('click', function () {
      window.location.reload();
    });
    backdrop.addEventListener('click', function (event) {
      if (event.target === backdrop) {
        hide();
      }
    });
    canvas.addEventListener('pointerdown', function (event) {
      event.preventDefault();
      if (game) {
        game.drop();
      }
    });

    return {
      backdrop: backdrop,
      canvas: canvas,
      ctx: canvas.getContext('2d'),
      status: status,
      reload: reload
    };
  }

  function sizeCanvas() {
    if (!ui) {
      return;
    }
    var ratio = window.devicePixelRatio || 1;
    var cssWidth = ui.canvas.clientWidth || W;
    var cssHeight = Math.round(cssWidth * (H / W));
    ui.canvas.style.height = cssHeight + 'px';
    ui.canvas.width = Math.round(cssWidth * ratio);
    ui.canvas.height = Math.round(cssHeight * ratio);
    // Draw in logical units regardless of element or device size.
    ui.ctx.setTransform(ui.canvas.width / W, 0, 0, ui.canvas.height / H, 0, 0);
  }

  function loop(timestamp) {
    if (!visible) {
      return;
    }
    rafId = window.requestAnimationFrame(loop);
    if (!lastFrame) {
      lastFrame = timestamp;
    }
    // Clamped so a backgrounded tab cannot slide the frame half a screen on
    // the tick it comes back.
    var dt = Math.min((timestamp - lastFrame) / 1000, 0.05);
    lastFrame = timestamp;
    game.update(dt);
    game.draw(ui.ctx);
  }

  function startLoop() {
    if (rafId) {
      return;
    }
    lastFrame = 0;
    rafId = window.requestAnimationFrame(loop);
  }

  function stopLoop() {
    if (rafId) {
      window.cancelAnimationFrame(rafId);
      rafId = 0;
    }
  }

  function onKeyDown(event) {
    if (!visible) {
      return;
    }
    if (event.key === 'Escape') {
      hide();
      return;
    }
    if (event.code === 'Space' || event.key === ' ' ||
        event.key === 'ArrowDown' || event.key === 'Enter') {
      event.preventDefault();   // stop the page scrolling behind the overlay
      game.drop();
    }
  }

  function onVisibility() {
    if (!visible) {
      return;
    }
    if (document.hidden) {
      stopLoop();
    } else {
      startLoop();
    }
  }

  function show() {
    if (visible) {
      return;
    }
    if (!ui) {
      ui = buildUI();
      game = new Game();
    }
    document.body.appendChild(ui.backdrop);
    visible = true;
    sizeCanvas();
    game.reset();
    game.draw(ui.ctx);
    startLoop();

    document.addEventListener('keydown', onKeyDown, true);
    window.addEventListener('resize', sizeCanvas);
    document.addEventListener('visibilitychange', onVisibility);
  }

  function hide() {
    if (!visible) {
      return;
    }
    visible = false;
    stopLoop();
    if (ui.backdrop.parentNode) {
      ui.backdrop.parentNode.removeChild(ui.backdrop);
    }
    document.removeEventListener('keydown', onKeyDown, true);
    window.removeEventListener('resize', sizeCanvas);
    document.removeEventListener('visibilitychange', onVisibility);
  }

  function onOffline() {
    show();
  }

  function onOnline() {
    if (!visible) {
      return;
    }
    ui.status.textContent = 'Connection is back. Reload when you are ready.';
    ui.status.style.color = INK;
    ui.reload.style.display = 'inline-block';
  }

  window.addEventListener('offline', onOffline);
  window.addEventListener('online', onOnline);

  // Exposed so a failed request can open it too: navigator.onLine reports the
  // link, not whether anything is reachable, so a request that dies is often
  // the first real evidence of an outage.
  window.ThiranOfflineGame = { show: show, hide: hide };
}());
