"""Deterministic calculations for calendar-year, consolidated YTD flows."""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
import csv
from urllib.parse import urlsplit

FLOW_METRICS = ("revenue", "parent_net_profit", "operating_cashflow", "capex")

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
    verification: str = "unverified"
    evidence_locator: str = ""
    unit_basis: str = "not_recorded"
    publication_basis: str = "source_reported_date"
    source_quality: str = "unclassified"

    @property
    def key(self):
        return (self.entity_id, self.period_end, self.metric, self.currency, self.scope)

    @property
    def ref(self):
        return "|".join(str(part) for part in self.key)


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
                if row["metric"] not in FLOW_METRICS:
                    raise DataError("Unsupported flow metric")
                url = urlsplit(row["source_url"])
                if url.scheme not in {"http", "https"} or not url.netloc or url.username or url.password:
                    raise DataError("Source URL must be HTTP(S) without embedded credentials")
                metadata = {name: row.get(name, "").strip() or default for name, default in (
                    ("verification", "unverified"), ("evidence_locator", ""),
                    ("unit_basis", "not_recorded"), ("publication_basis", "source_reported_date"),
                    ("source_quality", "unclassified"))}
                if metadata["verification"] not in {"unverified", "checked_against_disclosure"}:
                    raise DataError("Unknown verification status")
                if metadata["source_quality"] not in {"unclassified", "disclosure", "supplier_evidence", "tool_description"}:
                    raise DataError("Unknown source quality")
                if metadata["verification"] == "checked_against_disclosure" and not metadata["evidence_locator"]:
                    raise DataError("Checked facts require an evidence locator")
                result.append(Fact(row["entity_id"], end, pub, row["metric"], value,
                                   row["currency"], row["source_id"], row["source_url"], **metadata))
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
        if current < 0:
            return {"value": None, "status": "turn_to_loss"}
        return {"value": (current - prior) / prior, "status": "positive_base"}
    if prior == 0:
        return {"value": None, "status": "zero_base"}
    status = "turnaround" if current >= 0 else ("loss_widening" if current < prior else "loss_narrowing")
    return {"value": None, "status": status}


def required_periods(end, mode):
    if mode == "ytd" or (mode == "quarter" and end.month == 3) or (mode == "ttm" and end.month == 12):
        return [end]
    if mode == "quarter":
        month, day = {6: (3,31), 9: (6,30), 12: (9,30)}[end.month]
        return [end, date(end.year, month, day)]
    return [date(end.year - 1, 12, 31), end, date(end.year - 1, end.month, end.day)]


def observation(values, end, mode):
    required = required_periods(end, mode)
    evidence = [values[d] for d in required if d in values]
    missing = [d.isoformat() for d in required if d not in values or values[d].value is None]
    if missing:
        status = "missing_field" if not values else (
            "missing_periods" if any(d not in values for d in required) else "missing_value")
        return None, evidence, status, missing
    if mode == "quarter":
        value = single_quarter(values, end)
    elif mode == "ttm":
        value = ttm(values, end)[0]
    else:
        value = values[end].value
    return value, evidence, "available", []


def calculate(facts, as_of):
    selected = as_of_facts(facts, as_of)
    if not selected:
        raise DataError("No facts available at the requested as-of date")
    output, warnings, issues = [], [], []

    def emit(entity, currency, end, name, value, evidence, unit, status="available", missing=None):
        item = {"entity_id":entity, "currency":currency, "period_end":end.isoformat(), "metric":name,
                "value":str(value) if value is not None else None, "unit":unit,
                "source_ids":sorted({f.source_id for f in evidence}), "status":status,
                "fact_refs":sorted({f.ref for f in evidence}),
                "missing_periods":sorted(set(missing or []))}
        output.append(item)
        if value is None:
            issues.append({"entity_id":entity, "currency":currency, "period_end":end.isoformat(),
                           "metric":name, "status":status, "missing_periods":item["missing_periods"]})
            if status not in {"zero_base", "turnaround", "turn_to_loss", "loss_widening", "loss_narrowing"}:
                warnings.append(f"{entity}/{currency}/{end}/{name}: {status}")
    for entity, currency in sorted({(f.entity_id, f.currency) for f in selected}):
        all_ends = sorted({f.period_end for f in selected if (f.entity_id, f.currency) == (entity,currency)})
        for end in all_ends:
            calculated = {}
            for name in FLOW_METRICS:
                values = series(selected, entity, name, currency)
                for mode in ("ytd", "quarter", "ttm"):
                    value, evidence, status, missing = observation(values, end, mode)
                    emit(entity, currency, end, name+"_"+mode, value, evidence, currency, status, missing)
                    if mode == "ttm":
                        calculated[name] = (value, evidence, missing)
                    prior_end = date(end.year-1, end.month, end.day)
                    prior, prior_src, _, prior_missing = observation(values, prior_end, mode)
                    change = growth(value, prior)
                    change_status = change["status"]
                    if change_status == "missing":
                        change_status = status if value is None else "missing_prior_year"
                    emit(entity, currency, end, name+"_"+mode+"_yoy", change["value"],
                         evidence+prior_src, "ratio", change_status, missing+prior_missing)
            revenue, r_src, r_missing = calculated["revenue"]
            profit, p_src, p_missing = calculated["parent_net_profit"]
            cfo, c_src, c_missing = calculated["operating_cashflow"]
            capex, x_src, x_missing = calculated["capex"]
            for name, value, evidence, unit, missing in (
                ("parent_net_margin_ttm", profit / revenue if revenue is not None and revenue > 0 and profit is not None else None, r_src+p_src, "ratio", r_missing+p_missing),
                ("free_cashflow_ttm", cfo-capex if cfo is not None and capex is not None else None, c_src+x_src, currency, c_missing+x_missing),
            ):
                status = "available" if value is not None else (
                    "zero_revenue" if name == "parent_net_margin_ttm" and revenue == 0 else "missing_dependencies")
                emit(entity,currency,end,name,value,evidence,unit,status,missing)
    counts = {}
    for issue in issues:
        counts[issue["status"]] = counts.get(issue["status"],0)+1
    return output, {"status":"partial" if warnings else "passed", "as_of":as_of.isoformat(),
                    "input_facts":len(facts), "selected_facts":len(selected),
                    "excluded_future_facts":sum(f.published_at > as_of for f in facts),
                    "warnings": warnings, "issues":issues, "issue_counts":counts,
                    "scope":"calendar_year_consolidated_ytd_flows"}

