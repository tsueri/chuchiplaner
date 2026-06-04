export class DurationSerializer {
  static formatHuman(minutes: number | null): string | null {
    if (minutes === null) return null
    if (minutes < 60) return `${minutes} min`
    const hours = Math.floor(minutes / 60)
    const mins = minutes % 60
    if (mins === 0) return `${hours} Std.`
    return `${hours} Std. ${mins} min`
  }

  static parseHuman(human: string | null): number | null {
    if (human === null) return null
    const text = human.trim()
    if (text === "") return null

    const clockMatch = text.match(/^(\d+):(\d{1,2})$/)
    if (clockMatch) {
      const h = Number(clockMatch[1])
      const m = Number(clockMatch[2])
      return h * 60 + m
    }

    let total = 0
    let matchedAny = false

    const stdMatch = text.match(/(\d+(?:[.,]\d+)?)\s*Std\.?/)
    if (stdMatch) {
      total += Math.round(Number(stdMatch[1].replace(",", ".")) * 60)
      matchedAny = true
    }

    const hMatch = text.match(/(\d+(?:[.,]\d+)?)\s*h(?!\w)/)
    if (hMatch) {
      total += Math.round(Number(hMatch[1].replace(",", ".")) * 60)
      matchedAny = true
    }

    const minMatch = text.match(/(\d+(?:[.,]\d+)?)\s*min/)
    if (minMatch) {
      total += Math.round(Number(minMatch[1].replace(",", ".")))
      matchedAny = true
    }

    const mMatch = text.match(/(\d+(?:[.,]\d+)?)\s*m(?!\w)/)
    if (mMatch) {
      total += Math.round(Number(mMatch[1].replace(",", ".")))
      matchedAny = true
    }

    if (!matchedAny) return null
    return total
  }
}
