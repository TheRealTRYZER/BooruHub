import { describe, it, expect, vi } from 'vitest'
import { computeDifferenceHash, hammingDistance } from './perceptualHash'

describe('perceptualHash utilities', () => {
  describe('hammingDistance', () => {
    it('should calculate Hamming distance between identical hex strings as 0', () => {
      expect(hammingDistance('ffff', 'ffff')).toBe(0)
      expect(hammingDistance('0000', '0000')).toBe(0)
    })

    it('should calculate Hamming distance correctly for different hex strings', () => {
      // 'f' is 1111, 'e' is 1110 -> 1 bit difference
      expect(hammingDistance('f', 'e')).toBe(1)
      // 'f' is 1111, '0' is 0000 -> 4 bits difference
      expect(hammingDistance('f', '0')).toBe(4)
      // 'ffff' and '0000' -> 16 bits difference
      expect(hammingDistance('ffff', '0000')).toBe(16)
    })

    it('should return 999 for strings of different length', () => {
      expect(hammingDistance('ff', 'fff')).toBe(999)
    })
  })

  describe('computeDifferenceHash', () => {
    it('should calculate difference hash correctly based on drawImage and mock canvas output', () => {
      // Mock canvas API
      const mockGetImageData = vi.fn().mockReturnValue({
        // Size 17 * 16 = 272 pixels, RGBA data
        // Alternating pixel values: even indices are 255, odd indices are 0
        data: new Uint8ClampedArray(
          Array.from({ length: 272 }, (_, i) => {
            const val = i % 2 === 0 ? 255 : 0
            return [val, val, val, 255]
          }).flat()
        )
      })

      const mockGetContext = vi.fn().mockReturnValue({
        drawImage: vi.fn(),
        getImageData: mockGetImageData
      })

      const mockCanvas = {
        getContext: mockGetContext,
        width: 0,
        height: 0
      }

      // Spy on document.createElement
      const spyCreateElement = vi.spyOn(document, 'createElement').mockImplementation((tagName: string) => {
        if (tagName === 'canvas') {
          return mockCanvas as any
        }
        return document.createElement(tagName)
      })

      const mockImg = {} as HTMLImageElement
      const hash = computeDifferenceHash(mockImg, 16)

      expect(mockGetContext).toHaveBeenCalledWith('2d')
      expect(mockGetImageData).toHaveBeenCalledWith(0, 0, 17, 16)
      
      // Hash should be 64 characters long for a 16x16 difference output (256 bits)
      expect(hash.length).toBe(64)
      
      // First row (even start) has bits 1010101010101010 -> aaaa
      // Second row (odd start) has bits 0101010101010101 -> 5555
      // This alternates perfectly: aaaa5555aaaa5555...
      const expectedHash = 'aaaa5555'.repeat(8)
      expect(hash).toBe(expectedHash)

      spyCreateElement.mockRestore()
    })
  })
})
