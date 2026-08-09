/**
 * Client-side cropped previews for very tall ("long") posts.
 *
 * Why: the grid crops long posts to a 9:21 top slice purely via CSS, but the
 * browser still decodes the FULL source image at natural size (long strips are
 * often 20-40+ MP). Decoded bitmaps of that size are evicted from the browser
 * image cache almost immediately, so scrolling past such cards triggers a
 * re-decode storm -> heavy jank.
 *
 * How: load the original once, draw only the visible 9:21 top slice into a
 * canvas at display resolution, and keep that canvas in a small in-memory LRU
 * cache. A tainted (cross-origin) canvas can still be *displayed* — we never
 * read pixels back (no toBlob/getImageData), so CDN CORS headers are not
 * needed. The cached canvas is ~0.5-1.5 MP instead of the full bitmap, so
 * re-mounting a card on scroll is instant and cheap.
 *
 * Animated posts must NOT go through here (a canvas freezes the first frame).
 */

const CROP_RATIO = 21 / 9 // mirrors the 9:21 crop used by PostCard.mediaStyle
const MAX_ENTRIES = 40
const MAX_CONCURRENT_LOADS = 2

const cache = new Map<string, HTMLCanvasElement>()
const pending = new Map<string, Promise<HTMLCanvasElement>>()
const queue: (() => void)[] = []
let inFlight = 0

/** Clamp the raster width of the cropped canvas (CSS pixels * DPR). */
export function cropTargetWidth(cardSize: number, dpr: number): number {
  const w = Math.round(cardSize * (Number.isFinite(dpr) && dpr > 0 ? dpr : 1))
  return Math.max(250, Math.min(750, w))
}

/** Source rectangle (top slice) matching `object-fit: cover; object-position: top` for a 9:21 box. */
export function cropSourceRect(imgWidth: number, imgHeight: number): { sx: number; sy: number; sw: number; sh: number } {
  return { sx: 0, sy: 0, sw: imgWidth, sh: Math.min(imgHeight, Math.round(imgWidth * CROP_RATIO)) }
}

/** Get a cached cropped canvas, refreshing its LRU position. */
export function getCroppedCanvas(key: string): HTMLCanvasElement | undefined {
  const canvas = cache.get(key)
  if (canvas) {
    cache.delete(key)
    cache.set(key, canvas)
  }
  return canvas
}

function putCroppedCanvas(key: string, canvas: HTMLCanvasElement) {
  cache.set(key, canvas)
  while (cache.size > MAX_ENTRIES) {
    const oldest = cache.keys().next().value
    if (oldest === undefined) break
    cache.delete(oldest)
  }
}

function runNext() {
  if (inFlight >= MAX_CONCURRENT_LOADS) return
  const task = queue.shift()
  if (!task) return
  inFlight++
  task()
}

/**
 * Load `url`, draw its top 9:21 slice into a canvas of `targetW` width and
 * cache it under `key`. Concurrent calls with the same key share one load.
 * Rejects if the image fails to load or 2D canvas is unavailable.
 */
export function requestCroppedCanvas(key: string, url: string, targetW: number): Promise<HTMLCanvasElement> {
  const cached = getCroppedCanvas(key)
  if (cached) return Promise.resolve(cached)

  const existing = pending.get(key)
  if (existing) return existing

  const promise = new Promise<HTMLCanvasElement>((resolve, reject) => {
    queue.push(() => {
      const img = new Image()
      img.onload = () => {
        try {
          const { sx, sy, sw, sh } = cropSourceRect(img.naturalWidth, img.naturalHeight)
          if (!sw || !sh) throw new Error('empty image')

          const canvas = document.createElement('canvas')
          canvas.width = targetW
          canvas.height = Math.round(targetW * (sh / sw))
          canvas.className = 'post-card-crop-canvas'
          const ctx = canvas.getContext('2d')
          if (!ctx) throw new Error('2d context unavailable')
          ctx.drawImage(img, sx, sy, sw, sh, 0, 0, canvas.width, canvas.height)

          putCroppedCanvas(key, canvas)
          resolve(canvas)
        } catch (e) {
          reject(e)
        } finally {
          releaseSlot()
        }
      }
      img.onerror = () => {
        releaseSlot()
        reject(new Error('crop source failed to load'))
      }
      img.src = url
    })
    runNext()
  })

  pending.set(key, promise)
  // Self-clean once settled; .then(fn, fn) avoids creating a rejecting derived
  // promise (unlike .finally) and runs after pending.set even if the loader
  // settled synchronously.
  const cleanup = () => {
    if (pending.get(key) === promise) pending.delete(key)
  }
  promise.then(cleanup, cleanup)
  return promise
}

function releaseSlot() {
  inFlight--
  runNext()
}

/** Drop everything (used by tests). */
export function clearCropCache() {
  cache.clear()
  pending.clear()
  queue.length = 0
  inFlight = 0
}
