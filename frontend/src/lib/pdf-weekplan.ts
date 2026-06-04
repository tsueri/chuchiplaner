import jsPDF from "jspdf"
import QRCode from "qrcode"

const DAY_LABELS: Record<number, string> = {
  0: "Montag",
  1: "Dienstag",
  2: "Mittwoch",
  3: "Donnerstag",
  4: "Freitag",
  5: "Samstag",
  6: "Sonntag",
}

const MEAL_LABELS: Record<string, string> = {
  breakfast: "Fr\u00fchst\u00fcck",
  lunch: "Mittag",
  dinner: "Abend",
  dessert: "Dessert",
}

export interface WeekPlanPdfSlot {
  dayOfWeek: number
  mealType: string
  recipeTitle: string
  portions: number
}

export interface WeekPlanPdfOptions {
  weekLabel: string
  slots: WeekPlanPdfSlot[]
  publicUrl: string | null
  fileName?: string
}

const PAGE_WIDTH = 210
const PAGE_HEIGHT = 297
const MARGIN = 20
const TRUNCATE_AT = 50
const TRUNCATE_AT_TWO_COL = 30
const MAX_MEAL_HEIGHT = 215

const MEAL_ORDER: Record<string, number> = {
  breakfast: 0,
  lunch: 1,
  dinner: 2,
  dessert: 3,
}

function truncate(text: string, max: number): string {
  if (text.length <= max) return text
  return text.substring(0, max) + "\u2026"
}

function slotColumnHeight(slots: WeekPlanPdfSlot[]): number {
  let h = 0
  let prevDay: number | null = null
  for (const s of slots) {
    if (prevDay !== null && s.dayOfWeek !== prevDay) h += 6
    prevDay = s.dayOfWeek
    h += 17
  }
  return h
}

function renderColumn(
  doc: jsPDF,
  slots: WeekPlanPdfSlot[],
  x: number,
  width: number,
  yStart: number,
  truncateAt: number,
): void {
  let y = yStart
  let prevDay: number | null = null
  const cx = x + width / 2

  for (const slot of slots) {
    if (prevDay !== null && slot.dayOfWeek !== prevDay) {
      doc.setDrawColor(200)
      doc.line(x + 5, y, x + width - 5, y)
      y += 6
    }
    prevDay = slot.dayOfWeek

    const header = `${DAY_LABELS[slot.dayOfWeek] || ""} ${MEAL_LABELS[slot.mealType] || slot.mealType}`
    doc.setFont("Times", "Bold")
    doc.setFontSize(11)
    doc.text(header, cx, y, { align: "center" })
    y += 7

    doc.setFont("Times", "Normal")
    doc.setFontSize(10)
    doc.text(truncate(slot.recipeTitle, truncateAt), cx, y, {
      align: "center",
    })
    y += 10
  }
}

export function populatePdf(
  doc: jsPDF,
  options: { weekLabel: string; slots: WeekPlanPdfSlot[] },
): void {
  const yStart = MARGIN

  doc.setFont("Times", "Bold")
  doc.setFontSize(16)
  doc.text(options.weekLabel, PAGE_WIDTH / 2, yStart, { align: "center" })

  doc.setDrawColor(150)
  const ruleY = yStart + 12
  doc.line(MARGIN, ruleY, PAGE_WIDTH - MARGIN, ruleY)

  const mealsY = ruleY + 10
  const slots = [...options.slots].sort((a, b) => {
    if (a.dayOfWeek !== b.dayOfWeek) return a.dayOfWeek - b.dayOfWeek
    return (MEAL_ORDER[a.mealType] ?? 9) - (MEAL_ORDER[b.mealType] ?? 9)
  })

  if (slots.length === 0) return

  const needsTwoCol = slotColumnHeight(slots) > MAX_MEAL_HEIGHT

  if (!needsTwoCol) {
    const colWidth = PAGE_WIDTH - 2 * MARGIN
    renderColumn(doc, slots, MARGIN, colWidth, mealsY, TRUNCATE_AT)
    return
  }

  const mid = Math.ceil(slots.length / 2)
  const colWidth = (PAGE_WIDTH - 2 * MARGIN - 10) / 2
  const leftX = MARGIN
  const rightX = MARGIN + colWidth + 10

  renderColumn(doc, slots.slice(0, mid), leftX, colWidth, mealsY, TRUNCATE_AT_TWO_COL)
  renderColumn(doc, slots.slice(mid), rightX, colWidth, mealsY, TRUNCATE_AT_TWO_COL)
}

export async function embedQrCode(doc: jsPDF, url: string): Promise<void> {
  const qrSize = 20
  const qrMargin = 15
  const qrX = PAGE_WIDTH - qrMargin - qrSize
  const qrY = PAGE_HEIGHT - qrMargin - qrSize - 5

  const qrDataUrl = await QRCode.toDataURL(url, {
    width: 120,
    margin: 0,
  })
  doc.addImage(qrDataUrl, "PNG", qrX, qrY, qrSize, qrSize)

  doc.setFont("Times", "Italic")
  doc.setFontSize(7)
  doc.text("\u00D6ffentlicher Link", qrX + qrSize / 2, qrY + qrSize + 3, {
    align: "center",
  })
}

export async function generateWeekPlanPdf(
  options: WeekPlanPdfOptions,
): Promise<void> {
  const doc = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" })

  populatePdf(doc, {
    weekLabel: options.weekLabel,
    slots: options.slots,
  })

  if (options.publicUrl) {
    await embedQrCode(doc, options.publicUrl)
  }

  doc.setFont("Times", "Italic")
  doc.setFontSize(8)
  doc.text(
    "Erstellt mit Chuchiplaner",
    PAGE_WIDTH / 2,
    PAGE_HEIGHT - 10,
    { align: "center" },
  )

  doc.save(options.fileName || "wochenplan.pdf")
}
