import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  cropSourceRect,
  cropTargetWidth,
  getCroppedCanvas,
  requestCroppedCanvas,
  clearCropCache,
} from './cropCache'

// jsdom has no real canvas 2D context and never fires Image load events,
// so both are stubbed here.
const drawImage = vi.fn()

function stubAutoLoadingImage(naturalWidth = 1000, naturalHeight = 10000) {
  vi.stubGlobal('Image', class {
    onload: (() => void) | null = null
    onerror: (() => void) | null = null
    naturalWidth = naturalWidth
    naturalHeight = naturalHeight
    set src(_v: string) {
      this.onload?.()
    }
  })
}

beforeEach(() => {
  clearCropCache()
  drawImage.mockClear()
  vi.stubGlobal('Image', class {
    onload: (() => void) | null = null
    onerror: (() => void) | null = null
  })
  // jsdom returns null from getContext without the canvas package
  Object.defineProperty(HTMLCanvasElement.prototype, 'getContext', {
    writable: true,
    value: vi.fn().mockReturnValue({ drawImage }),
  })
})

describe('cropSourceRect', () => {
  it('takes the top 9:21 slice of a very tall image', () => {
    expect(cropSourceRect(1000, 10000)).toEqual({ sx: 0, sy: 0, sw: 1000, sh: 2333 })
  })

  it('never exceeds the natural height', () => {
    expect(cropSourceRect(1000, 2000)).toEqual({ sx: 0, sy: 0, sw: 1000, sh: 2000 })
  })
})

describe('cropTargetWidth', () => {
  it('scales with card size and DPR', () => {
    expect(cropTargetWidth(250, 2)).toBe(500)
  })

  it('clamps to a sane range', () => {
    expect(cropTargetWidth(100, 1)).toBe(250)
    expect(cropTargetWidth(500, 3)).toBe(750)
  })
})

describe('requestCroppedCanvas', () => {
  it('draws the top slice into a display-sized canvas and caches it', async () => {
    stubAutoLoadingImage(1000, 10000)

    const canvas = await requestCroppedCanvas('rule34-1-250', 'https://test.com/big.jpg', 250)

    expect(canvas.width).toBe(250)
    expect(canvas.height).toBe(583) // 250 * (2333 / 1000), rounded
    expect(drawImage).toHaveBeenCalledWith(expect.anything(), 0, 0, 1000, 2333, 0, 0, 250, 583)

    // Second call with the same key must reuse the cache (no new load)
    const again = await requestCroppedCanvas('rule34-1-250', 'https://test.com/big.jpg', 250)
    expect(again).toBe(canvas)
    expect(getCroppedCanvas('rule34-1-250')).toBe(canvas)
  })

  it('shares one in-flight load between concurrent callers with the same key', async () => {
    stubAutoLoadingImage()
    const [a, b] = await Promise.all([
      requestCroppedCanvas('rule34-2-250', 'https://test.com/big.jpg', 250),
      requestCroppedCanvas('rule34-2-250', 'https://test.com/big.jpg', 250),
    ])
    expect(a).toBe(b)
  })

  it('limits concurrency to 2 loads and processes the queue in order', async () => {
    const instances: Array<{ onload: (() => void) | null }> = []
    vi.stubGlobal('Image', class {
      onload: (() => void) | null = null
      onerror: (() => void) | null = null
      naturalWidth = 1000
      naturalHeight = 10000
      set src(_v: string) {
        instances.push(this)
      }
    })

    const p1 = requestCroppedCanvas('k1', 'https://test.com/1.jpg', 250)
    const p2 = requestCroppedCanvas('k2', 'https://test.com/2.jpg', 250)
    const p3 = requestCroppedCanvas('k3', 'https://test.com/3.jpg', 250)

    expect(instances.length).toBe(2) // third is queued

    instances[0]!.onload?.()
    await p1
    expect(instances.length).toBe(3)

    instances[1]!.onload?.()
    instances[2]!.onload?.()
    await Promise.all([p2, p3])
  })

  it('rejects and does not cache when the source fails to load', async () => {
    vi.stubGlobal('Image', class {
      onload: (() => void) | null = null
      onerror: (() => void) | null = null
      set src(_v: string) {
        this.onerror?.()
      }
    })

    await expect(requestCroppedCanvas('bad-1', 'https://test.com/broken.jpg', 250)).rejects.toThrow()
    expect(getCroppedCanvas('bad-1')).toBeUndefined()

    // A later retry must start a fresh load (rejects again, not a cached failure)
    await expect(requestCroppedCanvas('bad-1', 'https://test.com/broken.jpg', 250)).rejects.toThrow()
  })

  it('evicts least-recently-used entries beyond the cap', async () => {
    stubAutoLoadingImage()

    for (let i = 0; i < 41; i++) {
      await requestCroppedCanvas(`lru-${i}`, `https://test.com/${i}.jpg`, 250)
    }

    expect(getCroppedCanvas('lru-0')).toBeUndefined() // evicted
    expect(getCroppedCanvas('lru-40')).toBeDefined() // newest kept
  })
})
