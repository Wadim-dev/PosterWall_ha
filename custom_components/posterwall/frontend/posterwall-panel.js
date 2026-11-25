// PosterWall – sidebar panel: live preview, every setting of a wall and the screens of the house.
// The display page of each wall (a dashboard "posterwall-<id>") is created here automatically and removed
// again when its wall is deleted. No polling: the wall pushes every change over the websocket.
const VERSION = "1.0.1";
const REPO = "https://github.com/Wadim-dev/PosterWall_ha";

const TX = {
  en: {
    title: "PosterWall", add: "New wall", welcome: "Your photos, pinned to every screen",
    welcomeText: "PosterWall turns any screen into a pinboard of your photos – with clock, weather and events. Set up in three steps:",
    step1: "Choose where your photos are: a folder in Home Assistant, Immich or Synology Photos.",
    step2: "Look at the live preview and set it up the way you like.",
    step3: "Tap “Show” next to a screen – done.",
    start: "Set up the first wall", preview: "Live preview", photos: "Photos", look: "Look", info: "Clock, weather & events", night: "Night",
    screens: "Screens", source: "Source", album: "Album", interval: "Change every", count: "Photos on the wall", size: "Photo size",
    favorites: "Show favourites more often", onThisDay: "“On this day” – photos from this day in earlier years now and then",
    caption: "Date under every photo", effect: "Effect", background: "Background", clock: "Clock", weather: "Weather", events: "Events",
    weatherEntity: "Weather from", calendars: "Calendars", eventCount: "Number of events", eventDays: "Events of the next",
    days: "days", nightMode: "At night", nightFrom: "from", nightTo: "until", brightness: "Brightness",
    reread: "Read again", reading: "Reading photos …", photosFound: (n) => `${n.toLocaleString()} photos`, sec: "s",
    sizes: { small: "Small", medium: "Medium", large: "Large" },
    effects: { drop: "Drop", fade: "Fade", blow: "Blow away", flip: "Flip", random: "Random" },
    backgrounds: { cork: "Cork", wood: "Wood", slate: "Slate", black: "Black" },
    nights: { off: "Normal", dim: "Dimmed", clock: "Clock only", dark: "Dark" },
    sources: { media: "Home Assistant media", immich: "Immich", synology: "Synology Photos" },
    change: "Change", show: "Show", showing: "Shows", keep: "Always", keepHint: "Starts the wall again when the screen has nothing else to do – never interrupts music or videos.",
    page: "Display page", pageReady: "ready", pageMaking: "is being created …", openPage: "Open", copy: "Copy link", copied: "Link copied",
    linkHint: "Any other screen (a TV browser, an old tablet, a streamed Echo Show) simply opens this link.",
    noScreens: "No screen found yet.", installHint: "Screens appear here by themselves as soon as one of these integrations is set up:",
    castHttps: "Google Cast needs Home Assistant reachable over HTTPS (Home Assistant Cloud or an external URL with a certificate).",
    kinds: { cast: "Google Cast", fully_kiosk: "Fully Kiosk", browser_mod: "Browser Mod", techo5: "Echo Show · TECHO5" },
    sent: (n) => `Shown on ${n}`, failed: "Could not show:", empty: "No photos in this folder or album.",
    noWeather: "– none –", formats: "Screen format", wallSettings: "Wall settings", remove: "Delete or rename the wall",
    on: "On", off: "Off", notLoaded: "This wall could not start:", allPhotos: "All photos", favs: "Favourites", portrait: "Portrait · 9:16",
    folder: "Folder", chooseFolder: "Choose folder", useFolder: "Show this folder", close: "Close", showingNow: "shown now",
    inFolder: (p, f) => `${p.toLocaleString()} photos here · ${f} folders`, subAlways: "Photos in sub folders are always included.",
    outside: "This folder is outside the wall's folder – it becomes the wall's new folder.", folderSet: "Folder is being read …",
  },
  de: {
    title: "PosterWall", add: "Neue Wand", welcome: "Deine Fotos an jedem Bildschirm",
    welcomeText: "PosterWall macht jeden Bildschirm zur Pinnwand deiner Fotos – mit Uhr, Wetter und Terminen. Eingerichtet in drei Schritten:",
    step1: "Wähle, wo deine Fotos liegen: ein Ordner in Home Assistant, Immich oder Synology Photos.",
    step2: "Schau in die Live-Vorschau und stell alles nach deinem Geschmack ein.",
    step3: "Tippe neben einem Bildschirm auf „Anzeigen“ – fertig.",
    start: "Erste Wand einrichten", preview: "Live-Vorschau", photos: "Fotos", look: "Aussehen", info: "Uhr, Wetter & Termine", night: "Nacht",
    screens: "Bildschirme", source: "Quelle", album: "Album", interval: "Wechsel alle", count: "Fotos an der Wand", size: "Fotogröße",
    favorites: "Favoriten öfter zeigen", onThisDay: "„An diesem Tag“ – ab und zu Fotos von heute aus früheren Jahren",
    caption: "Datum unter jedem Foto", effect: "Effekt", background: "Hintergrund", clock: "Uhr", weather: "Wetter", events: "Termine",
    weatherEntity: "Wetter von", calendars: "Kalender", eventCount: "Anzahl Termine", eventDays: "Termine der nächsten",
    days: "Tage", nightMode: "Nachts", nightFrom: "von", nightTo: "bis", brightness: "Helligkeit",
    reread: "Neu einlesen", reading: "Fotos werden eingelesen …", photosFound: (n) => `${n.toLocaleString("de-DE")} Fotos`, sec: "s",
    sizes: { small: "Klein", medium: "Mittel", large: "Groß" },
    effects: { drop: "Abfallen", fade: "Überblenden", blow: "Wegwehen", flip: "Umdrehen", random: "Zufall" },
    backgrounds: { cork: "Kork", wood: "Holz", slate: "Schiefer", black: "Schwarz" },
    nights: { off: "Normal", dim: "Abgedunkelt", clock: "Nur Uhr", dark: "Dunkel" },
    sources: { media: "Home-Assistant-Medien", immich: "Immich", synology: "Synology Photos" },
    change: "Ändern", show: "Anzeigen", showing: "Zeigt", keep: "Dauerhaft", keepHint: "Startet die Wand neu, wenn auf dem Bildschirm nichts anderes läuft – unterbricht nie Musik oder Videos.",
    page: "Anzeige-Seite", pageReady: "bereit", pageMaking: "wird angelegt …", openPage: "Öffnen", copy: "Link kopieren", copied: "Link kopiert",
    linkHint: "Jeder andere Bildschirm (Browser am Fernseher, altes Tablet, gestreamte Echo Show) öffnet einfach diesen Link.",
    noScreens: "Noch kein Bildschirm gefunden.", installHint: "Bildschirme erscheinen hier von selbst, sobald eine dieser Integrationen eingerichtet ist:",
    castHttps: "Google Cast braucht Home Assistant über HTTPS erreichbar (Home Assistant Cloud oder externe Adresse mit Zertifikat).",
    kinds: { cast: "Google Cast", fully_kiosk: "Fully Kiosk", browser_mod: "Browser Mod", techo5: "Echo Show · TECHO5" },
    sent: (n) => `Wird auf ${n} gezeigt`, failed: "Anzeigen ging nicht:", empty: "In diesem Ordner oder Album sind keine Fotos.",
    noWeather: "– keins –", formats: "Bildschirmformat", wallSettings: "Wand-Einstellungen", remove: "Wand löschen oder umbenennen",
    on: "An", off: "Aus", notLoaded: "Diese Wand konnte nicht starten:", allPhotos: "Alle Fotos", favs: "Favoriten", portrait: "Hochkant · 9:16",
    folder: "Ordner", chooseFolder: "Ordner wählen", useFolder: "Diesen Ordner zeigen", close: "Schließen", showingNow: "wird gezeigt",
    inFolder: (p, f) => `${p.toLocaleString("de-DE")} Fotos hier · ${f} Ordner`, subAlways: "Fotos in Unterordnern sind immer dabei.",
    outside: "Dieser Ordner liegt außerhalb des Wand-Ordners – er wird der neue Ordner der Wand.", folderSet: "Ordner wird eingelesen …",
  },
};
const FORMATS = [["16:9", "TV · 16:9"], ["16:10", "Tablet · 16:10"], ["1024:600", "Nest Hub · 17:10"], ["4:3", "iPad · 4:3"], ["9:16", "portrait"]];
const KIND_ICON = { cast: "mdi:cast", fully_kiosk: "mdi:tablet-dashboard", browser_mod: "mdi:web", techo5: "mdi:tablet" };
const INSTALL = [["cast", "https://www.home-assistant.io/integrations/cast/"], ["fully_kiosk", "https://www.home-assistant.io/integrations/fully_kiosk/"],
  ["browser_mod", "https://github.com/thomasloven/hass-browser_mod"]];
const SWATCH = {
  cork: "linear-gradient(160deg,#6b4a2e,#4a3220 60%,#3a2718)", wood: "linear-gradient(95deg,#8a5a33,#a06a3c 30%,#7c4f2c 55%,#95633a 80%,#6f4627)",
  slate: "linear-gradient(160deg,#3d4650,#2a3139 60%,#1e2329)", black: "#000",
};
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const CSS = `
:host{display:block;min-height:100vh;background:var(--primary-background-color);color:var(--primary-text-color);font-family:var(--ha-font-family-body,Roboto,sans-serif)}
.top{position:sticky;top:0;z-index:3;display:flex;align-items:center;gap:6px;height:var(--header-height,56px);padding:0 12px 0 4px;
  background:var(--app-header-background-color,var(--primary-color));color:var(--app-header-text-color,#fff);border-bottom:var(--app-header-border-bottom,none)}
.top h1{font-size:20px;font-weight:400;margin:0 8px 0 4px;white-space:nowrap}
.top .menu{width:40px;height:40px;border:0;background:none;color:inherit;border-radius:50%;cursor:pointer;display:flex;align-items:center;justify-content:center}
.walls{display:flex;gap:6px;overflow-x:auto;flex:1;scrollbar-width:none;padding:4px 0}
.walls::-webkit-scrollbar{display:none}
.chip{display:inline-flex;align-items:center;gap:6px;padding:6px 14px;border-radius:18px;border:1px solid rgba(255,255,255,.35);color:inherit;background:none;
  font:inherit;font-size:14px;white-space:nowrap;cursor:pointer}
.chip.on{background:rgba(255,255,255,.22);border-color:transparent}
.chip ha-icon{--mdc-icon-size:18px}
main{max-width:1280px;margin:0 auto;padding:16px;display:grid;grid-template-columns:minmax(0,1.25fr) minmax(0,1fr);gap:16px;align-items:start}
main.narrow{grid-template-columns:1fr;padding:10px}
.left{position:sticky;top:calc(var(--header-height,56px) + 16px);display:grid;gap:12px}
main.narrow .left{position:static}
.card{background:var(--ha-card-background,var(--card-background-color,#fff));border-radius:var(--ha-card-border-radius,12px);
  box-shadow:var(--ha-card-box-shadow,none);border:1px solid var(--divider-color);padding:16px}
.card h2{display:flex;align-items:center;gap:8px;margin:0 0 14px;font-size:17px;font-weight:500}
.card h2 ha-icon{color:var(--primary-color);--mdc-icon-size:22px}
.card h2 .grow{flex:1}
.right{display:grid;gap:12px}
.pv{position:relative}
.pv .stage{display:flex;justify-content:center;background:repeating-conic-gradient(rgba(127,127,127,.06) 0 25%,transparent 0 50%) 0 0/20px 20px;border-radius:12px;padding:10px}
.pv posterwall-card{display:block;width:100%;max-height:70vh;box-shadow:0 10px 30px rgba(0,0,0,.35);border-radius:12px}
.pv .bezel{width:100%;border-radius:14px;padding:8px;background:#111;box-sizing:border-box}
.pv.tall .bezel{width:auto;height:min(70vh,640px);aspect-ratio:9/16}
.formats{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.seg{display:flex;flex-wrap:wrap;gap:6px}
.seg button,.formats button{font:inherit;font-size:13px;padding:7px 12px;border-radius:18px;border:1px solid var(--divider-color);background:none;
  color:var(--primary-text-color);cursor:pointer}
.seg button.on,.formats button.on{background:var(--primary-color);border-color:var(--primary-color);color:var(--text-primary-color,#fff)}
.row{display:flex;align-items:center;gap:12px;min-height:44px;padding:4px 0;border-top:1px solid var(--divider-color)}
.row:first-of-type{border-top:0}
.row .lab{flex:1;font-size:14px}
.row .lab small{display:block;color:var(--secondary-text-color);font-size:12px;margin-top:2px}
.row.col{flex-direction:column;align-items:stretch;gap:8px;padding:10px 0}
.row.col .lab{flex:none}
.val{min-width:52px;text-align:right;font-variant-numeric:tabular-nums;color:var(--secondary-text-color);font-size:14px}
input[type=range]{flex:1;accent-color:var(--primary-color);min-width:120px}
select,input[type=time],input[type=number]{font:inherit;font-size:14px;padding:8px 10px;border-radius:8px;border:1px solid var(--divider-color);
  background:var(--card-background-color);color:var(--primary-text-color);max-width:100%}
.sw{position:relative;width:40px;height:22px;flex:none}
.sw input{opacity:0;width:0;height:0}
.sw span{position:absolute;inset:0;border-radius:11px;background:var(--switch-unchecked-track-color,#9e9e9e);opacity:.6;cursor:pointer;transition:.2s}
.sw span:before{content:"";position:absolute;width:18px;height:18px;left:2px;top:2px;border-radius:50%;background:#fff;transition:.2s;box-shadow:0 1px 3px rgba(0,0,0,.4)}
.sw input:checked+span{background:var(--switch-checked-track-color,var(--primary-color));opacity:1}
.sw input:checked+span:before{transform:translateX(18px)}
.swatches{display:flex;gap:10px;flex-wrap:wrap}
.swatch{width:64px;cursor:pointer;text-align:center;font-size:12px;color:var(--secondary-text-color);background:none;border:0;padding:0;font-family:inherit}
.swatch i{display:block;height:42px;border-radius:10px;border:2px solid transparent;margin-bottom:4px;box-shadow:inset 0 0 0 1px rgba(255,255,255,.1)}
.swatch.on i{border-color:var(--primary-color)}
.swatch.on{color:var(--primary-text-color)}
.cals{display:grid;gap:4px;max-height:180px;overflow:auto}
.cals label{display:flex;align-items:center;gap:8px;font-size:14px}
.btn{text-decoration:none;font:inherit;font-size:14px;font-weight:500;display:inline-flex;align-items:center;gap:6px;padding:8px 14px;border-radius:18px;border:0;
  background:var(--primary-color);color:var(--text-primary-color,#fff);cursor:pointer;white-space:nowrap}
.btn.flat{background:rgba(var(--rgb-primary-color,3,169,244),.12);color:var(--primary-color)}
.btn:disabled{opacity:.5;cursor:default}
.btn ha-icon{--mdc-icon-size:18px}
.muted{color:var(--secondary-text-color);font-size:13px}
.note{font-size:13px;padding:10px 12px;border-radius:10px;background:rgba(var(--rgb-warning-color,255,152,0),.14);margin:8px 0}
.note.err{background:rgba(var(--rgb-error-color,219,68,55),.14)}
.screen{display:flex;align-items:center;gap:12px;padding:10px 0;border-top:1px solid var(--divider-color)}
.screen:first-child{border-top:0}
.screen .ic{width:40px;height:40px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:rgba(var(--rgb-primary-color,3,169,244),.12);color:var(--primary-color);flex:none}
.screen .nm{flex:1;min-width:0}
.screen .nm b{font-weight:500;display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.screen .keep{display:flex;align-items:center;gap:6px;font-size:12px;color:var(--secondary-text-color)}
.link{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:10px}
.link code{flex:1;min-width:0;font-size:12px;padding:8px 10px;border-radius:8px;background:rgba(127,127,127,.12);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.welcome{grid-column:1/-1;max-width:760px;margin:24px auto;text-align:center}
.welcome h2{justify-content:center;font-size:26px;font-weight:400}
.welcome ol{text-align:left;display:grid;gap:10px;margin:18px auto 24px;max-width:560px;padding-left:22px}
.logo{width:72px;height:72px;margin:0 auto 6px;display:block}
.toast{position:fixed;left:50%;bottom:24px;transform:translateX(-50%);background:#323232;color:#fff;padding:12px 18px;border-radius:8px;z-index:9;font-size:14px;
  box-shadow:0 4px 14px rgba(0,0,0,.4);max-width:90vw}
.fb{margin:6px 0 10px;border:1px solid var(--divider-color);border-radius:12px;overflow:hidden}
.fb .crumbs{display:flex;flex-wrap:wrap;gap:2px;align-items:center;padding:8px 10px;background:rgba(127,127,127,.08);font-size:13px}
.fb .crumbs button{font:inherit;border:0;background:none;color:var(--primary-color);cursor:pointer;padding:4px 6px;border-radius:6px}
.fb .crumbs button:last-child{color:var(--primary-text-color);font-weight:500;cursor:default}
.fb .crumbs span{color:var(--secondary-text-color)}
.fb .list{max-height:320px;overflow:auto}
.fb .list button{display:flex;align-items:center;gap:10px;width:100%;font:inherit;font-size:14px;text-align:left;padding:10px 12px;border:0;
  border-top:1px solid var(--divider-color);background:none;color:var(--primary-text-color);cursor:pointer}
.fb .list button:first-child{border-top:0}
.fb .list button:hover{background:rgba(127,127,127,.08)}
.fb .list ha-icon{color:var(--primary-color);--mdc-icon-size:20px;flex:none}
.fb .list .on{margin-left:auto;font-size:12px;color:var(--primary-color)}
.fb .foot2{display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:10px 12px;border-top:1px solid var(--divider-color)}
.fb .foot2 .muted{flex:1;min-width:160px}
.path{font-size:13px;color:var(--secondary-text-color);overflow-wrap:anywhere}
.foot{grid-column:1/-1;text-align:center;font-size:12px;color:var(--secondary-text-color);padding:8px 0 24px}
.foot a{color:inherit}
`;

// the card is a dashboard resource (created below); the panel loads it itself for the preview
const CARD = import(`/posterwall_static/posterwall-card.js?v=${VERSION}`).catch((e) => console.error("PosterWall: card could not be loaded", e));

class PosterWallPanel extends HTMLElement {
  set hass(h) {
    const first = !this._hass;
    this._hass = h;
    if (first) this._init();
  }
  get hass() { return this._hass; }
  set narrow(n) { this._narrow = n; if (this._main) this._main.classList.toggle("narrow", !!n || innerWidth < 900); }
  set route(r) { this._route = r; }
  set panel(p) { this._panel = p; }
  get _t() { const l = (this._hass.locale?.language || this._hass.language || "en").slice(0, 2); return TX[l] || TX.en; }

  connectedCallback() { if (this._hass && !this._on) this._init(); }
  disconnectedCallback() { this._on = false; this._unsub(); }

  async _init() {
    if (this._on) return;
    this._on = true;
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    try { this._format = localStorage.getItem("posterwall-format") || "16:9"; } catch (e) { this._format = "16:9"; }
    this.shadowRoot.innerHTML = `<style>${CSS}</style><div class="top"><button class="menu" title="Menu"><ha-icon icon="mdi:menu"></ha-icon></button>
      <h1>PosterWall</h1><div class="walls"></div></div><main></main>`;
    this._main = this.shadowRoot.querySelector("main");
    this._main.classList.toggle("narrow", !!this._narrow || innerWidth < 900);
    this.shadowRoot.querySelector(".menu").addEventListener("click", () => this.dispatchEvent(new Event("hass-toggle-menu", { bubbles: true, composed: true })));
    await this._loadWalls();
    this._loadScreens();
    this._pages();
  }
  async _loadWalls() {
    try { this._walls = await this._hass.callWS({ type: "posterwall/walls" }); } catch (e) { this._walls = []; }
    const want = new URLSearchParams(location.search).get("wall");
    const ids = this._walls.map((w) => w.entry_id);
    if (!ids.includes(this._sel)) this._sel = ids.includes(want) ? want : ids[0];
    this._chips();
    this._select(this._sel, true);
  }
  _chips() {
    const t = this._t, box = this.shadowRoot.querySelector(".walls");
    box.innerHTML = this._walls.map((w) => `<button class="chip ${w.entry_id === this._sel ? "on" : ""}" data-w="${esc(w.entry_id)}"><ha-icon icon="mdi:image-frame"></ha-icon>${esc(w.title)}</button>`).join("")
      + `<button class="chip" data-add="1"><ha-icon icon="mdi:plus"></ha-icon>${esc(t.add)}</button>`;
    box.querySelectorAll("[data-w]").forEach((b) => b.addEventListener("click", () => this._select(b.dataset.w)));
    box.querySelector("[data-add]").addEventListener("click", () => this._addWall());
  }
  _addWall() {
    history.pushState(null, "", "/config/integrations/dashboard/add?domain=posterwall");
    window.dispatchEvent(new CustomEvent("location-changed", { detail: { replace: false } }));
  }
  _go(path) { history.pushState(null, "", path); window.dispatchEvent(new CustomEvent("location-changed", { detail: { replace: false } })); }
  _unsub() { if (this._sub) { this._sub.then((u) => u && u()).catch(() => {}); this._sub = null; } }
  _select(id, force) {
    if (id === this._sel && !force && this._p) return;
    this._sel = id; this._p = null; this._fb = null; this._unsub();
    this._chips();
    if (id) { const u = new URL(location.href); u.searchParams.set("wall", id); history.replaceState(null, "", u); }
    this._layout();
    const w = this._walls.find((x) => x.entry_id === id);
    if (!w || w.state !== "loaded") return;
    this._sub = this._hass.connection.subscribeMessage((p) => { this._p = p; this._settings(); }, { type: "posterwall/subscribe", entry_id: id }).catch(() => null);
  }

  /* ---------- layout ---------- */
  _layout() {
    const t = this._t, m = this._main;
    if (!this._walls.length) {
      m.innerHTML = `<div class="welcome card"><svg class="logo" viewBox="0 0 120 120">${LOGO}</svg><h2>${esc(t.welcome)}</h2><p class="muted">${esc(t.welcomeText)}</p>
        <ol><li>${esc(t.step1)}</li><li>${esc(t.step2)}</li><li>${esc(t.step3)}</li></ol>
        <button class="btn" data-start><ha-icon icon="mdi:plus"></ha-icon>${esc(t.start)}</button></div>${this._foot()}`;
      m.querySelector("[data-start]").addEventListener("click", () => this._addWall());
      return;
    }
    const w = this._walls.find((x) => x.entry_id === this._sel);
    if (w && w.state !== "loaded") {
      m.innerHTML = `<div class="card" style="grid-column:1/-1"><div class="note err">${esc(t.notLoaded)} ${esc(w.error || w.state)}</div>
        <button class="btn flat" data-cfg><ha-icon icon="mdi:cog"></ha-icon>${esc(t.wallSettings)}</button></div>`;
      m.querySelector("[data-cfg]").addEventListener("click", () => this._go(`/config/integrations/integration/posterwall`));
      return;
    }
    m.innerHTML = `<div class="left"><div class="card pv"><h2><ha-icon icon="mdi:monitor-eye"></ha-icon><span class="grow">${esc(t.preview)}</span></h2>
        <div class="stage"><div class="bezel"></div></div>
        <div class="formats">${FORMATS.map(([k, l]) => `<button data-f="${k}">${esc(l === "portrait" ? t.portrait : l)}</button>`).join("")}</div></div>
        <div class="card screens"></div></div>
      <div class="right"></div>${this._foot()}`;
    this._preview();
    m.querySelectorAll("[data-f]").forEach((b) => b.addEventListener("click", () => {
      this._format = b.dataset.f; try { localStorage.setItem("posterwall-format", this._format); } catch (e) { /* ok */ }
      this._preview();
    }));
    this._screens();
  }
  _foot() { return `<div class="foot">PosterWall ${VERSION} · <a href="${REPO}" target="_blank" rel="noreferrer">GitHub</a></div>`; }
  _preview() {
    const pv = this._main.querySelector(".pv"); if (!pv) return;
    pv.classList.toggle("tall", this._format === "9:16");
    pv.querySelectorAll("[data-f]").forEach((b) => b.classList.toggle("on", b.dataset.f === this._format));
    const bezel = pv.querySelector(".bezel");
    let card = bezel.querySelector("posterwall-card");
    const conf = { type: "custom:posterwall-card", wall: this._sel, aspect_ratio: this._format, preview: true };
    if (!customElements.get("posterwall-card")) { CARD.then(() => customElements.get("posterwall-card") && this._preview()); return; }
    if (!card) { card = document.createElement("posterwall-card"); card.setConfig(conf); card.hass = this._hass; bezel.appendChild(card); }
    else card.setConfig(conf);
    this._card = card;
  }

  /* ---------- settings ---------- */
  _set(key, value) { return this._hass.callWS({ type: "posterwall/set", entry_id: this._sel, key, value }).catch((e) => this._toast(e.message)); }
  _opt(data) { return this._hass.callWS({ type: "posterwall/options", entry_id: this._sel, ...data }).catch((e) => this._toast(e.message)); }
  _sw(key, on, label, hint) {
    return `<div class="row"><div class="lab">${esc(label)}${hint ? `<small>${esc(hint)}</small>` : ""}</div>
      <label class="sw"><input type="checkbox" data-s="${key}" ${on ? "checked" : ""}><span></span></label></div>`;
  }
  _seg(key, value, labels) { return `<div class="seg">${Object.entries(labels).map(([k, l]) => `<button data-seg="${key}" data-v="${k}" class="${k === value ? "on" : ""}">${esc(l)}</button>`).join("")}</div>`; }
  _range(key, value, min, max, step, unit, label) {
    return `<div class="row"><div class="lab">${esc(label)}</div><input type="range" data-r="${key}" min="${min}" max="${max}" step="${step}" value="${value}">
      <span class="val" data-rv="${key}">${value}${unit}</span></div>`;
  }
  _settings() {
    const p = this._p, t = this._t, box = this._main.querySelector(".right");
    if (!p || !box) return;
    if (this._card) this._card.hass = this._hass;
    const s = p.settings, h = this._hass;
    const weathers = Object.keys(h.states).filter((e) => e.startsWith("weather.")).sort();
    const cals = Object.keys(h.states).filter((e) => e.startsWith("calendar.")).sort();
    const name = (e) => (h.states[e] && h.states[e].attributes.friendly_name) || e;
    const status = p.loading ? t.reading : p.error ? `⚠ ${p.error}` : t.photosFound(p.photos);
    box.innerHTML = `
      <div class="card"><h2><ha-icon icon="mdi:image-multiple"></ha-icon><span class="grow">${esc(t.photos)}</span>
          <button class="btn flat" data-reread ${p.loading ? "disabled" : ""}><ha-icon icon="mdi:folder-refresh"></ha-icon>${esc(t.reread)}</button></h2>
        <div class="row"><div class="lab">${esc(t.source)}<small>${esc(t.sources[p.source] || p.source)} · ${esc(status)}</small></div>
          <button class="btn flat" data-cfg>${esc(t.change)}</button></div>
        ${!p.loading && !p.error && !p.photos ? `<div class="note">${esc(t.empty)}</div>` : ""}
        ${p.source === "media" ? this._folderRow(p) : `<div class="row"><div class="lab">${esc(t.album)}</div><select data-sel="album">${p.albums.map((a) => `<option value="${esc(a.key)}" ${a.key === s.album ? "selected" : ""}>${esc(a.key === "all" ? t.allPhotos : a.key === "favorites" ? t.favs : a.title)}</option>`).join("")}</select></div>`}
        ${this._range("interval", s.interval, 5, 120, 1, ` ${t.sec}`, t.interval)}
        ${this._range("count", s.count, 1, 12, 1, "", t.count)}
        <div class="row"><div class="lab">${esc(t.size)}</div>${this._seg("size", s.size, t.sizes)}</div>
        ${p.source === "immich" ? this._sw("favorites", s.favorites, t.favorites) : ""}
        ${this._sw("on_this_day", s.on_this_day, t.onThisDay)}
        ${this._sw("caption", s.caption, t.caption)}
      </div>
      <div class="card"><h2><ha-icon icon="mdi:palette-outline"></ha-icon>${esc(t.look)}</h2>
        <div class="row col"><div class="lab">${esc(t.effect)}</div>${this._seg("effect", s.effect, t.effects)}</div>
        <div class="row col"><div class="lab">${esc(t.background)}</div><div class="swatches">${Object.entries(t.backgrounds).map(([k, l]) =>
          `<button class="swatch ${k === s.background ? "on" : ""}" data-seg="background" data-v="${k}"><i style="background:${SWATCH[k]}"></i>${esc(l)}</button>`).join("")}</div></div>
      </div>
      <div class="card"><h2><ha-icon icon="mdi:clock-outline"></ha-icon>${esc(t.info)}</h2>
        ${this._sw("clock", s.clock, t.clock)}
        ${this._sw("weather", s.weather, t.weather)}
        ${s.weather ? `<div class="row"><div class="lab">${esc(t.weatherEntity)}</div><select data-o="weather"><option value="">${esc(t.noWeather)}</option>
          ${weathers.map((e) => `<option value="${esc(e)}" ${e === p.weather ? "selected" : ""}>${esc(name(e))}</option>`).join("")}</select></div>` : ""}
        ${this._sw("events", s.events, t.events)}
        ${s.events ? `<div class="row col"><div class="lab">${esc(t.calendars)}</div><div class="cals">${cals.map((e) =>
          `<label><input type="checkbox" data-cal="${esc(e)}" ${p.calendars.includes(e) ? "checked" : ""}>${esc(name(e))}</label>`).join("")}</div></div>
          <div class="row"><div class="lab">${esc(t.eventCount)}</div><input type="number" min="1" max="10" data-o="events" value="${p.events}" style="width:70px"></div>
          <div class="row"><div class="lab">${esc(t.eventDays)}</div><input type="number" min="1" max="31" data-o="event_days" value="${p.event_days}" style="width:70px"><span class="muted">${esc(t.days)}</span></div>` : ""}
      </div>
      <div class="card"><h2><ha-icon icon="mdi:weather-night"></ha-icon>${esc(t.night)}</h2>
        <div class="row col"><div class="lab">${esc(t.nightMode)}</div>${this._seg("night_mode", s.night_mode, t.nights)}</div>
        ${s.night_mode !== "off" ? `<div class="row"><div class="lab">${esc(t.nightFrom)}</div><input type="time" data-time="night_start" value="${s.night_start.slice(0, 5)}">
          <span class="muted">${esc(t.nightTo)}</span><input type="time" data-time="night_end" value="${s.night_end.slice(0, 5)}"></div>` : ""}
        ${s.night_mode === "dim" ? this._range("night_brightness", s.night_brightness, 5, 90, 5, " %", t.brightness) : ""}
      </div>`;
    this._bind(box);
  }
  /* ---------- folders (Home Assistant media): click through the real folder tree ---------- */
  _folderRow(p) {
    const t = this._t, fb = this._fb, cur = p.albums.find((a) => a.key === p.settings.album);
    const shown = p.settings.album === "all" ? (p.folder_title || t.allPhotos) : [p.folder_title, cur && cur.title].filter(Boolean).join(" / ");
    let html = `<div class="row"><div class="lab">${esc(t.folder)}<small class="path">${esc(shown)}</small></div>
      <button class="btn flat" data-fb-open><ha-icon icon="mdi:folder-open"></ha-icon>${esc(fb ? t.close : t.chooseFolder)}</button></div>`;
    if (!fb) return html;
    if (!fb.data) return `${html}<div class="fb"><div class="crumbs"><span>${esc(fb.error || t.reading)}</span></div></div>`;
    const d = fb.data, here = d.folder;
    const inRoot = here.id === d.root || (here.id || "").startsWith(`${d.root.replace(/\/$/, "")}/`);
    html += `<div class="fb"><div class="crumbs">${d.chain.map((c, i) => `${i ? "<span>›</span>" : ""}<button data-fb="${esc(c.id ?? "")}">${esc(c.title)}</button>`).join("")}</div>
      <div class="list">${here.folders.map((f) => `<button data-fb="${esc(f.id)}"><ha-icon icon="mdi:folder"></ha-icon><span>${esc(f.title)}</span>${f.id === d.showing ? `<span class="on">${esc(t.showingNow)}</span>` : ""}</button>`).join("")}</div>
      ${here.id ? `<div class="foot2"><span class="muted">${esc(t.inFolder(here.photos, here.folders.length))}. ${esc(inRoot ? t.subAlways : t.outside)}</span>
        <button class="btn" data-fb-use ${here.id === d.showing ? "disabled" : ""}><ha-icon icon="mdi:check"></ha-icon>${esc(here.id === d.showing ? t.showingNow : t.useFolder)}</button></div>` : ""}
      ${fb.error ? `<div class="note err">${esc(fb.error)}</div>` : ""}</div>`;
    return html;
  }
  async _browse(folder) {
    const fb = this._fb = this._fb || {};
    const msg = { type: "posterwall/browse", entry_id: this._sel };
    if (folder !== undefined) msg.folder = folder === "" ? null : folder;
    try { fb.data = await this._hass.callWS(msg); fb.error = null; } catch (e) { fb.error = e.message || e.code; }
    if (this._fb === fb) this._settings();
  }
  async _useFolder() {
    const d = this._fb && this._fb.data; if (!d) return;
    try { await this._hass.callWS({ type: "posterwall/folder", entry_id: this._sel, folder: d.folder.id }); this._toast(this._t.folderSet); this._fb = null; }
    catch (e) { this._toast(e.message || e.code); }
    this._settings();
  }
  _bind(box) {
    const fo = box.querySelector("[data-fb-open]");
    if (fo) fo.addEventListener("click", () => { if (this._fb) { this._fb = null; this._settings(); } else { this._browse(); this._settings(); } });
    box.querySelectorAll("[data-fb]").forEach((el) => el.addEventListener("click", () => {
      if (this._fb && this._fb.data && el.dataset.fb === (this._fb.data.folder.id ?? "")) return;
      this._browse(el.dataset.fb);
    }));
    const fu = box.querySelector("[data-fb-use]");
    if (fu) fu.addEventListener("click", () => this._useFolder());
    box.querySelectorAll("[data-s]").forEach((el) => el.addEventListener("change", () => this._set(el.dataset.s, el.checked)));
    box.querySelectorAll("[data-seg]").forEach((el) => el.addEventListener("click", () => this._set(el.dataset.seg, el.dataset.v)));
    box.querySelectorAll("[data-sel]").forEach((el) => el.addEventListener("change", () => this._set(el.dataset.sel, el.value)));
    box.querySelectorAll("[data-r]").forEach((el) => {
      const v = box.querySelector(`[data-rv="${el.dataset.r}"]`), unit = v.textContent.replace(/^[\d.]+/, "");
      el.addEventListener("input", () => { v.textContent = el.value + unit; });
      el.addEventListener("change", () => this._set(el.dataset.r, Number(el.value)));
    });
    box.querySelectorAll("[data-time]").forEach((el) => el.addEventListener("change", () => el.value && this._set(el.dataset.time, `${el.value}:00`)));
    box.querySelectorAll("[data-o]").forEach((el) => el.addEventListener("change", () => {
      const k = el.dataset.o; this._opt({ [k]: el.type === "number" ? Math.max(1, Number(el.value) || 1) : el.value || null });
    }));
    box.querySelectorAll("[data-cal]").forEach((el) => el.addEventListener("change", () => {
      this._opt({ calendars: [...box.querySelectorAll("[data-cal]:checked")].map((c) => c.dataset.cal) });
    }));
    const rr = box.querySelector("[data-reread]");
    if (rr) rr.addEventListener("click", () => this._hass.callWS({ type: "posterwall/refresh", entry_id: this._sel }).catch((e) => this._toast(e.message)));
    const cfg = box.querySelector("[data-cfg]");
    if (cfg) cfg.addEventListener("click", () => this._go(`/config/integrations/integration/posterwall`));
  }

  /* ---------- display pages ---------- */
  async _resource() {
    // the card as a dashboard resource: every dashboard (also on Cast screens) loads it before drawing its cards
    const url = `/posterwall_static/posterwall-card.js?v=${VERSION}`;
    let res;
    try { res = await this._hass.callWS({ type: "lovelace/resources" }); } catch (e) { return; }
    const ours = res.filter((r) => r.url.split("?")[0] === "/posterwall_static/posterwall-card.js");
    try {
      if (!ours.length) await this._hass.callWS({ type: "lovelace/resources/create", res_type: "module", url });
      else if (ours[0].url !== url) await this._hass.callWS({ type: "lovelace/resources/update", resource_id: ours[0].id, res_type: "module", url });
      for (const r of ours.slice(1)) await this._hass.callWS({ type: "lovelace/resources/delete", resource_id: r.id });
    } catch (e) { /* resources in YAML mode: the card still loads for every page through Home Assistant */ }
  }
  async _pages() {
    // every wall gets its own display page; pages of deleted walls are removed
    await this._resource();
    let list;
    try { list = await this._hass.callWS({ type: "lovelace/dashboards/list" }); } catch (e) { return; }
    const want = new Map(this._walls.map((w) => [w.dashboard, w]));
    for (const d of list) {
      if (/^posterwall-[0-9a-z]{8}$/.test(d.url_path) && !want.has(d.url_path)) {
        try { await this._hass.callWS({ type: "lovelace/dashboards/delete", dashboard_id: d.id }); } catch (e) { /* later */ }
      }
    }
    const have = new Set(list.map((d) => d.url_path));
    for (const d of list) {
      // a renamed wall: its page follows (Echos with TECHO5 find the page by this title)
      const w = want.get(d.url_path);
      if (w && d.title !== `PosterWall ${w.title}`) {
        try { await this._hass.callWS({ type: "lovelace/dashboards/update", dashboard_id: d.id, title: `PosterWall ${w.title}` }); } catch (e) { /* later */ }
      }
    }
    for (const [path, w] of want) {
      if (have.has(path)) continue;
      try {
        await this._hass.callWS({ type: "lovelace/dashboards/create", url_path: path, title: `PosterWall ${w.title}`, icon: "mdi:image-frame",
          show_in_sidebar: false, require_admin: false, mode: "storage" });
        await this._hass.callWS({ type: "lovelace/config/save", url_path: path, config: {
          title: `PosterWall ${w.title}`,
          views: [{ title: w.title, path: "wall", type: "panel", cards: [{ type: "custom:posterwall-card", wall: w.entry_id, fullscreen: true }] }],
        } });
      } catch (e) { console.warn("PosterWall: display page could not be created", e); }
    }
    this._pagesReady = true;
    this._screens();
  }

  /* ---------- screens ---------- */
  async _loadScreens() {
    try { this._sc = await this._hass.callWS({ type: "posterwall/screens" }); } catch (e) { this._sc = { screens: [], kept: {}, integrations: {} }; }
    this._screens();
  }
  _screens() {
    const box = this._main && this._main.querySelector(".screens"), t = this._t;
    if (!box) return;
    const w = this._walls.find((x) => x.entry_id === this._sel); if (!w) return;
    const sc = this._sc || { screens: [], kept: {}, integrations: {} };
    const url = `${location.origin}/${w.dashboard}/wall`;
    const missing = INSTALL.filter(([k]) => !sc.integrations[k]);
    box.innerHTML = `<h2><ha-icon icon="mdi:monitor-share"></ha-icon><span class="grow">${esc(t.screens)}</span></h2>
      ${sc.screens.length ? sc.screens.map((s) => {
        const kept = sc.kept[s.id];
        return `<div class="screen"><div class="ic"><ha-icon icon="${KIND_ICON[s.kind] || "mdi:monitor"}"></ha-icon></div>
          <div class="nm"><b>${esc(s.name)}</b><span class="muted">${esc([s.area, s.model || t.kinds[s.kind]].filter(Boolean).join(" · "))}${kept && kept !== this._sel ? ` · ${esc(t.showing)} ${esc((this._walls.find((x) => x.entry_id === kept) || {}).title || "")}` : ""}</span></div>
          ${s.kind === "browser_mod" ? "" : `<label class="keep" title="${esc(t.keepHint)}"><span>${esc(t.keep)}</span><span class="sw"><input type="checkbox" data-keep="${esc(s.id)}" ${kept === this._sel ? "checked" : ""}><span></span></span></label>`}
          <button class="btn" data-show="${esc(s.id)}" data-name="${esc(s.name)}" ${this._pagesReady ? "" : "disabled"}><ha-icon icon="mdi:cast"></ha-icon>${esc(t.show)}</button></div>`;
      }).join("") : `<div class="muted">${esc(t.noScreens)}</div>`}
      ${sc.integrations.cast && !sc.cast_ready && sc.screens.some((s) => s.kind === "cast") ? `<div class="note">${esc(t.castHttps)}</div>` : ""}
      ${missing.length ? `<p class="muted">${esc(t.installHint)} ${missing.map(([k, l]) => `<a href="${l}" target="_blank" rel="noreferrer">${esc(t.kinds[k])}</a>`).join(" · ")}</p>` : ""}
      <h2 style="margin-top:18px"><ha-icon icon="mdi:link-variant"></ha-icon><span class="grow">${esc(t.page)}</span>
        <span class="muted">${esc(this._pagesReady ? t.pageReady : t.pageMaking)}</span></h2>
      <div class="link"><code>${esc(url)}</code><button class="btn flat" data-copy>${esc(t.copy)}</button>
        <a class="btn flat" href="/${esc(w.dashboard)}/wall" target="_blank" rel="noreferrer">${esc(t.openPage)}</a></div>
      <p class="muted">${esc(t.linkHint)}</p>`;
    box.querySelectorAll("[data-show]").forEach((b) => b.addEventListener("click", async () => {
      b.disabled = true;
      const keep = !!(box.querySelector(`[data-keep="${CSS_ESC(b.dataset.show)}"]`) || {}).checked;
      try { await this._hass.callWS({ type: "posterwall/show", entry_id: this._sel, screen: b.dataset.show, keep }); this._toast(t.sent(b.dataset.name)); }
      catch (e) { this._toast(`${t.failed} ${e.message || e.code}`); }
      b.disabled = false;
      this._loadScreens();
    }));
    box.querySelectorAll("[data-keep]").forEach((el) => el.addEventListener("change", async () => {
      try { await this._hass.callWS({ type: "posterwall/keep", entry_id: this._sel, screen: el.dataset.keep, keep: el.checked }); } catch (e) { this._toast(e.message); }
      this._loadScreens();
    }));
    box.querySelector("[data-copy]").addEventListener("click", async () => {
      try { await navigator.clipboard.writeText(url); this._toast(t.copied); } catch (e) { this._toast(url); }
    });
  }
  _toast(text) {
    const old = this.shadowRoot.querySelector(".toast"); if (old) old.remove();
    const d = document.createElement("div"); d.className = "toast"; d.textContent = text;
    this.shadowRoot.appendChild(d); setTimeout(() => d.remove(), 3500);
  }
}
const CSS_ESC = (s) => (window.CSS && window.CSS.escape ? window.CSS.escape(s) : s.replace(/"/g, '\\"'));
const LOGO = `<defs>
    <linearGradient id="pw" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ffc94d"/><stop offset="1" stop-color="#ff5a7a"/></linearGradient>
    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#5ec8f2"/><stop offset="1" stop-color="#2f7fd8"/></linearGradient>
    <filter id="sh" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="2.5" stdDeviation="2.5" flood-color="#000" flood-opacity=".45"/></filter>
  </defs>
  <rect width="120" height="120" rx="28" fill="#1c2129"/>
  <g transform="rotate(-9 44 62)" filter="url(#sh)">
    <rect x="19" y="34" width="46" height="54" rx="2.5" fill="#f4f1ea"/>
    <rect x="23.5" y="38.5" width="37" height="34" rx="1" fill="url(#sky)"/>
    <path d="M23.5 72.5 L36 57 L44 65 L50 59 L60.5 72.5 Z" fill="#1f6f4a"/>
    <circle cx="52" cy="47" r="4" fill="#ffe08a"/>
  </g>
  <g transform="rotate(8 77 58)" filter="url(#sh)">
    <rect x="54" y="28" width="46" height="54" rx="2.5" fill="#f4f1ea"/>
    <rect x="58.5" y="32.5" width="37" height="34" rx="1" fill="url(#pw)"/>
    <circle cx="70" cy="45" r="5" fill="#fff3" />
    <path d="M58.5 66.5 L70 54 L79 62 L86 55 L95.5 66.5 Z" fill="#00000030"/>
  </g>
  <circle cx="76" cy="27" r="5.2" fill="url(#pw)" stroke="#1c2129" stroke-width="1.5"/>
  <circle cx="40" cy="33" r="5.2" fill="#e6edf3" stroke="#1c2129" stroke-width="1.5"/>
<metadata><c2pa:manifest>AAAWgmp1bWIAAAAeanVtZGMycGEAEQAQgAAAqgA4m3EDYzJwYQAAABZcanVtYgAAAEdqdW1kYzJtYQARABCAAACqADibcQN1cm46YzJwYTowNjZiNmRjYy00ZjZkLTQ4OTAtYjFkMS01OGNkYjc3MThkOTkAAAADl2p1bWIAAAApanVtZGMyYXMAEQAQgAAAqgA4m3EDYzJwYS5hc3NlcnRpb25zAAAAALxqdW1iAAAARGp1bWRjYm9yABEAEIAAAKoAOJtxE2MycGEuaW5ncmVkaWVudC52MwAAAAAYYzJzaGy67TFNPJi7ap7E25QAa44AAABwY2JvcqNpZGM6Zm9ybWF0bWltYWdlL3N2Zyt4bWxqaW5zdGFuY2VJRHgseG1wOmlpZDowZDBmNTBhYS0zMDdhLTQyMmUtOGQxNS0yNmJlYmYwY2I3YzlscmVsYXRpb25zaGlwaHBhcmVudE9mAAAB4mp1bWIAAABBanVtZGNib3IAEQAQgAAAqgA4m3ETYzJwYS5hY3Rpb25zLnYyAAAAABhjMnNo2kdgelXkflWcUJE4/qwMHwAAAZljYm9yomdhY3Rpb25zgqJmYWN0aW9ua2MycGEub3BlbmVkanBhcmFtZXRlcnOha2luZ3JlZGllbnRzgaJjdXJseC1zZWxmI2p1bWJmPWMycGEuYXNzZXJ0aW9ucy9jMnBhLmluZ3JlZGllbnQudjNkaGFzaFgg6iPikbhrREYtHSUI/R/kdtkTSTdN5NG00I3fcshNhG+kZmFjdGlvbngdY29tLmFudGhyb3BpYy5jbGF1ZGUucHJvdmlkZWRqcGFyYW1ldGVyc6F4H2NvbS5hbnRocm9waWMub3JpZ2luLWNvbmZpZGVuY2VndW5rbm93bmtkZXNjcmlwdGlvbnhmQ2xhdWRlIHByb3ZpZGVkIHRoaXMgZmlsZSBhdCB0aGUgcmVxdWVzdCBvZiBhIHVzZXIgYW5kIG1heSBoYXZlIGNyZWF0ZWQgb3IgbW9kaWZpZWQgdGhlIGZpbGUgY29udGVudHMubXNvZnR3YXJlQWdlbnShZG5hbWVmQ2xhdWRlcmFsbEFjdGlvbnNJbmNsdWRlZPUAAADIanVtYgAAAEBqdW1kY2JvcgARABCAAACqADibcRNjMnBhLmhhc2guZGF0YQAAAAAYYzJzaBIIC1iCahSO4A3aU/cmpjwAAACAY2JvcqVjYWxnZnNoYTI1NmNwYWRMAAAAAAAAAAAAAAAAZGhhc2hYIN3/ial+EjTH4ZhmMBogqceGM/ee/oPEr4bsti04VOXqZG5hbWVuanVtYmYgbWFuaWZlc3RqZXhjbHVzaW9uc4GiZXN0YXJ0GQYJZmxlbmd0aBkeBAAAAj5qdW1iAAAAJ2p1bWRjMmNsABEAEIAAAKoAOJtxA2MycGEuY2xhaW0udjIAAAACD2Nib3KlY2FsZ2ZzaGEyNTZpc2lnbmF0dXJleE1zZWxmI2p1bWJmPS9jMnBhL3VybjpjMnBhOjA2NmI2ZGNjLTRmNmQtNDg5MC1iMWQxLTU4Y2RiNzcxOGQ5OS9jMnBhLnNpZ25hdHVyZWppbnN0YW5jZUlEeCx4bXA6aWlkOmEwYzE3ZDkzLWFhMGMtNDcyMy1hM2RmLTEzN2Q2NDRmYzMxZXJjcmVhdGVkX2Fzc2VydGlvbnODomN1cmx4LXNlbGYjanVtYmY9YzJwYS5hc3NlcnRpb25zL2MycGEuaW5ncmVkaWVudC52M2RoYXNoWCDqI+KRuGtERi0dJQj9H+R22RNJN03k0bTQjd9yyE2Eb6JjdXJseCpzZWxmI2p1bWJmPWMycGEuYXNzZXJ0aW9ucy9jMnBhLmFjdGlvbnMudjJkaGFzaFggwq9Ihbrp4u5VYZcw50eDjYw2ML2QzyHyGB/n9OQrEH+iY3VybHgpc2VsZiNqdW1iZj1jMnBhLmFzc2VydGlvbnMvYzJwYS5oYXNoLmRhdGFkaGFzaFgg+O6xrY8oRiSqpRol61mHVtaWG3e2x2mJLfQrGXEY+hh0Y2xhaW1fZ2VuZXJhdG9yX2luZm+jZG5hbWVvQW50aHJvcGljIEZpbGVzZ3ZlcnNpb25lMS4wLjBrc3BlY1ZlcnNpb25lMi40LjAAABA4anVtYgAAAChqdW1kYzJjcwARABCAAACqADibcQNjMnBhLnNpZ25hdHVyZQAAABAIY2JvctKEWQISogEmGCFZAgowggIGMIIBjaADAgECAhRA5aAK7sI50L64g/oGQgU9Z1UTADAKBggqhkjOPQQDAzBJMRcwFQYDVQQKEw5BbnRocm9waWMsIFBCQzEuMCwGA1UEAxMlQW50aHJvcGljIENvbnRlbnQgQ3JlZGVudGlhbHMgUm9vdCBDQTAeFw0yNjA4MDcxODQzNTZaFw0yODA4MDYxOTQzNTZaMEQxFzAVBgNVBAoTDkFudGhyb3BpYywgUEJDMSkwJwYDVQQDEyBBbnRocm9waWMgQ2xhdWRlIENvbnRlbnQgU2lnbmluZzBZMBMGByqGSM49AgEGCCqGSM49AwEHA0IABJh6CmvLUBgFFNU0vUKlOVtE6djd17L5SuwX0LemFisBM3dkd/3cyjxFA3Qo5S46fX0/ihY0VZ7mfb9KF703t5OjWDBWMA4GA1UdDwEB/wQEAwIHgDAVBgNVHSUEDjAMBgorBgEEAYPoXgIBMAwGA1UdEwEB/wQCMAAwHwYDVR0jBBgwFoAUzlHiBIFOZFsj+OPEz5o+nMHXXMIwCgYIKoZIzj0EAwMDZwAwZAIwMXMdFJ4BetLLVY7ORuE9noqbbAZOZn/aArXyTwFAZfKrPzxF2vPoJNf1+UCdg1XGAjBwX1zd9WGqYkqmL5SFqw1QySjr1zJfpJM9+1rdDwSPLMOPOjKuiXjoU/pUUeG9RwmhY3BhZFkNngAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAPZYQJCSf9RPMTFwl1YmahOfr4XLYAfDKx6GCqv/0nkDVu0hQ+d85CAR6QMze7UJmlYntG5XCZVoP9Xt3uI5pRcgoRA=</c2pa:manifest></metadata>`;

customElements.get("posterwall-panel") || customElements.define("posterwall-panel", PosterWallPanel);
