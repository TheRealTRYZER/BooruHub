import { describe, it, expect } from 'vitest'
import { usePinchZoom } from './usePinchZoom'

describe('usePinchZoom', () => {
  it('should initialize with default states', () => {
    const { scale, translateX, translateY } = usePinchZoom()
    expect(scale.value).toBe(1)
    expect(translateX.value).toBe(0)
    expect(translateY.value).toBe(0)
  })

  it('should reset to default states when reset is called', () => {
    const { scale, translateX, translateY, reset } = usePinchZoom()
    scale.value = 2.5
    translateX.value = 100
    translateY.value = -50
    reset()
    expect(scale.value).toBe(1)
    expect(translateX.value).toBe(0)
    expect(translateY.value).toBe(0)
  })

  it('should handle single finger touch for panning if zoomed', () => {
    const { scale, translateX, translateY, onTouchStart, onTouchMove } = usePinchZoom()
    scale.value = 2

    const touchEventStart = {
      touches: [
        { clientX: 10, clientY: 20 }
      ],
      stopPropagation: () => {}
    } as unknown as TouchEvent

    onTouchStart(touchEventStart)

    const touchEventMove = {
      touches: [
        { clientX: 30, clientY: 50 }
      ],
      stopPropagation: () => {},
      preventDefault: () => {}
    } as unknown as TouchEvent

    onTouchMove(touchEventMove)

    expect(translateX.value).toBe(20) // 30 - 10
    expect(translateY.value).toBe(30) // 50 - 20
  })

  it('should handle two finger pinch to scale', () => {
    const { scale, onTouchStart, onTouchMove } = usePinchZoom()

    const touchEventStart = {
      touches: [
        { clientX: 0, clientY: 0 },
        { clientX: 10, clientY: 0 }
      ],
      stopPropagation: () => {}
    } as unknown as TouchEvent

    onTouchStart(touchEventStart)

    const touchEventMove = {
      touches: [
        { clientX: 0, clientY: 0 },
        { clientX: 20, clientY: 0 }
      ],
      stopPropagation: () => {},
      preventDefault: () => {}
    } as unknown as TouchEvent

    onTouchMove(touchEventMove)

    expect(scale.value).toBe(1.125)
  })
})
