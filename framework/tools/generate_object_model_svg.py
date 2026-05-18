#!/usr/bin/env python3
"""
DRAFT Object Model SVG Generator
=================================
Reads  framework/configurations/object-model.yaml
Writes docs/assets/draft-object-model.svg

Usage:
    python framework/tools/generate_object_model_svg.py

The SVG is a generated artifact. Edit object-model.yaml, then re-run this
script — do not hand-edit the SVG directly.
"""

from __future__ import annotations
import sys
import yaml
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = REPO_ROOT / "framework" / "configurations" / "object-model.yaml"

# Layout constants
LABEL_AREA   = 28   # px reserved at section top for the label text
ROW_GAP      = 14   # vertical gap between rows within a section
SECTION_PAD  = 10   # bottom padding inside each left section
INNER_MARGIN = 10   # horizontal margin from section edge to first box
PAIR_GAP     = 20   # horizontal gap between paired boxes (2-object rows)
HEADER_H     = 26   # box header bar height
CAP_H        = 6    # box header cap strip height (bridges rx gap)
GOV_X_INSET  = 9    # left inset of governance boxes within right panel


# ──────────────────────────────────────────────────────────────────────────────
# Layout engine
# ──────────────────────────────────────────────────────────────────────────────

class LayoutEngine:
    """Computes absolute x/y positions for every box and section container."""

    def __init__(self, cfg: dict):
        self.cfg       = cfg
        self.ot        = cfg["objectTypes"]
        self.boxes: dict[str, dict]    = {}   # typeRef → geometry dict
        self.sections: dict[str, dict] = {}   # section_id → geometry dict
        self.total_height: float       = 0
        self._compute()

    # ── public helpers ────────────────────────────────────────────────────────

    def box(self, type_ref: str) -> dict:
        return self.boxes[type_ref]

    def sec(self, sec_id: str) -> dict:
        return self.sections[sec_id]

    # ── internals ─────────────────────────────────────────────────────────────

    def _compute(self):
        c    = self.cfg
        pad  = c["canvas"]["padding"]
        sgap = c["canvas"]["sectionGap"]
        pl   = c["panels"]["left"]
        pr   = c["panels"]["right"]

        # ── Left sections (stacked) ──
        cur_y = pad
        for section in c["leftSections"]:
            sx, sw = pl["x"], pl["width"]
            sy     = cur_y
            row_y  = sy + LABEL_AREA

            for row in section["rows"]:
                row_h, xs = self._layout_row(row, sx, sw)
                for obj, x in zip(row["objects"], xs):
                    t = obj["typeRef"]
                    w = self.ot[t]["width"]
                    h = self.ot[t]["height"]
                    self.boxes[t] = dict(
                        x=x, y=row_y, w=w, h=h,
                        cx=x + w / 2, cy=row_y + h / 2,
                        right=x + w, bottom=row_y + h,
                        section=section["id"],
                    )
                row_y += row_h + ROW_GAP

            sh = row_y - ROW_GAP + SECTION_PAD - sy
            self.sections[section["id"]] = dict(
                x=sx, y=sy, w=sw, h=sh,
                bottom=sy + sh,
                colorKey=section["colorKey"],
                label=section["label"],
            )
            cur_y = sy + sh + sgap

        left_bottom = cur_y - sgap   # bottom of last left section

        # ── Right section (governance) ──
        rs  = c["rightSection"]
        rsx = pr["x"]
        rsw = pr["width"]
        rsy = pad
        obj_gap = rs.get("objectGap", 8)

        # Compute natural governance content height first
        gov_content_h = (LABEL_AREA
                         + sum(self.ot[o["typeRef"]]["height"] for o in rs["objects"])
                         + (len(rs["objects"]) - 1) * obj_gap
                         + SECTION_PAD)

        # Governance section is the taller of left-panel height vs. its own content
        rsh = max(left_bottom - pad, gov_content_h)

        box_x = rsx + GOV_X_INSET
        obj_y = rsy + LABEL_AREA

        for obj in rs["objects"]:
            t = obj["typeRef"]
            w = self.ot[t]["width"]
            h = self.ot[t]["height"]
            self.boxes[t] = dict(
                x=box_x, y=obj_y, w=w, h=h,
                cx=box_x + w / 2, cy=obj_y + h / 2,
                right=box_x + w, bottom=obj_y + h,
                section=rs["id"],
            )
            obj_y += h + obj_gap

        self.sections[rs["id"]] = dict(
            x=rsx, y=rsy, w=rsw, h=rsh,
            bottom=rsy + rsh,
            colorKey=rs["colorKey"],
            label=rs["label"],
        )

        # Canvas height = tallest of left-panel bottom or governance bottom, plus bottom pad
        self.total_height = max(left_bottom, rsy + rsh) + pad

    def _layout_row(self, row: dict, sx: float, sw: float) -> tuple[float, list[float]]:
        """Return (row_height, [x_position_per_object])."""
        objects = row["objects"]
        row_h   = max(self.ot[o["typeRef"]]["height"] for o in objects)

        # Explicit xHint overrides (positions relative to panel left edge)
        if any("xHint" in o for o in objects):
            xs = [sx + o.get("xHint", 0) for o in objects]
            return row_h, xs

        n = len(objects)
        if n == 1:
            w  = self.ot[objects[0]["typeRef"]]["width"]
            xs = [sx + (sw - w) / 2]
        elif n == 2:
            # Group the pair and center it in the section
            w0 = self.ot[objects[0]["typeRef"]]["width"]
            w1 = self.ot[objects[1]["typeRef"]]["width"]
            gw = w0 + PAIR_GAP + w1
            x0 = sx + (sw - gw) / 2
            xs = [x0, x0 + w0 + PAIR_GAP]
        else:
            # Spread: equal gaps between boxes, flush to inner margins
            total_w = sum(self.ot[o["typeRef"]]["width"] for o in objects)
            avail   = sw - 2 * INNER_MARGIN
            gap     = (avail - total_w) / max(n - 1, 1)
            cur_x   = sx + INNER_MARGIN
            xs      = []
            for o in objects:
                xs.append(cur_x)
                cur_x += self.ot[o["typeRef"]]["width"] + gap

        return row_h, xs


# ──────────────────────────────────────────────────────────────────────────────
# SVG builder
# ──────────────────────────────────────────────────────────────────────────────

class SVGBuilder:
    def __init__(self, layout: LayoutEngine, cfg: dict):
        self.l   = layout
        self.cfg = cfg
        self.col = cfg["colors"]
        self._lines: list[str] = []

    # ── helpers ───────────────────────────────────────────────────────────────

    def _add(self, s: str = ""):
        self._lines.append(s)

    def _primary(self, color_key: str) -> str:
        return self.col[color_key]["primary"]

    def _bg(self, color_key: str) -> str:
        return self.col[color_key]["background"]

    def _arrow_color(self, key: str) -> str:
        return self.col["arrows"].get(key, self.col["arrows"]["default"])

    def _marker(self, color_key: str) -> str:
        return {"green": "arr-g", "purple": "arr-p", "teal": "arr-e"}.get(
            color_key, "arr"
        )

    def _line(self, x1, y1, x2, y2, stroke, sw=1.5, dash="", marker=""):
        d = f'stroke-dasharray="{dash}"' if dash else ""
        m = f'marker-end="url(#{marker})"' if marker else ""
        self._add(
            f'  <line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{stroke}" stroke-width="{sw}" {d} {m}/>'
        )

    def _text(self, x, y, text, size=9, fill="#5f564b", anchor="middle",
              italic=False, weight="normal"):
        style = 'font-style="italic"' if italic else ""
        fw    = f'font-weight="{weight}"' if weight != "normal" else ""
        self._add(
            f'  <text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" '
            f'text-anchor="{anchor}" {style} {fw}>{text}</text>'
        )

    # ── main build ────────────────────────────────────────────────────────────

    def build(self) -> str:
        w = self.cfg["canvas"]["width"]
        h = self.l.total_height
        self._add(
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="0 0 {w} {h:.0f}" width="{w}" height="{h:.0f}" '
            f'font-family="Inter, ui-sans-serif, system-ui, sans-serif">'
        )
        self._defs()
        self._sections()
        self._boxes()
        self._relationships()
        self._title()
        self._add("</svg>")
        return "\n".join(self._lines)

    # ── defs (arrowhead markers) ───────────────────────────────────────────────

    def _defs(self):
        self._add("  <defs>")
        for mid, key in [("arr", "default"), ("arr-p", "purple"),
                         ("arr-g", "green"),  ("arr-e", "teal")]:
            col = self._arrow_color(key)
            self._add(
                f'    <marker id="{mid}" markerWidth="9" markerHeight="9" '
                f'refX="8" refY="4.5" orient="auto">'
            )
            self._add(f'      <polygon points="0 0, 9 4.5, 0 9" fill="{col}"/>')
            self._add("    </marker>")
        self._add("  </defs>")
        self._add("")

    # ── section containers ────────────────────────────────────────────────────

    def _sections(self):
        for sid, sec in self.l.sections.items():
            col = self._primary(sec["colorKey"])
            bg  = self._bg(sec["colorKey"])
            self._add(f"  <!-- ══ {sec['label']} ══ -->")
            self._add(
                f'  <rect x="{sec["x"]}" y="{sec["y"]}" '
                f'width="{sec["w"]}" height="{sec["h"]:.0f}" '
                f'rx="12" fill="{bg}" stroke="{col}" '
                f'stroke-width="1.5" stroke-dasharray="7 3"/>'
            )
            self._text(
                sec["x"] + 14, sec["y"] + 18,
                sec["label"], size=10, fill=col, anchor="start", weight="700"
            )
            # Override letter-spacing inline for labels
            self._lines[-1] = self._lines[-1].replace(
                f'>{sec["label"]}<',
                f' letter-spacing="1.5">{sec["label"]}<'
            )
            self._add("")

    # ── object boxes ──────────────────────────────────────────────────────────

    def _boxes(self):
        for type_ref, box in self.l.boxes.items():
            ot  = self.cfg["objectTypes"][type_ref]
            sec = self.l.sections[box["section"]]
            col = self._primary(sec["colorKey"])
            x, y, w, h = box["x"], box["y"], box["w"], box["h"]
            cx = box["cx"]

            self._add(f"  <!-- {ot['displayName']} -->")

            # Outer rect (white body)
            self._add(
                f'  <rect x="{x:.1f}" y="{y:.1f}" width="{w}" height="{h}" '
                f'rx="6" fill="white" stroke="{col}" stroke-width="1.5"/>'
            )
            # Header fill
            self._add(
                f'  <rect x="{x:.1f}" y="{y:.1f}" width="{w}" height="{HEADER_H}" '
                f'rx="6" fill="{col}"/>'
            )
            # Header cap (covers the rx gap)
            self._add(
                f'  <rect x="{x:.1f}" y="{y + HEADER_H - CAP_H:.1f}" '
                f'width="{w}" height="{CAP_H}" fill="{col}"/>'
            )
            # Title text
            fs = ot.get("titleFontSize", 10.5)
            self._add(
                f'  <text x="{cx:.1f}" y="{y + 17:.1f}" font-size="{fs}" '
                f'fill="white" text-anchor="middle" font-weight="700">'
                f'{ot["displayName"]}</text>'
            )

            # Body text lines
            fields     = ot.get("displayFields", [])
            last_note  = ot.get("lastFieldNote", False)
            nf         = len(fields)
            body_top   = y + HEADER_H
            body_h     = h - HEADER_H

            if nf == 0:
                line_ys = []
            elif nf == 1:
                line_ys = [body_top + body_h * 0.55]
            elif nf == 2:
                step    = body_h / 3
                line_ys = [body_top + step, body_top + 2 * step]
            else:
                step    = body_h / (nf + 1)
                line_ys = [body_top + step * (i + 1) for i in range(nf)]

            for i, (field, fy) in enumerate(zip(fields, line_ys)):
                if last_note and i == nf - 1:
                    self._add(
                        f'  <text x="{cx:.1f}" y="{fy:.1f}" font-size="8" '
                        f'fill="#888" text-anchor="middle" font-style="italic">'
                        f'{field}</text>'
                    )
                else:
                    self._add(
                        f'  <text x="{cx:.1f}" y="{fy:.1f}" font-size="9" '
                        f'fill="#5f564b" text-anchor="middle">{field}</text>'
                    )
            self._add("")

    # ── relationships ─────────────────────────────────────────────────────────

    def _relationships(self):
        self._add("  <!-- ══ RELATIONSHIPS ══ -->")
        boxes = self.l.boxes
        secs  = self.l.sections

        for rel in self.cfg["relationships"]:
            routing = rel.get("routing", "default")
            ckey    = rel.get("color", "default")
            stroke  = self._arrow_color(ckey)
            marker  = self._marker(ckey)
            label   = rel.get("label", "")
            dashed  = rel.get("style", "solid") == "dashed"
            dash    = "4 3" if dashed else ""
            sdash   = "5 3" if dashed else ""  # slightly longer for governance dashes

            self._add(f"  <!-- {rel['id']} -->")

            if routing == "diagonal_to_governance":
                src = boxes[rel["from"]]
                tgt = boxes[rel["to"]]
                x1, y1 = src["right"], src["cy"]
                x2, y2 = tgt["x"] - 2, tgt["cy"]
                self._line(x1, y1, x2, y2, stroke, dash=sdash, marker=marker)
                self._text((x1 + x2) / 2, (y1 + y2) / 2 - 6,
                           label, size=8.5, fill=stroke, italic=True)

            elif routing == "stub_down":
                # Short dashed stub from SDP bottom toward architecture section
                src      = boxes[rel["from"]]
                arch_sec = secs["architecture"]
                x1       = src["cx"]
                y1       = src["bottom"]
                y2       = arch_sec["y"] - 2
                self._line(x1, y1, x1, y2, stroke, sw=1.2, dash=dash, marker=marker)
                self._text(x1 + 8, (y1 + y2) / 2 + 4,
                           label, size=8.5, fill=stroke, anchor="start", italic=True)

            elif routing == "down_through_gap":
                # Drop from Engineering box, jog to service, enter from top
                src        = boxes[rel["from"]]
                tgt        = boxes[rel["to"]]
                jog_offset = rel.get("jogOffset", -7)
                x1         = src["cx"]
                y1         = src["bottom"]
                jog_y      = tgt["y"] + jog_offset
                tgt_x      = tgt["cx"]
                y2         = tgt["y"]

                self._line(x1, y1, x1, jog_y, stroke, dash=dash)
                self._line(x1, jog_y, tgt_x, jog_y, stroke, dash=dash)
                self._line(tgt_x, jog_y, tgt_x, y2, stroke, dash=dash, marker=marker)
                self._text(x1 - 5, y1 + (jog_y - y1) / 2,
                           label, size=8.5, fill=stroke, anchor="end", italic=True)

            elif routing == "bus_downward":
                # Services → bus → TechComponent + Host (arrows point DOWN)
                from_refs  = rel["from"] if isinstance(rel["from"], list) else [rel["from"]]
                to_refs    = rel["to"]   if isinstance(rel["to"],   list) else [rel["to"]]
                from_boxes = [boxes[t] for t in from_refs]
                to_boxes   = [boxes[t] for t in to_refs]

                svc_bottom = from_boxes[0]["bottom"]   # all services same height
                comp_top   = to_boxes[0]["y"]           # all components same y
                bus_y      = (svc_bottom + comp_top) / 2
                bus_x1     = from_boxes[0]["cx"]
                bus_x2     = to_boxes[-1]["cx"]

                # Service bottoms → bus (no arrowhead)
                for fb in from_boxes:
                    self._line(fb["cx"], svc_bottom, fb["cx"], bus_y, stroke, sw=1.2)
                # Bus horizontal
                self._line(bus_x1, bus_y, bus_x2, bus_y, stroke, sw=1.2)
                # Bus → component tops (arrowhead points into component)
                for tb in to_boxes:
                    self._line(tb["cx"], bus_y, tb["cx"], comp_top,
                               stroke, sw=1.2, marker=marker)
                # Label just above bus
                self._text(bus_x2 - 18, bus_y - 7,
                           label, size=9, fill=stroke, anchor="end", italic=True)

            elif routing == "side_route_to_governance":
                # TechComponent right → down below arch section → up x-channel → governance
                src      = boxes[rel["from"]]
                tgt      = boxes[rel["to"]]
                arch_sec = secs["architecture"]
                x_start  = src["right"]
                y_start  = src["cy"]
                y_low    = arch_sec["bottom"] - 8
                x_ch     = rel.get("xChannel", 626)
                x2, y2   = tgt["x"] - 2, tgt["cy"]

                self._line(x_start, y_start, x_start, y_low, stroke)
                self._line(x_start, y_low,   x_ch,    y_low,   stroke)
                self._line(x_ch,    y_low,   x_ch,    y2,      stroke)
                self._line(x_ch,    y2,      x2,      y2,      stroke, marker=marker)
                # Label on the vertical segment, offset right
                lx = x_ch + 4
                ly = (y_low + y2) / 2
                self._text(lx, ly, label, size=9, fill=stroke, anchor="start", italic=True)

            elif routing == "short_vertical":
                # e.g. Domain → Capability, RequirementGroup → Requirement
                src = boxes[rel["from"]]
                tgt = boxes[rel["to"]]
                x1  = src["cx"]
                y1  = src["bottom"]
                y2  = tgt["y"] - 2
                self._line(x1, y1, x1, y2, stroke, marker=marker)
                self._text(x1 + 14, (y1 + y2) / 2 + 3,
                           label, size=9, fill=stroke, anchor="start", italic=True)

            elif routing == "arrow_left":
                # RequirementGroup appliesTo → left panel
                src = boxes[rel["from"]]
                x1  = src["x"] - 2
                y1  = src["cy"]
                x2  = x1 - 20
                self._line(x1, y1, x2, y1, stroke, dash=sdash, marker=marker)
                self._text((x1 + x2) / 2, y1 - 6,
                           label, size=9, fill=stroke, italic=True)

            self._add("")

    # ── title ─────────────────────────────────────────────────────────────────

    def _title(self):
        w = self.cfg["canvas"]["width"]
        y = self.l.total_height - 6
        self._add(
            f'  <text x="{w // 2}" y="{y:.1f}" font-size="11" fill="#5f564b" '
            f'text-anchor="middle" font-weight="600">'
            f'DRAFT Object Model - UML Class Diagram</text>'
        )


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

def main():
    if not CONFIG_PATH.exists():
        print(f"ERROR: config not found: {CONFIG_PATH}", file=sys.stderr)
        sys.exit(1)

    with open(CONFIG_PATH) as fh:
        cfg = yaml.safe_load(fh)

    out_path = REPO_ROOT / cfg["outputPath"]

    layout  = LayoutEngine(cfg)
    builder = SVGBuilder(layout, cfg)
    svg     = builder.build()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(svg)

    print(f"Generated: {out_path}")
    print(f"Canvas:    {cfg['canvas']['width']} × {layout.total_height:.0f} px")
    print(f"Sections:  {list(layout.sections.keys())}")
    print(f"Boxes:     {len(layout.boxes)}")


if __name__ == "__main__":
    main()
