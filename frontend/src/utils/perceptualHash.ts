/**
 * Computes a client-side difference hash (dHash) for an image or video frame.
 * Renders the media onto a tiny (size + 1) x size canvas, converts it to greyscale,
 * and generates a hex string by comparing adjacent pixels in each row.
 */
export function computeDifferenceHash(
  imgOrVideo: HTMLImageElement | HTMLVideoElement,
  size = 16
): string {
  const canvas = document.createElement('canvas')
  const width = size + 1
  const height = size
  canvas.width = width
  canvas.height = height
  
  const ctx = canvas.getContext('2d')
  if (!ctx) return ''

  // Draw media onto the tiny canvas
  ctx.drawImage(imgOrVideo, 0, 0, width, height)

  // Extract pixel colors
  const imgData = ctx.getImageData(0, 0, width, height)
  const data = imgData.data

  const totalPixels = width * height
  const luminances = new Float32Array(totalPixels)

  for (let i = 0; i < data.length; i += 4) {
    const r = data[i]
    const g = data[i + 1]
    const b = data[i + 2]
    
    // Standard luminance conversion: 0.299R + 0.587G + 0.114B
    const lum = 0.299 * r + 0.587 * g + 0.114 * b
    luminances[i / 4] = lum
  }

  // Construct hexadecimal representation (4 bits per character)
  let hashStr = ''
  let bitBuffer = 0
  let bitCount = 0

  for (let row = 0; row < height; row++) {
    for (let col = 0; col < size; col++) {
      const idxLeft = row * width + col
      const idxRight = idxLeft + 1
      
      const bit = luminances[idxLeft] > luminances[idxRight] ? 1 : 0
      bitBuffer = (bitBuffer << 1) | bit
      bitCount++

      if (bitCount === 4) {
        hashStr += bitBuffer.toString(16)
        bitBuffer = 0
        bitCount = 0
      }
    }
  }

  return hashStr
}

/**
 * Calculates the Hamming distance (bit-level differences) between two hex strings.
 */
export function hammingDistance(hex1: string, hex2: string): number {
  if (hex1.length !== hex2.length) return 999
  
  let distance = 0
  for (let i = 0; i < hex1.length; i++) {
    const val1 = parseInt(hex1[i], 16)
    const val2 = parseInt(hex2[i], 16)
    
    // XOR finds the differing bits
    let xor = val1 ^ val2
    while (xor > 0) {
      if (xor & 1) distance++
      xor >>= 1
    }
  }
  
  return distance
}
