import { describe, it, expect } from "vitest"
import { DurationSerializer } from "./duration-serializer"

describe("DurationSerializer.formatHuman", () => {
  it("returns '0 min' for 0", () => {
    expect(DurationSerializer.formatHuman(0)).toBe("0 min")
  })

  it("returns '{n} min' for n < 60", () => {
    expect(DurationSerializer.formatHuman(45)).toBe("45 min")
  })

  it("returns '1 Std.' for exactly 60", () => {
    expect(DurationSerializer.formatHuman(60)).toBe("1 Std.")
  })

  it("returns 'X Std. Y min' for mixed values", () => {
    expect(DurationSerializer.formatHuman(90)).toBe("1 Std. 30 min")
  })

  it("returns 'X Std.' for whole hours", () => {
    expect(DurationSerializer.formatHuman(120)).toBe("2 Std.")
  })

  it("returns null when minutes is null", () => {
    expect(DurationSerializer.formatHuman(null)).toBeNull()
  })
})

describe("DurationSerializer.parseHuman", () => {
  it("parses '1h 30m' as 90", () => {
    expect(DurationSerializer.parseHuman("1h 30m")).toBe(90)
  })

  it("parses '90 min' as 90", () => {
    expect(DurationSerializer.parseHuman("90 min")).toBe(90)
  })

  it("parses '1:30' as 90 (clock format)", () => {
    expect(DurationSerializer.parseHuman("1:30")).toBe(90)
  })

  it("parses '2 Std.' as 120", () => {
    expect(DurationSerializer.parseHuman("2 Std.")).toBe(120)
  })

  it("parses '2.5h' as 150", () => {
    expect(DurationSerializer.parseHuman("2.5h")).toBe(150)
  })

  it("returns null for garbage", () => {
    expect(DurationSerializer.parseHuman("garbage")).toBeNull()
  })

  it("returns null for empty string", () => {
    expect(DurationSerializer.parseHuman("")).toBeNull()
  })

  it("returns null for null input", () => {
    expect(DurationSerializer.parseHuman(null)).toBeNull()
  })
})
