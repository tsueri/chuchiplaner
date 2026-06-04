import re


class DurationSerializer:
    @staticmethod
    def to_iso_duration(minutes: int | None) -> str | None:
        if minutes is None:
            return None
        if minutes < 0:
            minutes = 0
        hours, mins = divmod(minutes, 60)
        if hours == 0 and mins == 0:
            return "PT0M"
        if hours == 0:
            return f"PT{mins}M"
        if mins == 0:
            return f"PT{hours}H"
        return f"PT{hours}H{mins}M"

    @staticmethod
    def from_iso_duration(iso: str | None) -> int | None:
        if iso is None:
            return None
        match = re.fullmatch(
            r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?",
            iso.strip(),
        )
        if match is None:
            return None
        h, m, s = match.groups()
        if h is None and m is None and s is None:
            return None
        total = 0
        if h is not None:
            total += int(h) * 60
        if m is not None:
            total += int(m)
        if s is not None:
            total += int(s) // 60
        return total

    @staticmethod
    def format_human(minutes: int | None) -> str | None:
        if minutes is None:
            return None
        if minutes < 60:
            return f"{minutes} min"
        hours, mins = divmod(minutes, 60)
        if mins == 0:
            return f"{hours} Std."
        return f"{hours} Std. {mins} min"

    @staticmethod
    def parse_human(human: str | None) -> int | None:
        if human is None:
            return None
        text = human.strip()
        if text == "":
            return None

        clock_match = re.fullmatch(r"(\d+):(\d{1,2})", text)
        if clock_match is not None:
            h = int(clock_match.group(1))
            m = int(clock_match.group(2))
            return h * 60 + m

        total = 0
        matched_any = False

        std_match = re.search(r"(\d+(?:[.,]\d+)?)\s*Std\.?", text)
        if std_match is not None:
            hours = float(std_match.group(1).replace(",", "."))
            total += int(round(hours * 60))
            matched_any = True

        h_match = re.search(r"(\d+(?:[.,]\d+)?)\s*h(?!\w)", text)
        if h_match is not None:
            hours = float(h_match.group(1).replace(",", "."))
            total += int(round(hours * 60))
            matched_any = True

        min_match = re.search(r"(\d+(?:[.,]\d+)?)\s*min", text)
        if min_match is not None:
            total += int(round(float(min_match.group(1).replace(",", "."))))
            matched_any = True

        m_match = re.search(r"(\d+(?:[.,]\d+)?)\s*m(?!\w)", text)
        if m_match is not None:
            total += int(round(float(m_match.group(1).replace(",", "."))))
            matched_any = True

        if not matched_any:
            return None

        return total
