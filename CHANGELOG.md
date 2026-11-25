# Changelog

## 1.0.3

- **Screens never hang:** every display page reports while it pins photos. A kept Echo (TECHO5) or Fully Kiosk tablet whose screen is on and that stops reporting is brought back by itself, step by step: page loaded again, page opened anew (Echo: dashboard closed and opened), finally the Echo restarts.
- **Reload screens:** button in the panel and button entity – loads the wall again on every screen at once (Echo: restart).

## 1.0.2

- **Choose folder** on the PosterWall page: your real folder tree (Home Assistant media), any depth, with the number of photos in each folder. Sub folders are always included; a folder outside the wall's folder becomes its new folder.
- **Echo Show with TECHO5** is found by itself: one tap sets *Streamed*, the wall's page and *also when idle*. *Always* sets the page back when another one was picked.
- *Reconfigure* asks for the source first (switch between Home Assistant media, Immich and Synology Photos) and starts in the folder the wall shows now.
- Synology Photos: the real folders of the personal and shared space, not only albums.
- A renamed wall renames its display page too.
- A deeper folder that was deleted falls back to all photos instead of an error.
- Quality scale **Platinum**: strict typing checked on every change.

## 1.0.1

- Big photo libraries: a chosen album or folder is now read on its own, so it is complete even when the whole library has more than 50,000 photos. The album list is read much faster.
- Display pages speak the language of Home Assistant, not the browser default of the screen (Cast devices and kiosk browsers often run in English).
- The same picture in two folders (backup and sorted copy) is no longer shown twice at the same time.

## 1.0.0

First release.

- Photo sources: Home Assistant media (any folder or NAS share), Immich and Synology Photos (with two-factor sign-in).
- Guided setup: pick the source, browse to the folder, name the wall, choose weather and calendars.
- PosterWall panel with live preview in the format of your screen and all settings.
- Screens found by themselves (Google Cast, Fully Kiosk Browser, Browser Mod) with *Show* and *Always*.
- Effects: drop, fade, blow away, flip, random. Backgrounds: cork, wood, slate, black.
- Favourites more often (Immich), *on this day* photos, date under the photo.
- Clock, weather and events on the wall.
- Night mode: dimmed, clock only or dark.
- Every setting as entity, action `posterwall.show`, diagnostics, English and German.
