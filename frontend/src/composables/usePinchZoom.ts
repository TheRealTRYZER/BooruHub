import { ref } from 'vue'

export function usePinchZoom() {
  const scale = ref(1)
  const translateX = ref(0)
  const translateY = ref(0)
  const isPinching = ref(false)
  const isPanning = ref(false)

  let initialDistance = 0
  let startScale = 1
  let initialMidX = 0
  let initialMidY = 0
  let startTranslateX = 0
  let startTranslateY = 0

  let panStartX = 0
  let panStartY = 0

  function onTouchStart(e: TouchEvent) {
    if (e.touches.length === 2) {
      isPinching.value = true
      isPanning.value = false
      initialDistance = Math.hypot(
        e.touches[0]!.clientX - e.touches[1]!.clientX,
        e.touches[0]!.clientY - e.touches[1]!.clientY
      )
      startScale = scale.value
      initialMidX = (e.touches[0]!.clientX + e.touches[1]!.clientX) / 2
      initialMidY = (e.touches[0]!.clientY + e.touches[1]!.clientY) / 2
      startTranslateX = translateX.value
      startTranslateY = translateY.value
      e.stopPropagation()
    } else if (e.touches.length === 1 && scale.value > 1) {
      isPanning.value = true
      isPinching.value = false
      panStartX = e.touches[0]!.clientX - translateX.value
      panStartY = e.touches[0]!.clientY - translateY.value
      e.stopPropagation()
    }
  }

  function onTouchMove(e: TouchEvent) {
    if (isPinching.value && e.touches.length === 2) {
      e.stopPropagation()
      if (e.cancelable) e.preventDefault()
      
      const currentDistance = Math.hypot(
        e.touches[0]!.clientX - e.touches[1]!.clientX,
        e.touches[0]!.clientY - e.touches[1]!.clientY
      )
      
      const deltaDistance = currentDistance - initialDistance
      scale.value = Math.min(Math.max(startScale + deltaDistance / 80, 1), 4)

      const currentMidX = (e.touches[0]!.clientX + e.touches[1]!.clientX) / 2
      const currentMidY = (e.touches[0]!.clientY + e.touches[1]!.clientY) / 2
      translateX.value = startTranslateX + (currentMidX - initialMidX)
      translateY.value = startTranslateY + (currentMidY - initialMidY)
    } else if (isPanning.value && e.touches.length === 1 && scale.value > 1) {
      e.stopPropagation()
      if (e.cancelable) e.preventDefault()
      translateX.value = e.touches[0]!.clientX - panStartX
      translateY.value = e.touches[0]!.clientY - panStartY
    }
  }

  function onTouchEnd(e: TouchEvent) {
    if (isPinching.value || isPanning.value) {
      e.stopPropagation()
    }

    if (e.touches.length === 0) {
      isPinching.value = false
      isPanning.value = false
      if (scale.value <= 1.05) {
        reset()
      }
    } else if (e.touches.length === 1 && scale.value > 1) {
      isPinching.value = false
      isPanning.value = true
      panStartX = e.touches[0]!.clientX - translateX.value
      panStartY = e.touches[0]!.clientY - translateY.value
    }
  }

  function reset() {
    scale.value = 1
    translateX.value = 0
    translateY.value = 0
    isPinching.value = false
    isPanning.value = false
  }

  return {
    scale,
    translateX,
    translateY,
    isPinching,
    isPanning,
    onTouchStart,
    onTouchMove,
    onTouchEnd,
    reset
  }
}
