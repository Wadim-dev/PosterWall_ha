/* PosterWall: loads and decodes one photo beside the page.
 *
 * A photo read with fetch becomes a Blob, and Chrome keeps every Blob in its main process until the
 * page that made it collects its garbage - which a quiet page hardly ever does, so a screen running
 * all day grew by every photo shown. Here the Blob lives in a worker that the card ends after each
 * photo: ending it frees everything it held, at once and every time.
 */
self.onmessage = async (e) => {
  const { url, width } = e.data;
  try {
    const a = await fetch(url, { cache: "no-store" });
    if (!a.ok) throw new Error(String(a.status));
    const blob = await a.blob();
    let bmp;
    // phone photos are shrunk while decoding: little memory, no work on the page
    try { bmp = await createImageBitmap(blob, { resizeWidth: width, resizeQuality: "medium" }); }
    catch (err) { bmp = await createImageBitmap(blob); }
    self.postMessage({ bmp }, [bmp]);
  } catch (err) {
    self.postMessage({ error: String(err) });
  }
};
