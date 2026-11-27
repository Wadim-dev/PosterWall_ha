# Changelog

## 1.0.9

- **Nothing piles up in the browser cache:** photos are sent with `Cache-Control: no-store` and the card fetches them without caching. Every photo link is used only once, but the browser kept each one for an hour. A screen that runs all day wrote every photo into its cache (reproduced: about 100 MB a minute at 10 photos a second, flat with no-store); on an Echo with TECHO5 the dashboard server's memory grew by about 140 MB an hour.

## 1.0.8

- **Photos leave Home Assistant display-sized:** every photo is shrunk to the size the card draws (at most 720 pixels wide, JPEG) before it goes to a screen – also photos from Home Assistant media folders, which went out as the full file before. A phone photo is now about 50–100 KB instead of several MB: less network, less decoding, and a long-running browser no longer piles up memory. On an Echo with TECHO5 the full files made the dashboard server's memory grow by about 30 MB a minute until its pages were stopped (reproduced: big photos +45 MB a minute, shrunk photos flat). Photos are turned upright by their EXIF orientation; transparent images get a white ground; at most two photos are shrunk at once.
- Choosing the next photo no longer walks through the whole collection for *On this day* and favourites (lists are prepared once per photo read).
- The card redraws the weather only when the weather changed, not on every state change in Home Assistant.

## 1.0.7

- **No endless restarts:** a kept Echo is restarted itself at most once in six hours, and a screen only counts as fixed after an hour without a break. A screen that keeps breaking down (for example because the TECHO5 dashboard server runs out of memory) is left alone after two rounds and a repair says why. Before, a screen that ran again for a few minutes started the count afresh, so Echos could be restarted every half hour all day.
- **New effect "None":** the new photo is simply there, without animation. Lightest for weak devices and streamed screens: an Echo with TECHO5 gets one new picture per change instead of many per second during an animation (measured: 7 instead of 141 pictures in 30 seconds).
- Lighter animations: no permanent compositing layers, and a leaving photo is removed only after its way out has ended (Fade took longer than the photo stayed).
- Diagnostics show what every display page holds (memory, photos, elements, minutes running) and the watchdog's rounds, to find a screen that grows.

## 1.0.6

- Updates reach the screens by themselves: at start PosterWall points the card resource to the new version. Before, it was only changed when an admin opened the PosterWall page, so screens that loaded again after an update still got the old card.

## 1.0.5

- The watchdog counts every display page once (a page asking for photos and reporting was counted twice, so one hung screen could go unnoticed next to a running one).

## 1.0.4

- The watchdog now sees every display page that asks for photos, also pages still running an older card in a streaming browser (Echo with TECHO5). Before, such pages did not report and kept Echos were restarted again and again.
- No endless restarts: after two rounds without success PosterWall leaves the screen alone and shows a repair that says why (most often the TECHO5 dashboard server is down). It goes away by itself when photos come again.
- Diagnostics show which display pages reported lately and the watchdog's step.

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
