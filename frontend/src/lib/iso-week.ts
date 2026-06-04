/**
 * ISO week date helpers — uses the standard "Thursday determines ISO year"
 * algorithm.  Week 1 is the week containing the first Thursday of the year.
 *
 * Mon = 1 … Sun = 7 throughout this module, matching the ISO standard.
 */
function dayOfWeekMon1(d: Date): number {
  return d.getDay() || 7
}

/** Monday 00:00 of the given ISO week/year. */
export function isoWeekMonday(year: number, week: number): Date {
  const jan4 = new Date(year, 0, 4)
  const jan4Dow = dayOfWeekMon1(jan4)
  const monday = new Date(jan4)
  monday.setDate(jan4.getDate() - jan4Dow + 1 + (week - 1) * 7)
  monday.setHours(0, 0, 0, 0)
  return monday
}

/** [isoYear, isoWeek] for a given date. */
export function getIsoWeek(date: Date): [number, number] {
  const d = new Date(date)
  d.setHours(0, 0, 0, 0)

  // Thursday in the same ISO week — its calendar year IS the ISO year.
  const thursday = new Date(d)
  thursday.setDate(d.getDate() + 4 - dayOfWeekMon1(d))
  const isoYear = thursday.getFullYear()

  // Week 1 starts on the Monday before the first Thursday of isoYear.
  const jan4 = new Date(isoYear, 0, 4)
  const jan4Dow = dayOfWeekMon1(jan4)
  const week1Monday = new Date(jan4)
  week1Monday.setDate(jan4.getDate() - jan4Dow + 1)

  const diff = Math.round(
    (d.getTime() - week1Monday.getTime()) / 86_400_000,
  )
  return [isoYear, Math.floor(diff / 7) + 1]
}

export function getCurrentIsoWeek(): [number, number] {
  return getIsoWeek(new Date())
}

/** Swiss-style label like "KW 23, 2.–8.6" */
export function formatWeekLabel(year: number, week: number): string {
  const monday = isoWeekMonday(year, week)
  const sunday = new Date(monday)
  sunday.setDate(monday.getDate() + 6)
  return (
    `KW ${week}, ${monday.getDate()}.` +
    `\u2013${sunday.getDate()}.${sunday.getMonth() + 1}`
  )
}
