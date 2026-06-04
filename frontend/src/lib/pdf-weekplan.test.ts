import { describe, it, expect } from "vitest"
import jsPDF from "jspdf"
import { populatePdf, embedQrCode } from "./pdf-weekplan"
import type { WeekPlanPdfSlot } from "./pdf-weekplan"

function pdfText(doc: jsPDF): string {
  const dataUri = doc.output("datauristring")
  const base64 = dataUri.split("base64,")[1]
  return atob(base64)
}

function makeSlot(
  dayOfWeek: number,
  mealType: string,
  recipeTitle: string,
  portions: number,
): WeekPlanPdfSlot {
  return { dayOfWeek, mealType, recipeTitle, portions }
}

describe("populatePdf", () => {
  it("includes the week label as title", () => {
    const doc = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" })
    populatePdf(doc, { weekLabel: "KW 23, 2.\u20138.6", slots: [] })
    const raw = pdfText(doc)
    expect(raw).toContain("(KW 23,")
  })

  it("includes day and meal header combined", () => {
    const doc = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" })
    populatePdf(doc, {
      weekLabel: "KW 23",
      slots: [makeSlot(0, "lunch", "Spaghetti", 2)],
    })
    const raw = pdfText(doc)
    expect(raw).toContain("(Montag Mittag)")
  })

  it("includes recipe title", () => {
    const doc = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" })
    populatePdf(doc, {
      weekLabel: "KW 23",
      slots: [makeSlot(0, "lunch", "Spaghetti Bolognese", 4)],
    })
    const raw = pdfText(doc)
    expect(raw).toContain("(Spaghetti Bolognese)")
  })

  it("includes portions", () => {
    const doc = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" })
    populatePdf(doc, {
      weekLabel: "KW 23",
      slots: [makeSlot(0, "lunch", "Spaghetti", 3)],
    })
    const raw = pdfText(doc)
    expect(raw).toContain("(3 Port.)")
  })

  it("truncates long recipe titles at 50 chars", () => {
    const doc = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" })
    const longTitle = "A".repeat(60)
    populatePdf(doc, {
      weekLabel: "KW 23",
      slots: [makeSlot(0, "lunch", longTitle, 1)],
    })
    const raw = pdfText(doc)
    // Should have 50 A's + ellipsis, not all 60 A's
    const match = raw.match(/\(A+[\u2026\u0085]/)
    expect(match).toBeTruthy()
    expect(match![0]).toContain("A".repeat(50))
    expect(match![0]).not.toContain("A".repeat(51))
  })

  it("renders multiple slots", () => {
    const doc = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" })
    populatePdf(doc, {
      weekLabel: "KW 23",
      slots: [
        makeSlot(0, "lunch", "Spaghetti", 2),
        makeSlot(0, "dinner", "Salat", 1),
        makeSlot(1, "lunch", "Pizza", 4),
      ],
    })
    const raw = pdfText(doc)
    expect(raw).toContain("(Salat)")
    expect(raw).toContain("(Pizza)")
  })

  it("uses all day labels including Sunday", () => {
    const doc = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" })
    populatePdf(doc, {
      weekLabel: "KW 23",
      slots: [makeSlot(6, "lunch", "Braten", 2)],
    })
    const raw = pdfText(doc)
    expect(raw).toContain("(Sonntag Mittag)")
  })

  it("falls back to raw meal type for unknown types", () => {
    const doc = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" })
    populatePdf(doc, {
      weekLabel: "KW 23",
      slots: [makeSlot(0, "snack", "Apfel", 1)],
    })
    const raw = pdfText(doc)
    expect(raw).toContain("(Montag snack)")
  })
})

describe("embedQrCode", () => {
  it("embeds QR image and label for a public URL", async () => {
    const doc = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" })
    await embedQrCode(doc, "https://example.com/plan/test/2025/kw23", 50)
    const raw = pdfText(doc)
    expect(raw).toContain("\u00D6ffentlicher")
  })
})
