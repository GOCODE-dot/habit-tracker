/* =====================================================
   LIVE DESK CLOCK
===================================================== */
function pad(n){ return n.toString().padStart(2,'0'); }

function tickClock(){
  const now = new Date();
  document.getElementById('clockTime').textContent =
    `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
  document.getElementById('clockDate').textContent =
    now.toLocaleDateString(undefined, { weekday:'long', year:'numeric', month:'long', day:'numeric' });
}
tickClock();
setInterval(tickClock, 1000);

/* =====================================================
   DIAL TICK MARKS (drawn once)
===================================================== */
(function drawTicks(){
  const g = document.getElementById('dialTicks');
  const cx = 120, cy = 120, rOuter = 105, rInner = 97;
  for (let i = 0; i < 60; i++){
    const angle = (i / 60) * 2 * Math.PI - Math.PI/2;
    const isMajor = i % 5 === 0;
    const rI = isMajor ? rInner - 4 : rInner;
    const x1 = cx + rI * Math.cos(angle);
    const y1 = cy + rI * Math.sin(angle);
    const x2 = cx + rOuter * Math.cos(angle);
    const y2 = cy + rOuter * Math.sin(angle);
    const line = document.createElementNS('http://www.w3.org/2000/svg','line');
    line.setAttribute('x1', x1); line.setAttribute('y1', y1);
    line.setAttribute('x2', x2); line.setAttribute('y2', y2);
    line.setAttribute('class', 'dial-tick');
    line.setAttribute('opacity', isMajor ? '0.9' : '0.35');
    g.appendChild(line);
  }
})();

/* =====================================================
   STOPWATCH
===================================================== */
const CIRCUMFERENCE = 659.7;
let swElapsedMs = 0;      // total elapsed while running (accumulated)
let swRunning = false;
let swStartTs = null;     // performance.now() timestamp when current run started
let swRafId = null;
let laps = [];

const dialProgress = document.getElementById('dialProgress');
const stopwatchDisplay = document.getElementById('stopwatchDisplay');
const dialCaption = document.getElementById('dialCaption');
const btnStartPause = document.getElementById('btnStartPause');
const btnLap = document.getElementById('btnLap');
const btnReset = document.getElementById('btnReset');
const lapsWrap = document.getElementById('lapsWrap');
const lapsList = document.getElementById('lapsList');

function formatStopwatch(ms){
  const totalCentis = Math.floor(ms / 10);
  const centis = totalCentis % 100;
  const totalSeconds = Math.floor(ms / 1000);
  const seconds = totalSeconds % 60;
  const minutes = Math.floor(totalSeconds / 60);
  return `${pad(minutes)}:${pad(seconds)}.${pad(centis)}`;
}

function currentElapsedMs(){
  if (swRunning) return swElapsedMs + (performance.now() - swStartTs);
  return swElapsedMs;
}

function renderStopwatch(){
  const ms = currentElapsedMs();
  stopwatchDisplay.textContent = formatStopwatch(ms);
  const secondsIntoMinute = (ms / 1000) % 60;
  const offset = CIRCUMFERENCE - (secondsIntoMinute / 60) * CIRCUMFERENCE;
  dialProgress.style.strokeDashoffset = offset;
}

function loop(){
  renderStopwatch();
  swRafId = requestAnimationFrame(loop);
}

btnStartPause.addEventListener('click', () => {
  if (!swRunning){
    swRunning = true;
    swStartTs = performance.now();
    btnStartPause.textContent = 'Pause';
    dialCaption.textContent = 'running';
    dialCaption.classList.add('running');
    loop();
  } else {
    swRunning = false;
    swElapsedMs += performance.now() - swStartTs;
    cancelAnimationFrame(swRafId);
    btnStartPause.textContent = 'Resume';
    dialCaption.textContent = 'paused';
    dialCaption.classList.remove('running');
    renderStopwatch();
  }
});

btnLap.addEventListener('click', () => {
  const ms = currentElapsedMs();
  laps.push(ms);
  lapsWrap.hidden = false;
  const li = document.createElement('li');
  const prev = laps.length > 1 ? laps[laps.length - 2] : 0;
  li.innerHTML = `<span>Lap ${laps.length}</span><span>${formatStopwatch(ms - prev)} · ${formatStopwatch(ms)}</span>`;
  lapsList.prepend(li);
});

btnReset.addEventListener('click', () => {
  swRunning = false;
  swElapsedMs = 0;
  cancelAnimationFrame(swRafId);
  laps = [];
  lapsList.innerHTML = '';
  lapsWrap.hidden = true;
  btnStartPause.textContent = 'Start';
  dialCaption.textContent = 'ready';
  dialCaption.classList.remove('running');
  renderStopwatch();
});

renderStopwatch();

/* Save stopwatch time to a habit */
document.getElementById('btnSaveSession').addEventListener('click', async () => {
  const select = document.getElementById('habitSelect');
  const habitId = select.value;
  const hint = document.getElementById('saveHint');
  if (!habitId){
    hint.textContent = 'Pick a habit first.';
    return;
  }
  const totalSeconds = Math.floor(currentElapsedMs() / 1000);
  if (totalSeconds <= 0){
    hint.textContent = 'Start the stopwatch before saving.';
    return;
  }
  const res = await fetch('/api/timer_log', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ habit_id: Number(habitId), seconds: totalSeconds })
  });
  if (res.ok){
    hint.textContent = `Logged ${formatStopwatch(totalSeconds*1000)} just now.`;
    btnReset.click();
    loadData();
  } else {
    hint.textContent = 'Could not save. Try again.';
  }
});

/* =====================================================
   HABITS: LOAD + RENDER
===================================================== */
let selectedIcon = '✅';
let selectedColor = '#e3a857';

async function loadData(){
  const res = await fetch('/api/data');
  const data = await res.json();
  renderHabits(data.habits);
  renderTodayStrip(data.today_progress);
  populateHabitSelect(data.habits);
}

function renderTodayStrip(progress){
  document.getElementById('todayDoneCount').textContent = progress.done;
  document.getElementById('todayTotalCount').textContent = progress.total;
  document.getElementById('todayPct').textContent = progress.pct + '%';
  document.getElementById('todayProgressFill').style.width = progress.pct + '%';
}

function populateHabitSelect(habits){
  const select = document.getElementById('habitSelect');
  const currentVal = select.value;
  select.innerHTML = '<option value="">Select a habit…</option>' +
    habits.map(h => `<option value="${h.id}">${h.icon} ${escapeHtml(h.name)}</option>`).join('');
  if (currentVal) select.value = currentVal;
}

function escapeHtml(str){
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function humanDuration(seconds){
  if (!seconds) return null;
  const h = Math.floor(seconds/3600);
  const m = Math.floor((seconds%3600)/60);
  if (h > 0) return `${h}h ${m}m logged`;
  if (m > 0) return `${m}m logged`;
  return `${seconds}s logged`;
}

function renderHabits(habits){
  const list = document.getElementById('habitsList');
  const empty = document.getElementById('emptyState');
  list.innerHTML = '';

  if (!habits.length){
    empty.hidden = false;
    return;
  }
  empty.hidden = true;

  habits.forEach(h => {
    const card = document.createElement('div');
    card.className = 'habit-card';
    card.style.setProperty('--habit-color', h.color);

    const todayCell = h.calendar[h.calendar.length - 1];
    const durationNote = humanDuration(h.total_seconds_30d);

    card.innerHTML = `
      <div class="habit-top">
        <div class="habit-id-group">
          <div class="habit-icon">${h.icon}</div>
          <div>
            <p class="habit-name">${escapeHtml(h.name)}</p>
            <div class="habit-cat">${escapeHtml(h.category)}</div>
          </div>
        </div>
        <div class="habit-actions">
          <button class="today-toggle ${todayCell.completed ? 'done' : ''}" title="Toggle today" data-habit="${h.id}" data-date="${todayCell.date}">
            ${todayCell.completed ? '✓' : ''}
          </button>
          <button class="habit-delete" data-delete="${h.id}" title="Archive habit">✕</button>
        </div>
      </div>
      <div class="habit-stats-row">
        <span class="stat-streak">streak <b>${h.current_streak}d</b></span>
        <span class="stat-longest">best <b>${h.longest_streak}d</b></span>
        <span class="stat-rate">30d <b>${h.completion_rate}%</b></span>
        ${durationNote ? `<span class="stat-duration">${durationNote}</span>` : ''}
      </div>
      <div class="ledger-row">
        ${h.calendar.map(c => `
          <div class="ledger-cell ${c.completed ? 'done' : ''} ${c.is_today ? 'today' : ''} ${c.is_future ? 'future' : ''}"
               data-habit="${h.id}" data-date="${c.date}"
               data-tip="${c.weekday} ${c.day}${c.duration ? ' · ' + humanDuration(c.duration) : ''}">
          </div>
        `).join('')}
      </div>
    `;
    list.appendChild(card);
  });

  // wire up toggles
  list.querySelectorAll('.today-toggle, .ledger-cell:not(.future)').forEach(el => {
    el.addEventListener('click', async () => {
      const habitId = el.dataset.habit;
      const date = el.dataset.date;
      await fetch('/api/toggle', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ habit_id: Number(habitId), date })
      });
      loadData();
    });
  });

  list.querySelectorAll('[data-delete]').forEach(el => {
    el.addEventListener('click', async (e) => {
      e.stopPropagation();
      if (!confirm('Archive this habit? Its history will be kept but hidden.')) return;
      await fetch(`/api/habits/${el.dataset.delete}`, { method:'DELETE' });
      loadData();
    });
  });
}

/* =====================================================
   ADD HABIT MODAL
===================================================== */
const modalBackdrop = document.getElementById('modalBackdrop');

document.getElementById('openAddHabit').addEventListener('click', () => {
  document.getElementById('habitName').value = '';
  document.getElementById('habitCategory').value = '';
  modalBackdrop.hidden = false;
  document.getElementById('habitName').focus();
});
document.getElementById('cancelAddHabit').addEventListener('click', () => {
  modalBackdrop.hidden = true;
});
modalBackdrop.addEventListener('click', (e) => {
  if (e.target === modalBackdrop) modalBackdrop.hidden = true;
});

document.querySelectorAll('.icon-opt').forEach((btn, i) => {
  if (i === 0) btn.classList.add('selected');
  btn.addEventListener('click', () => {
    document.querySelectorAll('.icon-opt').forEach(b => b.classList.remove('selected'));
    btn.classList.add('selected');
    selectedIcon = btn.dataset.icon;
  });
});
document.querySelectorAll('.color-opt').forEach((btn, i) => {
  if (i === 0) btn.classList.add('selected');
  btn.addEventListener('click', () => {
    document.querySelectorAll('.color-opt').forEach(b => b.classList.remove('selected'));
    btn.classList.add('selected');
    selectedColor = btn.dataset.color;
  });
});

document.getElementById('confirmAddHabit').addEventListener('click', async () => {
  const name = document.getElementById('habitName').value.trim();
  const category = document.getElementById('habitCategory').value.trim() || 'General';
  if (!name){
    document.getElementById('habitName').focus();
    return;
  }
  await fetch('/api/habits', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ name, category, icon: selectedIcon, color: selectedColor })
  });
  modalBackdrop.hidden = true;
  loadData();
});

/* =====================================================
   INIT
===================================================== */
loadData();
setInterval(loadData, 60000); // keep calendar/today marker fresh across midnight etc.

