/* PosterWall card – photos pinned like on a pinboard: on every tick the front photo leaves, a new one is pinned behind.
   A small clock, weather and the next events. All settings come live from the PosterWall integration.
   Config: type: custom:posterwall-card, wall: <config entry id>, fullscreen: true|false, aspect_ratio: "16:9"
   Robust on weak devices and streamed screens: one photo is loaded at a time (one in stock), every step has a time limit,
   a watchdog restarts a stalled wall, photos are decoded at most 720 px wide. */
(() => {
  const VERSION = "1.0.6";
  const T = {
    en: {
      loading: "Loading photos …", none: "No photos found in this folder or album.", pick: "Choose a wall in the card settings.",
      gone: "This wall does not exist anymore.", today: "Today", tomorrow: "Tomorrow", noEvents: "No events",
      ago: (n) => (n === 1 ? "One year ago today" : `${n} years ago today`), wall: "Wall", fullscreen: "Full screen (for a screen that only shows the wall)",
      ratio: "Aspect ratio", more: "Everything else is set in the PosterWall panel in the sidebar.", noWalls: "No wall yet – add PosterWall under Settings → Devices & services.",
    },
    de: {
      loading: "Fotos werden geladen …", none: "In diesem Ordner oder Album sind keine Fotos.", pick: "Wähle in den Karteneinstellungen eine Wand.",
      gone: "Diese Wand gibt es nicht mehr.", today: "Heute", tomorrow: "Morgen", noEvents: "Keine Termine",
      ago: (n) => (n === 1 ? "Heute vor einem Jahr" : `Heute vor ${n} Jahren`), wall: "Wand", fullscreen: "Vollbild (für einen Bildschirm, der nur die Wand zeigt)",
      ratio: "Seitenverhältnis", more: "Alles andere stellst du in der Seite PosterWall in der Seitenleiste ein.", noWalls: "Noch keine Wand – füge PosterWall unter Einstellungen → Geräte & Dienste hinzu.",
    },
  };
  const WEATHER = {
    "clear-night": "mdi:weather-night", cloudy: "mdi:weather-cloudy", exceptional: "mdi:alert-circle-outline",
    fog: "mdi:weather-fog", hail: "mdi:weather-hail", lightning: "mdi:weather-lightning",
    "lightning-rainy": "mdi:weather-lightning-rainy", partlycloudy: "mdi:weather-partly-cloudy",
    pouring: "mdi:weather-pouring", rainy: "mdi:weather-rainy", snowy: "mdi:weather-snowy",
    "snowy-rainy": "mdi:weather-snowy-rainy", sunny: "mdi:weather-sunny", windy: "mdi:weather-windy",
    "windy-variant": "mdi:weather-windy-variant",
  };
  const SIZE = { small: [0.22, 0.27], medium: [0.29, 0.36], large: [0.36, 0.44] };
  const EFFECTS = ["drop", "fade", "blow", "flip"];
  const MIN_TICK = 5;   // seconds: fading in (1.6 s) and leaving (0.9 s) need some room
  const WIDTH = 720;    // pixels: photos are kept at most this wide (the wall never shows them bigger)
  const RATIOS = ["16:9", "16:10", "4:3", "3:2", "21:9", "1:1", "9:16"];
  const wait = (ms) => new Promise((ok) => setTimeout(ok, ms));
  const limit = (p, ms) => Promise.race([p, new Promise((_, no) => setTimeout(() => no(new Error("timeout")), ms))]);
  const free = (c) => { if (c) { c.width = 0; c.height = 0; } }; // release image memory right away
  const rand = (a, b) => a + Math.random() * (b - a);
  const esc = (x) => String(x ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  class PosterWallCard extends HTMLElement {
    static getConfigElement() { return document.createElement("posterwall-card-editor"); }
    static async getStubConfig(hass) {
      let wall = "";
      try { const w = await hass.callWS({ type: "posterwall/walls" }); wall = (w[0] && w[0].entry_id) || ""; } catch (e) { /* none */ }
      return { wall, fullscreen: false, aspect_ratio: "16:9" };
    }
    setConfig(c) {
      const old = this._c;
      this._c = Object.assign({ wall: "", fullscreen: false, aspect_ratio: "16:9", preview: false }, c || {});
      if (old && (old.wall !== this._c.wall || old.fullscreen !== this._c.fullscreen)) { this._stop(); if (this._hass) this._start(); }
      else if (this._frame) this._applyFrame();
    }
    getCardSize() { return this._c && this._c.fullscreen ? 12 : 6; }
    getGridOptions() { return { columns: 12, rows: "auto", min_columns: 6 }; }
    // display pages (full screen) are shared screens: they speak the language of Home Assistant itself,
    // not the browser default of a Cast device or kiosk user
    get _lang() {
      const h = this._hass;
      return (h && ((this._c.fullscreen && !this._c.preview && h.config?.language) || h.locale?.language || h.language)) || navigator.language || "en";
    }
    get _t() { return T[this._lang.slice(0, 2)] || T.en; }
    _tz() { return (this._hass && this._hass.config && this._hass.config.time_zone) || undefined; }
    _parts(d) {
      // date and time in the time zone of Home Assistant (a streaming browser often runs in UTC)
      const f = new Intl.DateTimeFormat("en-GB", { timeZone: this._tz(), year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
      const o = {}; f.formatToParts(d).forEach((p) => { o[p.type] = p.value; });
      return { hh: o.hour, mm: o.minute, day: `${o.year}-${o.month}-${o.day}` };
    }
    _fmt(d, opts) { return new Intl.DateTimeFormat(this._lang, { timeZone: this._tz(), ...opts }).format(d); }

    set hass(h) {
      const first = !this._hass;
      this._hass = h;
      if (first) this._start();
      else this._showWeather();
    }
    connectedCallback() { if (this._hass && !this._on) this._start(); }
    disconnectedCallback() { this._stop(); }

    /* ---------- start / stop ---------- */
    _stop() {
      this._on = false;
      this._gen = (this._gen || 0) + 1; // drop loads of the previous round
      clearTimeout(this._clockT); clearTimeout(this._tickT); clearTimeout(this._fillT); clearTimeout(this._retryT); this._retryT = null;
      clearInterval(this._eventsT); clearInterval(this._guardT);
      (this._stack || []).forEach((el) => free(el.querySelector("canvas"))); this._stack = [];
      (this._stock || []).forEach((f) => free(f.c)); this._stock = [];
      if (this._sub) { this._sub.then((u) => u && u()).catch(() => {}); this._sub = null; }
      if (this._fc) { this._fc.then((u) => u && u()).catch(() => {}); this._fc = null; }
      if (this._conn && this._ready) this._conn.removeEventListener("ready", this._ready);
      this._conn = null; this._s = null; this._p = null; this._started = false; this._sleeping = false;
      if (this._layer) { this._layer.remove(); this._layer = null; }
    }
    _start() {
      if (this._on || !this.isConnected || !this._hass || !this._c) return;
      this._on = true;
      this._gen = (this._gen || 0) + 1;
      this._stack = []; this._stock = []; this._soft = 0; this._z = 50000;
      this._since = this._last = Date.now();
      // full screen: the wall lies above everything (sidebar, header) as its own layer of the page
      if (this._c.fullscreen && !this._c.preview) {
        this._layer = document.createElement("div");
        this._layer.className = "posterwall-layer";
        document.body.appendChild(this._layer);
        this._root = this._layer.attachShadow({ mode: "open" });
      } else {
        if (!this.shadowRoot) this.attachShadow({ mode: "open" });
        this._root = this.shadowRoot;
      }
      this._root.innerHTML = `<style>${CSS}</style>
        <div class="frame"><div class="wall">
          <div class="photos"></div>
          <div class="clock"><div class="time"></div><div class="date"></div></div>
          <div class="info"><div class="weather"><ha-icon></ha-icon><div class="temp"></div><div class="hl"></div></div><div class="events"></div></div>
          <div class="night"></div>
          <div class="msg"></div>
        </div></div>`;
      this._frame = this._root.querySelector(".frame");
      this._wall = this._root.querySelector(".wall");
      this._photos = this._root.querySelector(".photos");
      this._applyFrame();
      this._clock();
      if (!this._c.wall) { this._message(this._t.pick); return; }
      this._message(this._t.loading);
      this._conn = this._hass.connection;
      this._ready = () => this._reconnect();
      this._conn.addEventListener("ready", this._ready);
      this._subscribe();
      this._eventsT = setInterval(() => this._loadEvents(), 15 * 60 * 1000);
      this._guardT = setInterval(() => this._guard(), 30000);
    }
    _applyFrame() {
      const full = !!this._c.fullscreen;
      this._frame.classList.toggle("full", full);
      const [w, h] = String(this._c.aspect_ratio || "16:9").split(":").map(Number);
      this._frame.style.aspectRatio = full ? "" : `${w || 16} / ${h || 9}`;
    }
    _message(text) {
      const m = this._root && this._root.querySelector(".msg");
      if (!m) return;
      m.textContent = text || ""; m.style.display = text ? "" : "none";
    }
    _reconnect() {
      // Home Assistant was restarted: subscribe again, weather and events again
      if (!this._on) return;
      if (this._sub) { this._sub.then((u) => u && u()).catch(() => {}); this._sub = null; }
      this._subscribe();
    }
    _later() { if (this._on && !this._retryT) this._retryT = setTimeout(() => { this._retryT = null; this._reconnect(); }, 60000); }
    _subscribe() {
      this._sub = this._hass.connection.subscribeMessage((p) => this._settings(p), { type: "posterwall/subscribe", entry_id: this._c.wall })
        .catch((e) => { if (e && e.code === "not_found") this._message(this._t.gone); this._later(); return null; });
    }

    /* ---------- settings ---------- */
    _settings(p) {
      const old = this._p, o = old ? old.settings : {};
      this._p = p; this._s = p.settings;
      const s = this._s, w = this._wall;
      if (!this._c.preview && this._c.fullscreen && old && (p.version !== VERSION || p.reload !== old.reload)) this._reload(); // integration updated or "reload screens"
      w.dataset.bg = s.background;
      this._root.querySelector(".clock").style.display = s.clock ? "" : "none";
      const weatherOn = s.weather && p.weather, eventsOn = s.events && p.calendars.length;
      const info = this._root.querySelector(".info");
      info.style.display = weatherOn || eventsOn ? "" : "none";
      info.querySelector(".weather").style.display = weatherOn ? "" : "none";
      info.querySelector(".events").style.display = eventsOn ? "" : "none";
      info.classList.toggle("only", !weatherOn || !eventsOn);
      this._stack.forEach((el) => el.classList.toggle("cap", !!(s.caption || el._ago)));
      if (!old || old.weather !== p.weather) this._weatherSub();
      if (!old || old.calendars.join() !== p.calendars.join() || old.events !== p.events || old.event_days !== p.event_days) this._loadEvents();
      this._night();
      if (!p.photos) {
        this._message(p.loading ? this._t.loading : p.error || this._t.none);
        return;
      }
      this._message(this._stack.length ? "" : this._t.loading);
      if (!this._started) { this._begin(); return; }
      if (o.album !== s.album || (old.loading && !p.loading)) { this._restart(); return; } // other album or photos read again
      if (o.count !== s.count) this._pump();
      if (o.interval !== s.interval) { clearTimeout(this._tickT); this._tickT = setTimeout(() => this._tick(), this._tickTime()); }
      if (o.size !== s.size) this._stack.forEach((el) => el.classList.add("resize"));
    }
    _tickTime() { return Math.max(MIN_TICK, (this._s && this._s.interval) || 15) * 1000; }

    /* ---------- night ---------- */
    _isNight() {
      const s = this._s; if (!s || s.night_mode === "off") return false;
      const { hh, mm } = this._parts(new Date()), now = `${hh}:${mm}`, a = s.night_start.slice(0, 5), b = s.night_end.slice(0, 5);
      return a <= b ? now >= a && now < b : now >= a || now < b;
    }
    _night() {
      const s = this._s; if (!s || !this._wall) return;
      const night = this._isNight(), mode = night ? s.night_mode : "off";
      this._wall.dataset.night = mode;
      this._root.querySelector(".night").style.opacity = mode === "dim" ? String(1 - s.night_brightness / 100) : "";
      const sleeping = mode === "clock" || mode === "dark";
      if (sleeping && !this._sleeping) { this._sleeping = true; clearTimeout(this._tickT); }
      else if (!sleeping && this._sleeping) { this._sleeping = false; this._last = Date.now(); this._pump(); this._tickT = setTimeout(() => this._tick(), this._tickTime()); }
    }

    /* ---------- clock ---------- */
    _clock() {
      const d = new Date(), z = this._parts(d), r = this._root;
      r.querySelector(".time").textContent = `${z.hh}:${z.mm}`;
      r.querySelector(".date").textContent = this._fmt(d, { weekday: "short", day: "numeric", month: "long" });
      this._night();
      // a screen that only shows the wall loads fresh every night at 4 (cleans up long-running browsers)
      if (this._c.fullscreen && !this._c.preview && z.hh === "04" && z.mm === "00" && Date.now() - this._since > 3600000) this._reload();
      this._clockT = setTimeout(() => this._clock(), 60500 - d.getSeconds() * 1000 - d.getMilliseconds());
    }
    async _reload() {
      // only when Home Assistant answers (otherwise an error page would stay)
      try { if ((await fetch(`/manifest.json?p=${Date.now()}`, { cache: "no-store" })).ok) location.reload(); } catch (e) { /* later */ }
    }

    /* ---------- weather ---------- */
    _weatherSub() {
      if (this._fc) { this._fc.then((u) => u && u()).catch(() => {}); this._fc = null; }
      this._forecast = null;
      if (!this._p || !this._p.weather) return;
      this._fc = this._hass.connection.subscribeMessage((m) => { this._forecast = m.forecast; this._showWeather(); },
        { type: "weather/subscribe_forecast", forecast_type: "daily", entity_id: this._p.weather }).catch(() => null);
      this._showWeather();
    }
    _showWeather() {
      const r = this._root; if (!r || !this._hass || !this._p || !this._p.weather) return;
      const s = this._hass.states[this._p.weather]; if (!s) return;
      const ic = r.querySelector(".weather ha-icon"), icon = WEATHER[s.state] || "mdi:weather-partly-cloudy";
      if (ic.getAttribute("icon") !== icon) ic.setAttribute("icon", icon);
      const t = s.attributes.temperature;
      r.querySelector(".temp").textContent = t != null ? `${Math.round(t)}°` : "";
      const f = this._forecast && this._forecast[0];
      r.querySelector(".hl").textContent = f && f.templow != null ? `${Math.round(f.temperature)}° / ${Math.round(f.templow)}°` : "";
    }

    /* ---------- events ---------- */
    async _loadEvents() {
      const p = this._p; if (!p || !p.calendars.length || !this._on) return;
      const from = new Date(), to = new Date(Date.now() + p.event_days * 86400000), all = [];
      let failed = 0;
      await Promise.all(p.calendars.map(async (id) => {
        try { (await this._hass.callApi("GET", `calendars/${id}?start=${from.toISOString()}&end=${to.toISOString()}`)).forEach((e) => all.push(e)); }
        catch (e) { failed++; }
      }));
      if (failed === p.calendars.length) { this._later(); return; } // HA is starting: keep the old list
      const start = (e) => (e.start.dateTime ? new Date(e.start.dateTime) : new Date(`${e.start.date}T00:00:00`));
      const end = (e) => (e.end.dateTime ? new Date(e.end.dateTime) : new Date(`${e.end.date}T00:00:00`));
      const now = new Date(), t = this._t;
      const list = all.filter((e) => end(e) > now).sort((a, b) => start(a) - start(b)).slice(0, p.events);
      const today = this._parts(now).day, tomorrow = this._parts(new Date(now.getTime() + 86400000)).day;
      const label = (day, d) => (day <= today ? t.today : day === tomorrow ? t.tomorrow : this._fmt(d, { weekday: "short" }));
      const box = this._root.querySelector(".events");
      box.innerHTML = list.length ? list.map((e) => {
        let day, time = "";
        if (e.start.dateTime) { const s = start(e) < now ? now : start(e), z = this._parts(start(e)); day = label(this._parts(s).day, s); time = `${z.hh}:${z.mm}`; }
        else day = label(e.start.date, new Date(`${e.start.date}T12:00:00Z`));
        return `<div class="e"><span class="d">${esc(day)}</span><span class="h">${time}</span><span class="n">${esc(e.summary)}</span></div>`;
      }).join("") : `<div class="e none">${esc(t.noEvents)}</div>`;
    }

    /* ---------- photos ---------- */
    _begin() { this._started = true; this._stack = []; this._stock = []; this._last = Date.now(); this._pump(); clearTimeout(this._tickT); this._tickT = setTimeout(() => this._tick(), this._tickTime()); }
    _restart() {
      // other album: clear the stock, the wall changes photo by photo
      this._gen++; this._pumping = null;
      this._stock.splice(0).forEach((f) => free(f.c));
      if (!this._started) this._begin(); else this._pump();
    }
    async _nextPhoto() {
      // ask the integration for the next photo, fetch and shrink it; every step has a time limit
      for (let tries = 0; tries < 4; tries++) {
        let r;
        try { r = await limit(this._hass.callWS({ type: "posterwall/next", entry_id: this._c.wall, count: 1, preview: !this._c.fullscreen || !!this._c.preview, client: this._client() }), 15000); }
        catch (e) { return null; }
        const ph = r.photos && r.photos[0]; if (!ph) return null;
        if (this._stack.some((o) => o._id === ph.id) && r.total > this._stack.length + 1) continue;
        try {
          const ab = new AbortController(), t = setTimeout(() => ab.abort(), 20000);
          let blob;
          try { const a = await fetch(ph.url, { signal: ab.signal }); if (!a.ok) throw new Error(a.status); blob = await a.blob(); }
          finally { clearTimeout(t); }
          // phone photos (12 MP) are shrunk while decoding: happens beside the page, no jank, little memory
          let bmp;
          try { bmp = await limit(createImageBitmap(blob, { resizeWidth: WIDTH, resizeQuality: "medium" }), 20000); }
          catch (e) { bmp = await limit(createImageBitmap(blob), 20000); }
          blob = null;
          const f = Math.min(1, WIDTH / bmp.width), c = document.createElement("canvas");
          c.width = Math.round(bmp.width * f); c.height = Math.round(bmp.height * f);
          c.getContext("2d").drawImage(bmp, 0, 0, c.width, c.height);
          bmp.close && bmp.close();
          return { id: ph.id, c, q: c.height / c.width, date: ph.date, ago: ph.years_ago };
        } catch (e) { /* next one */ }
      }
      return null;
    }
    _need() { return ((this._s && this._s.count) || 7) - this._stack.length + 1 - this._stock.length; }
    async _pump() {
      // loads ONE photo at a time and keeps one in stock: loads never pile up, whatever the settings
      const g = this._gen;
      if (this._pumping === g || this._sleeping) return;
      this._pumping = g;
      try {
        while (this._on && this._gen === g && !this._sleeping && this._need() > 0) {
          const f = await this._nextPhoto();
          if (!this._on || this._gen !== g) { if (f) free(f.c); break; }
          if (!f) { await wait(10000); continue; }
          this._stock.push(f);
          this._fill();
          await wait(300);
        }
      } finally { if (this._pumping === g) this._pumping = null; }
    }
    _fill() {
      // fill gaps (start, more photos) from stock, one after another
      const n = this._s.count;
      if (this._stack.length < n && this._stock.length && Date.now() - (this._lastPin || 0) > 900) this._pin(this._stock.shift());
      if (this._stack.length < n && this._stock.length) { clearTimeout(this._fillT); this._fillT = setTimeout(() => this._fill(), 1000); }
    }
    _tick() {
      if (!this._on || this._sleeping || !this._s) return;
      const n = this._s.count;
      if (this._stack.length > n) {
        for (let i = 0; i < 2 && this._stack.length > n; i++) this._leave(this._stack.shift()); // fewer photos: two at once
      } else if (this._stack.length === n) {
        // change only when the next photo is ready; otherwise wait a moment instead of leaving gaps
        if (!this._stock.length) { this._pump(); this._tickT = setTimeout(() => this._tick(), 1000); return; }
        this._leave(this._stack.shift());
        this._pin(this._stock.shift());
      }
      this._pump();
      this._tickT = setTimeout(() => this._tick(), this._tickTime());
    }
    _alive() {
      // a full-screen page tells the integration it runs fine; when it stops, the integration loads it again
      if (!this._c.fullscreen || this._c.preview || !this._hass) return;
      this._hass.callWS({ type: "posterwall/alive", entry_id: this._c.wall, client: this._client() }).catch(() => {});
    }
    _client() { if (!this._cid) this._cid = Math.random().toString(36).slice(2, 12); return this._cid; }
    _guard() {
      // no new photo for too long: restart loading and ticking (the photos stay);
      // after three tries reload a full-screen page (at most once an hour)
      if (!this._on || !this._p) return;
      const max = Math.max(4 * this._tickTime(), 120000);
      if (this._sleeping || (this._started && Date.now() - this._last < max)) this._alive();
      if (!this._started || this._sleeping || !this._p.photos) return;
      if (Date.now() - this._last < max) return;
      console.warn("PosterWall: no new photos, restarting");
      this._last = Date.now() - max / 2;
      if (++this._soft >= 3 && this._c.fullscreen && !this._c.preview) {
        this._soft = 0;
        let z = 0; try { z = +sessionStorage.getItem("posterwall-reload") || 0; } catch (e) { /* ok */ }
        if (Date.now() - z > 3600000) { try { sessionStorage.setItem("posterwall-reload", Date.now()); } catch (e) { /* ok */ } this._reload(); }
      }
      this._gen++; this._pumping = null;
      clearTimeout(this._tickT); clearTimeout(this._fillT);
      this._pump();
      this._tickT = setTimeout(() => this._tick(), this._tickTime());
    }
    _place(wPx, hPx) {
      // the spot farthest from the photos on the wall (overlap allowed, edges may stick out a little)
      const W = this._wall.clientWidth, H = this._wall.clientHeight;
      const zones = [".clock", ".info"].map((s) => this._root.querySelector(s)).filter((z) => z && z.style.display !== "none").map((z) => {
        const b = z.getBoundingClientRect(), o = this._wall.getBoundingClientRect();
        return [(b.left - o.left) / W * 100 - 4, (b.top - o.top) / H * 100 - 4, (b.right - o.left) / W * 100 + 4, (b.bottom - o.top) / H * 100 + 4];
      });
      const freeSpot = (x, y) => !zones.some((z) => x > z[0] && y > z[1] && x < z[2] && y < z[3]);
      let best = null, bestD = -1;
      for (let k = 0; k < 24; k++) {
        const cx = rand(10, 90), cy = rand(12, 88);
        if (!freeSpot(cx, cy)) continue;
        let d = 1e9;
        this._stack.forEach((o) => { d = Math.min(d, Math.hypot(o._cx - cx, (o._cy - cy) * H / W)); });
        if (d > bestD) { bestD = d; best = { cx, cy }; }
      }
      best = best || { cx: 50, cy: 50 };
      const x = Math.min(Math.max(best.cx / 100 * W - wPx / 2, -W * 0.04), W - wPx + W * 0.04);
      const y = Math.min(Math.max(best.cy / 100 * H - hPx / 2, -H * 0.05), H - hPx + H * 0.05);
      return { x, y, cx: best.cx, cy: best.cy };
    }
    _caption(f) {
      if (f.ago) return this._t.ago(f.ago);
      if (!f.date) return "";
      if (f.date.length === 4) return f.date;
      return this._fmt(new Date(`${f.date}T12:00:00Z`), { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
    }
    _pin(f) {
      if (!this._on || !f) return;
      const W = this._wall.clientWidth, H = this._wall.clientHeight, portrait = H > W;
      const g = SIZE[this._s.size] || SIZE.medium;
      let wPx = (portrait ? H * 0.62 : W) * rand(g[0], g[1]);
      const hMax = H * 0.64;
      if (wPx * 0.88 * f.q > hMax) wPx = hMax / (0.88 * f.q);
      const hPx = wPx * 0.88 * f.q + wPx * 0.21;
      const o = this._place(wPx, hPx);
      const el = document.createElement("div");
      const caption = this._caption(f);
      el.className = "poster" + (Math.random() < 0.45 ? " tape" : "") + ((this._s.caption && caption) || f.ago ? " cap" : "") + (f.ago ? " ago" : "");
      const rot = rand(-11, 11).toFixed(1);
      // every new photo lies below all others
      el.style.cssText = `left:${o.x}px;top:${o.y}px;width:${wPx}px;z-index:${--this._z};--r:${rot}deg;--pin:hsl(${Math.round(rand(0, 360))} 75% 52%)`;
      el.innerHTML = `<div class="paper"><i class="pin"></i><div class="txt">${esc(caption)}</div></div>`;
      el.firstChild.prepend(f.c);
      el._cx = o.cx; el._cy = o.cy; el._id = f.id; el._ago = f.ago;
      const fx = this._s.effect === "random" ? EFFECTS[Math.floor(Math.random() * EFFECTS.length)] : this._s.effect;
      el.dataset.fx = fx;
      this._stack.push(el);
      this._photos.appendChild(el);
      this._last = this._lastPin = Date.now(); this._soft = 0;
      this._message("");
      requestAnimationFrame(() => requestAnimationFrame(() => el.classList.add("in")));
    }
    _leave(el) {
      el.style.setProperty("--fr", `${rand(6, 14) * (Math.random() < 0.5 ? -1 : 1)}deg`);
      el.style.setProperty("--dx", `${(Math.random() < 0.5 ? -1 : 1) * rand(45, 70)}vw`);
      el.classList.add("out");
      setTimeout(() => { free(el.querySelector("canvas")); el.remove(); }, 1100);
    }
  }

  const CSS = `
  :host { display:block; }
  .frame { position:relative; width:100%; overflow:hidden; border-radius:var(--ha-card-border-radius, 12px); container-type:size; contain:layout paint; }
  .frame.full { position:fixed; inset:0; z-index:2147483000; border-radius:0; aspect-ratio:auto; }
  .wall { position:absolute; inset:0; overflow:hidden; color:#fff; font-family:var(--ha-font-family-body, system-ui, sans-serif);
    font-size:clamp(7px, min(1.25cqw, 2cqh), 34px); }
  .wall, .wall[data-bg="cork"] { background:
      radial-gradient(ellipse at 30% 20%, rgba(255,255,255,.07), transparent 60%),
      radial-gradient(circle at 70% 80%, rgba(0,0,0,.35), transparent 55%),
      linear-gradient(160deg, #6b4a2e, #4a3220 60%, #3a2718); }
  .wall[data-bg="wood"] { background:
      repeating-linear-gradient(92deg, rgba(0,0,0,.06) 0 2px, transparent 2px 9px, rgba(255,255,255,.03) 9px 11px, transparent 11px 23px),
      linear-gradient(180deg, rgba(0,0,0,.18), transparent 30%, rgba(0,0,0,.25)),
      linear-gradient(95deg, #8a5a33, #a06a3c 30%, #7c4f2c 55%, #95633a 80%, #6f4627); }
  .wall[data-bg="slate"] { background:
      radial-gradient(ellipse at 25% 15%, rgba(255,255,255,.08), transparent 55%),
      radial-gradient(circle at 80% 90%, rgba(0,0,0,.4), transparent 60%),
      linear-gradient(160deg, #3d4650, #2a3139 60%, #1e2329); }
  .wall[data-bg="black"] { background:#000; }
  .photos { position:absolute; inset:0; }
  .wall[data-night="clock"] .photos, .wall[data-night="clock"] .info, .wall[data-night="clock"] .msg, .wall[data-night="dark"] > * { display:none !important; }
  .wall[data-night="clock"], .wall[data-night="dark"] { background:#000; }
  .wall[data-night="clock"] .clock { display:block !important; right:auto; top:50%; left:50%; transform:translate(-50%,-50%); text-align:center; opacity:.55; }
  .wall[data-night="clock"] .time { font-size:9em; font-weight:300; }
  .wall[data-night="clock"] .date { font-size:1.6em; }
  .night { position:absolute; inset:0; background:#000; opacity:0; pointer-events:none; z-index:100001; transition:opacity 2s; }
  .wall:not([data-night="dim"]) .night { opacity:0 !important; }
  /* a new photo fades in, the old one leaves (only opacity/transform: smoothest when streamed) */
  .poster { position:absolute; transform:rotate(var(--r)); opacity:0; transition:opacity 1.6s ease; will-change:opacity; }
  .poster[data-fx="flip"] { transform:perspective(60em) rotate(var(--r)) rotateY(-80deg); transition:opacity 1.2s ease, transform 1.2s ease; }
  .poster.in { opacity:1; }
  .poster[data-fx="flip"].in { transform:perspective(60em) rotate(var(--r)) rotateY(0deg); }
  .poster.out { transition:opacity .9s ease-in, transform .9s cubic-bezier(.5,0,.9,.6); opacity:0; will-change:opacity, transform; }
  .poster[data-fx="drop"].out { transform:translateY(18cqh) rotate(calc(var(--r) + var(--fr))); }
  .poster[data-fx="fade"].out { transition:opacity 1.4s ease; transform:rotate(var(--r)) scale(.97); }
  .poster[data-fx="blow"].out { transition:opacity 1s ease-in, transform 1s cubic-bezier(.4,0,.8,.5); transform:translate(var(--dx), -6cqh) rotate(calc(var(--r) + var(--fr) * 3)); }
  .poster[data-fx="flip"].out { transition:opacity .8s ease-in, transform .8s ease-in; transform:perspective(60em) rotate(var(--r)) rotateY(88deg); }
  .poster.resize { transition:opacity 1.6s ease, width .8s ease; }
  .paper { position:relative; background:#fbfaf6; padding:6% 6% 15% 6%; border-radius:2px; box-shadow:0 2px 3px rgba(0,0,0,.35), 0 10px 22px rgba(0,0,0,.4); }
  .paper canvas { display:block; width:100%; height:auto; border-radius:1px; }
  .txt { position:absolute; left:6%; right:6%; bottom:2.2%; height:10%; display:none; align-items:center; justify-content:center; color:#4a3f35;
    font-family:"Segoe Print","Bradley Hand","Comic Sans MS",cursive; font-size:max(.7em, 1.05cqw); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .cap .txt { display:flex; }
  .ago .txt { color:#a0522d; font-weight:600; }
  .pin { position:absolute; left:50%; top:-.6em; width:1.25em; height:1.25em; margin-left:-.625em; border-radius:50%;
    background:radial-gradient(circle at 35% 30%, rgba(255,255,255,.85), var(--pin) 38%, rgba(0,0,0,.55) 100%); box-shadow:.12em .25em .25em rgba(0,0,0,.45); }
  .tape .pin { width:5.6em; height:1.6em; margin-left:-2.8em; top:-.85em; border-radius:2px; transform:rotate(-3deg);
    background:linear-gradient(90deg, rgba(255,255,240,.55), rgba(255,250,220,.7), rgba(255,255,240,.55)); box-shadow:0 1px 2px rgba(0,0,0,.2); }
  .clock { position:absolute; right:2.2%; top:3%; text-align:right; z-index:100000; text-shadow:0 .12em .5em rgba(0,0,0,.6); }
  .time { font-size:3.4em; font-weight:600; line-height:1; letter-spacing:.02em; font-variant-numeric:tabular-nums; }
  .date { font-size:1.05em; opacity:.9; margin-top:.3em; }
  .info { position:absolute; right:2%; bottom:3%; width:clamp(15.5em, 21%, 22em); z-index:100000; padding:.9em 1em; border-radius:1em;
    background:rgba(20,16,12,.72); box-shadow:0 .5em 1.5em rgba(0,0,0,.4); border:1px solid rgba(255,255,255,.08); }
  .weather { display:flex; align-items:center; gap:.55em; }
  .weather ha-icon { --mdc-icon-size:2.1em; color:#ffd54f; }
  .temp { font-size:1.9em; font-weight:600; }
  .hl { margin-left:auto; font-size:.95em; opacity:.8; }
  .events { margin-top:.6em; border-top:1px solid rgba(255,255,255,.12); padding-top:.5em; }
  .info.only .events { margin-top:0; border-top:0; padding-top:0; }
  .e { display:grid; grid-template-columns:3.6em 2.9em 1fr; gap:.25em; font-size:.92em; line-height:1.35; padding:.16em 0; }
  .e.none { display:block; opacity:.7; }
  .d { color:#ffd54f; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .h { opacity:.8; font-variant-numeric:tabular-nums; }
  .n { white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .msg { position:absolute; left:5%; right:28%; top:44%; text-align:center; opacity:.75; font-size:1.2em; }
  `;

  /* ---------- card editor ---------- */
  class PosterWallCardEditor extends HTMLElement {
    setConfig(c) { this._c = Object.assign({ wall: "", fullscreen: false, aspect_ratio: "16:9" }, c); this._draw(); }
    set hass(h) {
      const first = !this._hass; this._hass = h;
      if (first) h.callWS({ type: "posterwall/walls" }).then((w) => { this._walls = w; this._draw(); }).catch(() => { this._walls = []; this._draw(); });
    }
    _t() { const l = ((this._hass && (this._hass.locale?.language || this._hass.language)) || "en").slice(0, 2); return T[l] || T.en; }
    _draw() {
      if (!this._c || !this._hass) return;
      const t = this._t(), w = this._walls || [];
      this.innerHTML = `<style>
        .pw-ed{display:grid;gap:14px;padding:4px 0}.pw-ed label{display:grid;gap:6px;font-size:14px}
        .pw-ed select{font:inherit;padding:10px;border-radius:8px;border:1px solid var(--divider-color);background:var(--card-background-color);color:var(--primary-text-color)}
        .pw-ed .row{display:flex;align-items:center;gap:10px}.pw-ed .hint{font-size:13px;color:var(--secondary-text-color)}
        .pw-ed a{color:var(--primary-color)}</style>
        <div class="pw-ed">
          ${w.length ? `<label>${t.wall}<select data-k="wall">${w.map((x) => `<option value="${esc(x.entry_id)}" ${x.entry_id === this._c.wall ? "selected" : ""}>${esc(x.title)}</option>`).join("")}</select></label>`
            : `<div class="hint">${esc(t.noWalls)}</div>`}
          <label class="row"><input type="checkbox" data-k="fullscreen" ${this._c.fullscreen ? "checked" : ""}> ${esc(t.fullscreen)}</label>
          ${this._c.fullscreen ? "" : `<label>${t.ratio}<select data-k="aspect_ratio">${RATIOS.map((r) => `<option ${r === this._c.aspect_ratio ? "selected" : ""}>${r}</option>`).join("")}</select></label>`}
          <div class="hint">${esc(t.more)} <a href="/posterwall">PosterWall →</a></div>
        </div>`;
      if (w.length && !w.some((x) => x.entry_id === this._c.wall)) this._set("wall", w[0].entry_id);
      this.querySelectorAll("[data-k]").forEach((el) => el.addEventListener("change", () => this._set(el.dataset.k, el.type === "checkbox" ? el.checked : el.value)));
    }
    _set(k, v) {
      this._c = { ...this._c, [k]: v };
      this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: this._c }, bubbles: true, composed: true }));
      if (k === "fullscreen") this._draw();
    }
  }

  customElements.get("posterwall-card") || customElements.define("posterwall-card", PosterWallCard);
  customElements.get("posterwall-card-editor") || customElements.define("posterwall-card-editor", PosterWallCardEditor);
  window.customCards = window.customCards || [];
  if (!window.customCards.some((c) => c.type === "posterwall-card")) {
    window.customCards.push({ type: "posterwall-card", name: "PosterWall", description: "Your photos pinned like on a pinboard – with clock, weather and events", preview: true,
      documentationURL: "https://github.com/Wadim-dev/PosterWall_ha" });
  }
  console.info(`%c POSTERWALL %c v${VERSION} `, "background:#6b4a2e;color:#fff", "");
})();
