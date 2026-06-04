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
const TRUNCATE_AT = 50

function truncate(text: string): string {
  if (text.length <= TRUNCATE_AT) return text
  return text.substring(0, TRUNCATE_AT) + "\u2026"
}

export function populatePdf(
  doc: jsPDF,
  options: { weekLabel: string; slots: WeekPlanPdfSlot[] },
): number {
  const margin = 20
  let y = margin

  doc.setFont("Times", "Bold")
  doc.setFontSize(16)
  doc.text(options.weekLabel, PAGE_WIDTH / 2, y, { align: "center" })
  y += 12

  doc.setDrawColor(150)
  doc.line(margin, y, PAGE_WIDTH - margin, y)
  y += 10

  let currentDay: number | null = null
  for (const slot of options.slots) {
    if (currentDay !== null && slot.dayOfWeek !== currentDay) {
      doc.setDrawColor(200)
      doc.line(margin + 10, y, PAGE_WIDTH - margin - 10, y)
      y += 6
    }
    currentDay = slot.dayOfWeek

    const header = `${DAY_LABELS[slot.dayOfWeek] || ""} ${MEAL_LABELS[slot.mealType] || slot.mealType}`
    doc.setFont("Times", "Bold")
    doc.setFontSize(11)
    doc.text(header, PAGE_WIDTH / 2, y, { align: "center" })
    y += 7

    doc.setFont("Times", "Normal")
    doc.setFontSize(10)
    doc.text(truncate(slot.recipeTitle), PAGE_WIDTH / 2, y, {
      align: "center",
    })
    y += 10
  }

  return y
}

export async function embedQrCode(doc: jsPDF, url: string): Promise<void> {
  const qrSize = 20
  const margin = 15
  const qrX = PAGE_WIDTH - margin - qrSize
  const qrY = PAGE_HEIGHT - margin - qrSize - 5

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
