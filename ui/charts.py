"""Pure Altair chart builders (no Streamlit calls, no model logic)."""
from __future__ import annotations

import altair as alt
import pandas as pd

from bloodtypelab.config import ShockConfig

HEIGHT = 320


def _x() -> alt.X:
    """Shared year axis: exactly the simulated range (no 'nice' rounding beyond the horizon)."""
    return alt.X("step:Q", title="Year", scale=alt.Scale(nice=False, zero=True))


def _scale(colors: dict[str, str]) -> alt.Scale:
    return alt.Scale(domain=list(colors), range=list(colors.values()))


def to_long(df: pd.DataFrame, columns: dict[str, str], value_name: str = "value", scale: float = 100.0) -> pd.DataFrame:
    """Wide share columns -> long (step, category, value*scale)."""
    sub = df[["step", *columns]].rename(columns=columns)
    long = sub.melt(id_vars="step", var_name="category", value_name=value_name)
    long[value_name] = long[value_name] * scale
    return long


def shock_layer(shocks: tuple[ShockConfig, ...] | list[ShockConfig]) -> alt.Chart | None:
    if not shocks:
        return None
    rows = []
    for s in shocks:
        rows.append({"step": s.start_step, "end": s.start_step + s.duration_steps - 1, "shock": s.describe(), "kind": s.kind})
    data = pd.DataFrame(rows)
    span = alt.Chart(data).mark_rect(opacity=0.10, color="#B4234A").encode(
        x=_x(), x2="end:Q", tooltip=[alt.Tooltip("shock:N", title="Shock")]
    )
    rule = alt.Chart(data).mark_rule(strokeDash=[4, 3], color="#B4234A", strokeWidth=1.5).encode(
        x=_x(), tooltip=[alt.Tooltip("shock:N", title="Shock"), alt.Tooltip("step:Q", title="Starts in year")]
    )
    return span + rule


def lines(long: pd.DataFrame, colors: dict[str, str], y_title: str, shocks=(), legend_title: str = "",
          height: int = HEIGHT, zero: bool = False, fmt: str = ".1f") -> alt.LayerChart | alt.Chart:
    base = alt.Chart(long).mark_line(strokeWidth=2.2).encode(
        x=_x(),
        y=alt.Y("value:Q", title=y_title, scale=alt.Scale(zero=zero)),
        color=alt.Color("category:N", scale=_scale(colors), title=legend_title, legend=alt.Legend(orient="top")),
        tooltip=[
            alt.Tooltip("step:Q", title="Year"),
            alt.Tooltip("category:N", title=legend_title or "Category"),
            alt.Tooltip("value:Q", title=y_title, format=fmt),
        ],
    )
    # Direct labels at the last point so the chart does not rely on colour alone.
    last = long[long.step == long.step.max()]
    labels = alt.Chart(last).mark_text(align="left", dx=6, fontWeight=600).encode(
        x=_x(), y="value:Q", text="category:N", color=alt.Color("category:N", scale=_scale(colors), legend=None)
    )
    chart = base + labels
    layer = shock_layer(shocks)
    if layer is not None:
        chart = layer + chart
    return chart.properties(height=height)


def stacked_area(long: pd.DataFrame, colors: dict[str, str], y_title: str, shocks=(), legend_title: str = "",
                 height: int = HEIGHT) -> alt.LayerChart | alt.Chart:
    order = {k: i for i, k in enumerate(colors)}
    data = long.assign(order=long["category"].map(order))
    area = alt.Chart(data).mark_area(opacity=0.9).encode(
        x=_x(),
        y=alt.Y("value:Q", title=y_title, stack="zero", scale=alt.Scale(domain=[0, 100])),
        color=alt.Color("category:N", scale=_scale(colors), title=legend_title, legend=alt.Legend(orient="top")),
        order=alt.Order("order:Q"),
        tooltip=[
            alt.Tooltip("step:Q", title="Year"),
            alt.Tooltip("category:N", title=legend_title or "Category"),
            alt.Tooltip("value:Q", title=y_title, format=".2f"),
        ],
    )
    layer = shock_layer(shocks)
    chart = area if layer is None else area + layer
    return chart.properties(height=height)


def band(summary: pd.DataFrame, colors: dict[str, str], y_title: str, title: str = "", shocks=(),
         height: int = 260, zero_rule: bool = False, legend: bool = True) -> alt.LayerChart:
    """summary columns: step, scenario, mean, p025, p975 (already scaled)."""
    sc = _scale(colors)
    area = alt.Chart(summary).mark_area(opacity=0.18).encode(
        x=_x(),
        y=alt.Y("p025:Q", title=y_title, scale=alt.Scale(zero=False)),
        y2="p975:Q",
        color=alt.Color("scenario:N", scale=sc, title="Scenario", legend=alt.Legend(orient="top") if legend else None),
    )
    line = alt.Chart(summary).mark_line(strokeWidth=2.2).encode(
        x=_x(),
        y="mean:Q",
        color=alt.Color("scenario:N", scale=sc, title="Scenario", legend=alt.Legend(orient="top") if legend else None),
        tooltip=[
            alt.Tooltip("scenario:N", title="Scenario"),
            alt.Tooltip("step:Q", title="Year"),
            alt.Tooltip("mean:Q", title="Mean", format=".2f"),
            alt.Tooltip("p025:Q", title="2.5th pct", format=".2f"),
            alt.Tooltip("p975:Q", title="97.5th pct", format=".2f"),
        ],
    )
    chart = area + line
    if zero_rule:
        chart = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color="#888", strokeDash=[2, 2]).encode(y="y:Q") + chart
    layer = shock_layer(shocks)
    if layer is not None:
        chart = layer + chart
    return chart.properties(height=height, title=title)


def grouped_bars(df: pd.DataFrame, x: str, value: str, group: str, colors: dict[str, str] | None,
                 y_title: str, height: int = 280, x_sort: list[str] | None = None, fmt: str = ".1f") -> alt.Chart:
    color = alt.Color(f"{group}:N", title="", legend=alt.Legend(orient="top"))
    if colors:
        color = alt.Color(f"{group}:N", scale=_scale(colors), title="", legend=alt.Legend(orient="top"))
    return alt.Chart(df).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
        x=alt.X(f"{x}:N", title=None, sort=x_sort, axis=alt.Axis(labelAngle=0)),
        xOffset=alt.XOffset(f"{group}:N", sort=list(colors) if colors else None),
        y=alt.Y(f"{value}:Q", title=y_title),
        color=color,
        tooltip=[alt.Tooltip(f"{x}:N"), alt.Tooltip(f"{group}:N"), alt.Tooltip(f"{value}:Q", format=fmt)],
    ).properties(height=height)


def age_pyramid(agents: pd.DataFrame, colors: dict[str, str] | None = None, height: int = 300) -> alt.Chart:
    df = agents.copy()
    df["age_group"] = (df["age"] // 5) * 5
    g = df.groupby(["age_group", "sex"]).size().reset_index(name="count")
    g["signed"] = g.apply(lambda r: -r["count"] if r["sex"] == "M" else r["count"], axis=1)
    g["label"] = g["age_group"].astype(int).astype(str) + "-" + (g["age_group"] + 4).astype(int).astype(str)
    sex_colors = {"F": "#B4234A", "M": "#0072B2"}
    return alt.Chart(g).mark_bar().encode(
        y=alt.Y("age_group:O", sort="descending", title="Age group", axis=alt.Axis(labelExpr="datum.value + '-' + (datum.value + 4)")),
        x=alt.X("signed:Q", title="Men  |  Women", axis=alt.Axis(labelExpr="abs(datum.value)")),
        color=alt.Color("sex:N", scale=_scale(sex_colors), title="Sex", legend=alt.Legend(orient="top")),
        tooltip=[alt.Tooltip("label:N", title="Age"), alt.Tooltip("sex:N", title="Sex"), alt.Tooltip("count:Q", title="Agents")],
    ).properties(height=height)


def population_and_events(ts: pd.DataFrame, shocks=(), height: int = 260) -> tuple[alt.Chart, alt.Chart]:
    pop = alt.Chart(ts).mark_line(color="#B4234A", strokeWidth=2.4).encode(
        x=_x(),
        y=alt.Y("population:Q", title="Living agents", scale=alt.Scale(zero=False)),
        tooltip=[alt.Tooltip("step:Q", title="Year"), alt.Tooltip("population:Q", title="Population", format=",")],
    )
    layer = shock_layer(shocks)
    pop_chart = (pop if layer is None else layer + pop).properties(height=height)
    ev_cols = {
        "births": "Births",
        "deaths_natural": "Deaths (baseline)",
        "deaths_disease": "Deaths (disease excess)",
        "deaths_bottleneck": "Deaths (bottleneck)",
        "immigrants": "Immigrants",
        "fetal_losses": "Fetal losses (Rh-HDN)",
    }
    present = {k: v for k, v in ev_cols.items() if ts[k].sum() > 0 or k in ("births", "deaths_natural")}
    long = ts[["step", *present]].rename(columns=present).melt("step", var_name="event", value_name="count")
    colors = {
        "Births": "#009E73",
        "Deaths (baseline)": "#6B6166",
        "Deaths (disease excess)": "#D55E00",
        "Deaths (bottleneck)": "#CC79A7",
        "Immigrants": "#0072B2",
        "Fetal losses (Rh-HDN)": "#E69F00",
    }
    colors = {k: v for k, v in colors.items() if k in present.values()}
    ev = alt.Chart(long).mark_line(strokeWidth=1.6).encode(
        x=_x(),
        y=alt.Y("count:Q", title="People per year", scale=alt.Scale(type="symlog")),
        color=alt.Color("event:N", scale=_scale(colors), title="", legend=alt.Legend(orient="top")),
        tooltip=[alt.Tooltip("step:Q", title="Year"), alt.Tooltip("event:N"), alt.Tooltip("count:Q", format=",")],
    ).properties(height=height)
    return pop_chart, ev


def docking_chart(band_df: pd.DataFrame, al: pd.DataFrame, metric_label: str, height: int = 230) -> alt.LayerChart:
    area = alt.Chart(band_df).mark_area(opacity=0.22, color="#6B6166").encode(
        x=_x(), y=alt.Y("p025:Q", title=metric_label, scale=alt.Scale(zero=False)), y2="p975:Q"
    )
    mean = alt.Chart(band_df).mark_line(color="#6B6166", strokeWidth=2).encode(x=_x(), y="mean:Q")
    al_lines = alt.Chart(al).mark_line(color="#B4234A", strokeWidth=1.3, opacity=0.85).encode(
        x=_x(), y="value:Q", detail="replicate:N",
        tooltip=[alt.Tooltip("replicate:N", title="AnyLogic replicate"), alt.Tooltip("step:Q"), alt.Tooltip("value:Q", format=".2f")],
    )
    return (area + mean + al_lines).properties(height=height, title=metric_label)
