# -*- coding: utf-8 -*-
"""Generates the animated architecture diagrams used by the README and website.

    python website/assets/gen_architecture.py

Writes architecture.svg (English) and architecture-zh.svg next to this file.
The SVGs are self-contained: CSS-animated, light/dark aware, no scripts, so
they render both inline on the website and as <img> on GitHub.
"""
import os

TEXT = {
    "en": {
        "lang": "en",
        "left": "FROM THE INTERNET",
        "right": "TO YOUR INFRASTRUCTURE",
        "engine": "Routing Engine",
        "pills_top": [("Security &amp; Identity", "OIDC · JWT · IDS · WAF"),
                      ("Traffic Management", "LB · retry · circuit breaker · rate limit")],
        "pills_bottom": [("Certificates &amp; ECH", "ACME · DNS-01 · on-demand"),
                         ("Static Hosting", "SPA · Markdown · WebDAV"),
                         ("Observability", "Dashboard · logs · Prometheus")],
        "groups": [("Labels &amp; Tags", "Docker · Consul · Litemesh · K8s", ["Backend Service 1", "Backend Service 2"]),
                   ("Site files &amp; KV", "YAML · Litemesh / Consul KV", ["Server / VM"]),
                   ("Connect", "reverse tunnel · no inbound ports", ["Home / On-prem Service"])],
        "chips": ["Tags", "Files", "Tunnel"],
    },
    "zh": {
        "lang": "zh-CN",
        "left": "来自互联网",
        "right": "到你的基础设施",
        "engine": "路由引擎",
        "pills_top": [("安全与身份", "OIDC · JWT · IDS · WAF"),
                      ("流量治理", "负载均衡 · 重试 · 熔断 · 限流")],
        "pills_bottom": [("自动证书与 ECH", "ACME · DNS-01 · 按需签发"),
                         ("静态托管", "SPA · Markdown · WebDAV"),
                         ("可观测", "Dashboard · 日志 · Prometheus")],
        "groups": [("服务发现 · 标签", "Docker · Consul · Litemesh · K8s", ["后端服务 1", "后端服务 2"]),
                   ("站点文件 · KV", "YAML · Litemesh / Consul KV", ["服务器 / 虚拟机"]),
                   ("内网 · Connect", "反向隧道，不开放入站端口", ["家庭 / 机房内的服务"])],
        "chips": ["标签", "文件", "隧道"],
    },
}

SOURCES = [("api.example.com", "HTTPS"), ("app.example.com", "HTTP/3"),
           ("redis.example.com", "TCP · SNI"), ("iot.example.com", "UDP")]

STYLE = """
  :root, svg { --pill:#17201d; --pill-text:#ffffff; --frame:#d4cfc3; --frame-fill:rgba(23,32,29,.025);
    --muted:#7d8984; --text:#17201d; --line:#c9cfcb; --accent:#0f7a5f; --accent-soft:rgba(15,122,95,.10);
    --amber:#b9602a; --chip:#ffffff; }
  @media (prefers-color-scheme: dark) {
    :root, svg { --pill:#e9efec; --pill-text:#0d1211; --frame:#31403c; --frame-fill:rgba(255,255,255,.02);
      --muted:#8d9b96; --text:#e9efec; --line:#3a4743; --accent:#3cc99f; --accent-soft:rgba(60,201,159,.12);
      --amber:#f0a16b; --chip:#161e1c; }
  }
  text { font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue","PingFang SC","Microsoft YaHei",sans-serif; }
  .mono { font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; }
  .col-title { fill:var(--muted); font-size:13px; letter-spacing:1px; }
  .frame { fill:var(--frame-fill); stroke:var(--frame); stroke-width:1.2; }
  .group { fill:none; stroke:var(--frame); stroke-width:1.2; }
  .pill { fill:var(--pill); }
  .pill-text { fill:var(--pill-text); font-size:15px; font-weight:600; }
  .cap { fill:var(--accent-soft); stroke:var(--accent); stroke-width:1; }
  .cap-title { fill:var(--accent); font-size:14px; font-weight:700; }
  .cap-sub { fill:var(--muted); font-size:11.5px; }
  .engine { fill:var(--pill); stroke:var(--accent); stroke-width:2; }
  .engine-text { fill:var(--pill-text); font-size:19px; font-weight:700; }
  .brand-mark { fill:var(--accent); }
  .brand-l { fill:#ffffff; font-size:17px; font-weight:800; }
  .brand { fill:var(--text); font-size:24px; font-weight:750; }
  .g-title { fill:var(--text); font-size:14px; font-weight:700; }
  .g-sub { fill:var(--muted); font-size:11.5px; }
  .base { fill:none; stroke:var(--line); stroke-width:1.6; }
  .flow { fill:none; stroke:var(--accent); stroke-width:2; stroke-dasharray:6 10; animation:dash 1.1s linear infinite; }
  .provider { fill:none; stroke:var(--amber); stroke-width:1.4; stroke-dasharray:3 5; animation:dash-back 1.6s linear infinite; }
  .chip { fill:var(--chip); stroke:var(--line); stroke-width:1; }
  .chip-text { fill:var(--muted); font-size:11px; font-weight:600; }
  .chip-p { fill:var(--chip); stroke:var(--amber); stroke-width:1; }
  .chip-p-text { fill:var(--amber); font-size:11px; font-weight:600; }
  @keyframes dash { to { stroke-dashoffset:-32; } }
  @keyframes dash-back { to { stroke-dashoffset:16; } }
  @media (prefers-reduced-motion: reduce) { .flow, .provider { animation:none; } }
"""

ENGINE = (580, 302)  # center of the routing engine


def pill(cx, cy, w, h, label, cls="pill", tcls="pill-text"):
    return (f'<rect class="{cls}" x="{cx - w / 2:.0f}" y="{cy - h / 2:.0f}" width="{w}" height="{h}" rx="{h / 2:.0f}"/>'
            f'<text class="{tcls}" x="{cx}" y="{cy + 5}" text-anchor="middle">{label}</text>')


def chip(cx, cy, label, w, cls="chip", tcls="chip-text"):
    return (f'<rect class="{cls}" x="{cx - w / 2:.0f}" y="{cy - 11}" width="{w}" height="22" rx="11"/>'
            f'<text class="{tcls}" x="{cx}" y="{cy + 4}" text-anchor="middle">{label}</text>')


def capability(cy, title, sub):
    x, w, h = 400, 360, 46
    return (f'<rect class="cap" x="{x}" y="{cy - h / 2:.0f}" width="{w}" height="{h}" rx="12"/>'
            f'<text class="cap-title" x="{x + 18}" y="{cy + 5}">{title}</text>'
            f'<text class="cap-sub" x="{x + w - 18}" y="{cy + 4}" text-anchor="end">{sub}</text>')


def build(t):
    ex, ey = ENGINE
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 600" width="1200" height="600" '
           f'role="img" aria-label="LiteGate architecture" lang="{t["lang"]}">',
           f'<style>{STYLE}</style>']

    # Column frames and titles.
    out += ['<text class="col-title mono" x="20" y="28">' + t["left"] + '</text>',
            '<rect class="frame" x="20" y="40" width="250" height="540" rx="16"/>',
            '<rect class="frame" x="370" y="40" width="420" height="540" rx="16"/>',
            '<text class="col-title mono" x="880" y="28">' + t["right"] + '</text>',
            '<rect class="frame" x="880" y="40" width="300" height="540" rx="16"/>']

    # Brand.
    out += ['<rect class="brand-mark" x="512" y="62" width="30" height="30" rx="8"/>',
            '<text class="brand-l mono" x="527" y="83" text-anchor="middle">L</text>',
            '<text class="brand" x="552" y="86">LiteGate</text>']

    # Internet -> engine.
    ys = [150, 250, 350, 450]
    for (host, proto), y in zip(SOURCES, ys):
        d = f"M240,{y} C330,{y} 330,{ey} 430,{ey}"
        out += [f'<path class="base" d="{d}"/>', f'<path class="flow" d="{d}"/>']
    for (host, proto), y in zip(SOURCES, ys):
        out.append(pill(140, y, 190, 40, host))
        # Midpoint of the cubic curve: x = (240 + 3*330 + 3*330 + 430) / 8.
        out.append(chip(331, (y + ey) / 2, proto, 78))

    # Engine -> infrastructure targets.
    groups = t["groups"]
    frames = [(70, 200), (290, 130), (440, 130)]  # (top, height) per group
    targets = []
    for (title, sub, nodes), (top, height) in zip(groups, frames):
        first = top + 78
        step = 50
        for i, node in enumerate(nodes):
            targets.append((node, first + i * step))
    for node, y in targets:
        d = f"M730,{ey} C820,{ey} 830,{y} 940,{y}"
        out += [f'<path class="base" d="{d}"/>', f'<path class="flow" d="{d}"/>']

    # Providers feed configuration back to the engine (dotted, reversed).
    for i, ((title, sub, nodes), (top, height)) in enumerate(zip(groups, frames)):
        y = top + 26
        d = f"M865,{y} C800,{y} 790,{ey - 24} 730,{ey - 24}"
        out.append(f'<path class="provider" d="{d}"/>')

    # Group frames, headers, nodes.
    for i, ((title, sub, nodes), (top, height)) in enumerate(zip(groups, frames)):
        out.append(f'<rect class="group" x="900" y="{top}" width="264" height="{height}" rx="12"/>')
        out.append(f'<text class="g-title" x="916" y="{top + 26}">{title}</text>')
        out.append(f'<text class="g-sub" x="916" y="{top + 45}">{sub}</text>')
        out.append(chip(866, top + 26, t["chips"][i], 58, "chip-p", "chip-p-text"))
    for node, y in targets:
        out.append(pill(1040, y, 200, 38, node))

    # Engine and capabilities.
    for cy, (title, sub) in zip([140, 204], t["pills_top"]):
        out.append(capability(cy, title, sub))
    out.append(f'<rect class="engine" x="430" y="{ey - 34}" width="300" height="68" rx="16"/>')
    out.append(f'<text class="engine-text" x="{ex}" y="{ey + 7}" text-anchor="middle">{t["engine"]}</text>')
    for cy, (title, sub) in zip([400, 464, 528], t["pills_bottom"]):
        out.append(capability(cy, title, sub))

    out.append("</svg>")
    return "\n".join(out) + "\n"


here = os.path.dirname(os.path.abspath(__file__))
for lang, name in (("en", "architecture.svg"), ("zh", "architecture-zh.svg")):
    with open(os.path.join(here, name), "w", encoding="utf-8", newline="\n") as f:
        f.write(build(TEXT[lang]))
    print("wrote", name)
