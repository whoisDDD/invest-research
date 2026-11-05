"""Deterministic calculations for calendar-year, consolidated YTD flows."""
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal, InvalidOperation
import csv

SCALES = {Decimal(n) for n in ("1", "1000", "10000", "1000000", "100000000")}
REQUIRED = {"entity_id", "period_end", "published_at", "metric", "value",
            "currency", "scale", "scope", "period_type", "source_id", "source_url"}


class DataError(ValueError):
    pass


@dataclass(frozen=True)
class Fact:
    entity_id: str
    period_end: date
    published_at: date
    metric: str
    value: Decimal | None
    currency: str
    source_id: str
    source_url: str
    scope: str = "consolidated"
    period_type: str = "ytd"

    @property
    def key(self):
        return (self.entity_id, self.period_end, self.metric, self.currency, self.scope)


def load_facts(path):
    result = []
    with open(path, encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not REQUIRED <= set(reader.fieldnames or []):
            raise DataError("Missing required CSV columns")
        for line, row in enumerate(reader, 2):
            try:
                for field in REQUIRED - {"value"}:
                    if not row.get(field, "").strip():
                        raise DataError("Empty required field: " + field)
                end, pub = date.fromisoformat(row["period_end"]), date.fromisoformat(row["published_at"])
                if end > pub:
                    raise DataError("Period ends after publication")
                if (end.month, end.day) not in {(3,31),(6,30),(9,30),(12,31)}:
                    raise DataError("Only calendar-quarter YTD flows supported")
                if row["scope"] != "consolidated" or row["period_type"] != "ytd":
                    raise DataError("Only consolidated YTD flows supported")
                scale = Decimal(row["scale"])
                if scale not in SCALES:
                    raise DataError("Unsupported scale")
                value = Decimal(row["value"]) * scale if row["value"].strip() else None
                if value is not None and not value.is_finite():
                    raise DataError("Non-finite value")
                if row["metric"] in {"revenue", "capex"} and value is not None and value < 0:
                    raise DataError("Revenue and capex must be non-negative")
                result.append(Fact(row["entity_id"], end, pub, row["metric"], value,
                                   row["currency"], row["source_id"], row["source_url"]))
            except (ValueError, InvalidOperation) as exc:
                raise DataError(f"CSV line {line}: {exc}") from exc
    if not result:
        raise DataError("Empty input")
    return result


def as_of_facts(facts, as_of):
    selected = {}
    for fact in facts:
        if fact.published_at > as_of:
            continue
        previous = selected.get(fact.key)
        if previous is None or fact.published_at > previous.published_at:
            selected[fact.key] = fact
        elif fact.published_at == previous.published_at and fact.value != previous.value:
            raise DataError("Conflicting values for the same date/key")
    return list(selected.values())


def series(facts, entity_id, metric, currency):
    return {f.period_end: f for f in facts
            if (f.entity_id, f.metric, f.currency) == (entity_id, metric, currency)}


def ttm(values, end):
    """Returns (value, evidence facts); no missing observation becomes zero."""
    latest = values.get(end)
    if latest is None or latest.value is None:
        return None, []
    if end.month == 12:
        return latest.value, [latest]
    annual = values.get(date(end.year - 1, 12, 31))
    prior = values.get(date(end.year - 1, end.month, end.day))
    if annual is None or prior is None or annual.value is None or prior.value is None:
        return None, []
    if len({f.currency for f in (latest, annual, prior)}) != 1:
        raise DataError("Mixed currencies in TTM")
    return annual.value + latest.value - prior.value, [annual, latest, prior]


def single_quarter(values, end):
    current = values.get(end)
    if current is None or current.value is None:
        return None
    if end.month == 3:
        return current.value
    months = {6: (3,31), 9: (6,30), 12: (9,30)}
    m, d = months[end.month]
    previous = values.get(date(end.year, m, d))
    if previous is None or previous.value is None:
        return None
    if current.currency != previous.currency:
        raise DataError("Mixed currencies in quarter calculation")
    return current.value - previous.value


def growth(current, prior):
    if current is None or prior is None:
        return {"value": None, "status": "missing"}
    if prior > 0:
        return {"value": (current - prior) / prior, "status": "positive_base"}
    if prior == 0:
        return {"value": None, "status": "zero_base"}
    status = "turnaround" if current >= 0 else ("loss_widening" if current < prior else "loss_narrowing")
    return {"value": None, "status": status}


def calculate(facts, as_of):
    selected = as_of_facts(facts, as_of)
    output, warnings = [], []
    for entity, currency in sorted({(f.entity_id, f.currency) for f in selected}):
        all_ends = sorted({f.period_end for f in selected if (f.entity_id, f.currency) == (entity,currency)})
        for end in all_ends:
            calculated = {}
            for name in ("revenue", "parent_net_profit", "operating_cashflow", "capex"):
                values = series(selected, entity, name, currency)
                value, evidence = ttm(values, end)
                calculated[name] = (value, evidence)
                output.append({"entity_id": entity, "period_end": end.isoformat(),
                               "metric": name + "_ttm", "value": str(value) if value is not None else None,
                               "unit": currency, "source_ids": sorted({f.source_id for f in evidence})})
                if value is None:
                    warnings.append(f"{entity}/{currency}/{end}/{name}: insufficient TTM history")
            revenue, r_src = calculated["revenue"]
            profit, p_src = calculated["parent_net_profit"]
            cfo, c_src = calculated["operating_cashflow"]
            capex, x_src = calculated["capex"]
            for name, value, evidence, unit in (
                ("parent_net_margin_ttm", profit / revenue if revenue is not None and revenue > 0 and profit is not None else None, r_src+p_src, "ratio"),
                ("free_cashflow_ttm", cfo-capex if cfo is not None and capex is not None else None, c_src+x_src, currency),
            ):
                output.append({"entity_id":entity, "period_end":end.isoformat(), "metric":name,
                               "value":str(value) if value is not None else None, "unit":unit,
                               "source_ids":sorted({f.source_id for f in evidence}) if value is not None else []})
    return output, {"status":"partial" if warnings else "passed", "as_of":as_of.isoformat(),
                    "input_facts":len(facts), "selected_facts":len(selected),
                    "excluded_future_facts":sum(f.published_at > as_of for f in facts),
                    "warnings": warnings, "scope":"calendar_year_consolidated_ytd_flows"}

