"""Designer — template definitions for 7 design categories.

Each template provides a set of starter pages with professional HTML/CSS
using CSS variables for brand theming.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Template:
    """A designer template definition."""
    id: str
    name: str
    category: str          # "Presentations" | "Documents" | "Marketing" | "UI" | "General"
    description: str
    aspect_ratio: str      # default aspect ratio for this template
    pages: list[dict]      # [{html, title, notes}...]
    icon: str = "🎨"


# ─── CSS base that all templates share ────────────────────────────────────
def _base_style(
    width: int = 1920, height: int = 1080,
    primary: str = "#2563EB", secondary: str = "#1E40AF",
    accent: str = "#F59E0B", bg: str = "#0F172A", text: str = "#F8FAFC",
    heading_font: str = "Inter", body_font: str = "Inter",
) -> str:
    from designer.fonts import get_all_fonts_css, get_fallback_stack
    # Resolve fonts locally (bundled → cached → CDN fallback)
    font_families = list(dict.fromkeys([heading_font, body_font, "Inter"]))
    font_css = get_all_fonts_css(font_families)
    fallback = get_fallback_stack(body_font)
    h_fallback = get_fallback_stack(heading_font)
    return (
        f"<style>\n{font_css}\n"
        "  * { margin: 0; padding: 0; box-sizing: border-box; }\n"
        "  :root {\n"
        f"    --primary: {primary};\n"
        f"    --secondary: {secondary};\n"
        f"    --accent: {accent};\n"
        f"    --bg: {bg};\n"
        f"    --text: {text};\n"
        f"    --heading-font: '{heading_font}', {fallback};\n"
        f"    --body-font: '{body_font}', {fallback};\n"
        "  }\n"
        "  body {\n"
        f"    width: {width}px; height: {height}px;\n"
        f"    font-family: var(--body-font);\n"
        "    background: var(--bg);\n"
        "    color: var(--text);\n"
        "    overflow: hidden;\n"
        "    -webkit-font-smoothing: antialiased;\n"
        "    text-rendering: optimizeLegibility;\n"
        "  }\n"
        "  h1, h2, h3, h4 {\n"
        f"    font-family: var(--heading-font);\n"
        "    letter-spacing: -0.02em;\n"
        "  }\n"
        "  .card {\n"
        "    background: rgba(255,255,255,0.05);\n"
        "    border-radius: 16px;\n"
        "    border: 1px solid rgba(255,255,255,0.06);\n"
        "    backdrop-filter: blur(8px);\n"
        "  }\n"
        "  .card-light {\n"
        "    background: #F9FAFB;\n"
        "    border-radius: 12px;\n"
        "    border: 1px solid #E5E7EB;\n"
        "  }\n"
        "  .gradient-primary {\n"
        "    background: linear-gradient(135deg, var(--primary), var(--secondary));\n"
        "  }\n"
        "</style>"
    )


# ═══════════════════════════════════════════════════════════════════════
# TEMPLATES
# ═══════════════════════════════════════════════════════════════════════

def _pitch_deck() -> Template:
    s = _base_style()
    return Template(
        id="pitch_deck",
        name="Pitch Deck",
        category="Presentations",
        description="5-slide investor pitch deck with title, problem, solution, traction, and CTA.",
        aspect_ratio="16:9",
        icon="📊",
        pages=[
            {"title": "Title Slide", "notes": "Introduce company and tagline.", "html": f"""<!DOCTYPE html><html><head>{s}</head><body>
<div style="display:flex;flex-direction:column;justify-content:center;align-items:center;height:100%;padding:80px;">
  <div style="width:120px;height:120px;border-radius:24px;background:var(--primary);margin-bottom:40px;display:flex;align-items:center;justify-content:center;">
    <span style="font-size:3rem;color:#fff;">✦</span>
  </div>
  <h1 style="font-size:4.5rem;font-weight:800;text-align:center;margin-bottom:16px;">Your Company Name</h1>
  <p style="font-size:1.8rem;opacity:0.7;text-align:center;max-width:800px;">A one-line description of what you do and why it matters</p>
  <div style="margin-top:60px;padding:12px 32px;border:2px solid var(--accent);border-radius:8px;font-size:1.2rem;color:var(--accent);">investor@company.com</div>
</div></body></html>"""},
            {"title": "Problem", "notes": "Define the problem you solve.", "html": f"""<!DOCTYPE html><html><head>{s}</head><body>
<div style="display:flex;flex-direction:column;padding:80px 100px;height:100%;">
  <h2 style="font-size:3rem;font-weight:700;color:var(--accent);margin-bottom:48px;">The Problem</h2>
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:40px;flex:1;align-items:start;">
    <div style="background:rgba(255,255,255,0.05);border-radius:16px;padding:40px;">
      <div style="font-size:2.5rem;margin-bottom:16px;">😤</div>
      <h3 style="font-size:1.5rem;margin-bottom:12px;">Pain Point 1</h3>
      <p style="font-size:1.1rem;opacity:0.7;line-height:1.6;">Description of the first major pain point your target audience faces.</p>
    </div>
    <div style="background:rgba(255,255,255,0.05);border-radius:16px;padding:40px;">
      <div style="font-size:2.5rem;margin-bottom:16px;">⏰</div>
      <h3 style="font-size:1.5rem;margin-bottom:12px;">Pain Point 2</h3>
      <p style="font-size:1.1rem;opacity:0.7;line-height:1.6;">Description of the second major pain point your target audience faces.</p>
    </div>
    <div style="background:rgba(255,255,255,0.05);border-radius:16px;padding:40px;">
      <div style="font-size:2.5rem;margin-bottom:16px;">💸</div>
      <h3 style="font-size:1.5rem;margin-bottom:12px;">Pain Point 3</h3>
      <p style="font-size:1.1rem;opacity:0.7;line-height:1.6;">Description of the third major pain point your target audience faces.</p>
    </div>
  </div>
</div></body></html>"""},
            {"title": "Solution", "notes": "Show your solution.", "html": f"""<!DOCTYPE html><html><head>{s}</head><body>
<div style="display:flex;flex-direction:column;padding:80px 100px;height:100%;">
  <h2 style="font-size:3rem;font-weight:700;color:var(--primary);margin-bottom:48px;">Our Solution</h2>
  <div style="display:flex;gap:60px;flex:1;align-items:center;">
    <div style="flex:1;">
      <h3 style="font-size:2rem;margin-bottom:24px;">How It Works</h3>
      <div style="display:flex;flex-direction:column;gap:20px;">
        <div style="display:flex;align-items:center;gap:16px;"><div style="width:40px;height:40px;border-radius:50%;background:var(--primary);display:flex;align-items:center;justify-content:center;font-weight:700;flex-shrink:0;">1</div><p style="font-size:1.2rem;opacity:0.8;">Step one of your solution workflow</p></div>
        <div style="display:flex;align-items:center;gap:16px;"><div style="width:40px;height:40px;border-radius:50%;background:var(--primary);display:flex;align-items:center;justify-content:center;font-weight:700;flex-shrink:0;">2</div><p style="font-size:1.2rem;opacity:0.8;">Step two of your solution workflow</p></div>
        <div style="display:flex;align-items:center;gap:16px;"><div style="width:40px;height:40px;border-radius:50%;background:var(--primary);display:flex;align-items:center;justify-content:center;font-weight:700;flex-shrink:0;">3</div><p style="font-size:1.2rem;opacity:0.8;">Step three of your solution workflow</p></div>
      </div>
    </div>
    <div style="flex:1;height:400px;border-radius:20px;background:linear-gradient(135deg,var(--primary),var(--secondary));display:flex;align-items:center;justify-content:center;">
      <span style="font-size:4rem;opacity:0.3;">📱</span>
    </div>
  </div>
</div></body></html>"""},
            {"title": "Traction", "notes": "Show your progress and metrics.", "html": f"""<!DOCTYPE html><html><head>{s}</head><body>
<div style="display:flex;flex-direction:column;padding:80px 100px;height:100%;">
  <h2 style="font-size:3rem;font-weight:700;color:var(--accent);margin-bottom:48px;">Traction</h2>
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:32px;margin-bottom:48px;">
    <div style="text-align:center;padding:32px;background:rgba(255,255,255,0.05);border-radius:16px;">
      <div style="font-size:3rem;font-weight:800;color:var(--primary);">10K+</div>
      <div style="font-size:1rem;opacity:0.6;margin-top:8px;">Active Users</div>
    </div>
    <div style="text-align:center;padding:32px;background:rgba(255,255,255,0.05);border-radius:16px;">
      <div style="font-size:3rem;font-weight:800;color:var(--primary);">150%</div>
      <div style="font-size:1rem;opacity:0.6;margin-top:8px;">MoM Growth</div>
    </div>
    <div style="text-align:center;padding:32px;background:rgba(255,255,255,0.05);border-radius:16px;">
      <div style="font-size:3rem;font-weight:800;color:var(--primary);">$2M</div>
      <div style="font-size:1rem;opacity:0.6;margin-top:8px;">ARR</div>
    </div>
    <div style="text-align:center;padding:32px;background:rgba(255,255,255,0.05);border-radius:16px;">
      <div style="font-size:3rem;font-weight:800;color:var(--primary);">95%</div>
      <div style="font-size:1rem;opacity:0.6;margin-top:8px;">Retention</div>
    </div>
  </div>
  <div style="flex:1;background:rgba(255,255,255,0.03);border-radius:16px;padding:40px;display:flex;align-items:center;justify-content:center;">
    <span style="font-size:1.5rem;opacity:0.4;">📈 Growth chart placeholder</span>
  </div>
</div></body></html>"""},
            {"title": "Call to Action", "notes": "Next steps and contact info.", "html": f"""<!DOCTYPE html><html><head>{s}</head><body>
<div style="display:flex;flex-direction:column;justify-content:center;align-items:center;height:100%;padding:80px;">
  <h2 style="font-size:3.5rem;font-weight:800;text-align:center;margin-bottom:24px;">Let's Build the Future Together</h2>
  <p style="font-size:1.5rem;opacity:0.6;text-align:center;max-width:700px;margin-bottom:60px;">We're raising a $5M Series A to scale our platform globally.</p>
  <div style="display:flex;gap:24px;margin-bottom:60px;">
    <div style="padding:16px 40px;background:var(--primary);border-radius:12px;font-size:1.3rem;font-weight:600;">Schedule a Call</div>
    <div style="padding:16px 40px;border:2px solid var(--accent);border-radius:12px;font-size:1.3rem;color:var(--accent);">Download Deck</div>
  </div>
  <div style="opacity:0.5;font-size:1.1rem;">
    <p>founder@company.com · (555) 123-4567</p>
    <p style="margin-top:8px;">www.company.com</p>
  </div>
</div></body></html>"""},
        ],
    )


def _status_report() -> Template:
    s = _base_style()
    return Template(
        id="status_report",
        name="Status Report",
        category="Documents",
        description="3-page project status report with summary, metrics, and next steps.",
        aspect_ratio="16:9",
        icon="📋",
        pages=[
            {"title": "Executive Summary", "notes": "", "html": f"""<!DOCTYPE html><html><head>{s}</head><body>
<div style="display:flex;flex-direction:column;padding:80px 100px;height:100%;">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:48px;">
    <h1 style="font-size:3rem;font-weight:800;">Project Status Report</h1>
    <div style="padding:8px 24px;background:var(--accent);border-radius:8px;font-weight:600;color:#000;">On Track</div>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:40px;flex:1;">
    <div style="background:rgba(255,255,255,0.05);border-radius:16px;padding:36px;">
      <h3 style="font-size:1.3rem;color:var(--primary);margin-bottom:16px;">Overview</h3>
      <p style="font-size:1.1rem;line-height:1.8;opacity:0.8;">Summary of the project's current state, key accomplishments this period, and overall health assessment.</p>
    </div>
    <div style="background:rgba(255,255,255,0.05);border-radius:16px;padding:36px;">
      <h3 style="font-size:1.3rem;color:var(--primary);margin-bottom:16px;">Key Highlights</h3>
      <ul style="font-size:1.1rem;line-height:2;opacity:0.8;list-style:none;padding:0;">
        <li>✅ Milestone 1 completed ahead of schedule</li>
        <li>✅ Team expanded by 2 engineers</li>
        <li>⚠️ Budget utilization at 78%</li>
        <li>🔄 Feature X moved to next sprint</li>
      </ul>
    </div>
  </div>
  <div style="margin-top:32px;opacity:0.4;font-size:0.9rem;">Report Date: April 2026 · Prepared by: Team Lead</div>
</div></body></html>"""},
            {"title": "Metrics", "notes": "", "html": f"""<!DOCTYPE html><html><head>{s}</head><body>
<div style="display:flex;flex-direction:column;padding:80px 100px;height:100%;">
  <h2 style="font-size:2.5rem;font-weight:700;margin-bottom:48px;">Key Metrics</h2>
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:32px;margin-bottom:40px;">
    <div style="text-align:center;padding:32px;background:rgba(37,99,235,0.15);border-radius:16px;border:1px solid rgba(37,99,235,0.3);">
      <div style="font-size:2.5rem;font-weight:800;color:var(--primary);">87%</div>
      <div style="font-size:1rem;opacity:0.6;margin-top:8px;">Sprint Velocity</div>
    </div>
    <div style="text-align:center;padding:32px;background:rgba(245,158,11,0.15);border-radius:16px;border:1px solid rgba(245,158,11,0.3);">
      <div style="font-size:2.5rem;font-weight:800;color:var(--accent);">23</div>
      <div style="font-size:1rem;opacity:0.6;margin-top:8px;">Tasks Completed</div>
    </div>
    <div style="text-align:center;padding:32px;background:rgba(34,197,94,0.15);border-radius:16px;border:1px solid rgba(34,197,94,0.3);">
      <div style="font-size:2.5rem;font-weight:800;color:#22c55e;">4</div>
      <div style="font-size:1rem;opacity:0.6;margin-top:8px;">Blockers Resolved</div>
    </div>
  </div>
  <div style="flex:1;background:rgba(255,255,255,0.03);border-radius:16px;padding:40px;display:flex;align-items:center;justify-content:center;">
    <span style="opacity:0.3;font-size:1.2rem;">📊 Burn-down chart placeholder</span>
  </div>
</div></body></html>"""},
            {"title": "Next Steps", "notes": "", "html": f"""<!DOCTYPE html><html><head>{s}</head><body>
<div style="display:flex;flex-direction:column;padding:80px 100px;height:100%;">
  <h2 style="font-size:2.5rem;font-weight:700;margin-bottom:48px;">Next Steps</h2>
  <div style="display:flex;flex-direction:column;gap:24px;flex:1;">
    <div style="display:flex;gap:20px;align-items:start;padding:24px;background:rgba(255,255,255,0.05);border-radius:12px;border-left:4px solid var(--primary);">
      <div style="font-size:1.2rem;font-weight:700;color:var(--primary);white-space:nowrap;">Week 1</div>
      <div><h4 style="font-size:1.2rem;margin-bottom:8px;">Complete Feature Integration</h4><p style="opacity:0.6;">Finish API integration and run end-to-end tests.</p></div>
    </div>
    <div style="display:flex;gap:20px;align-items:start;padding:24px;background:rgba(255,255,255,0.05);border-radius:12px;border-left:4px solid var(--accent);">
      <div style="font-size:1.2rem;font-weight:700;color:var(--accent);white-space:nowrap;">Week 2</div>
      <div><h4 style="font-size:1.2rem;margin-bottom:8px;">User Testing Round</h4><p style="opacity:0.6;">Run beta testing with 50 users and collect feedback.</p></div>
    </div>
    <div style="display:flex;gap:20px;align-items:start;padding:24px;background:rgba(255,255,255,0.05);border-radius:12px;border-left:4px solid #22c55e;">
      <div style="font-size:1.2rem;font-weight:700;color:#22c55e;white-space:nowrap;">Week 3</div>
      <div><h4 style="font-size:1.2rem;margin-bottom:8px;">Production Release</h4><p style="opacity:0.6;">Deploy to production and begin monitoring.</p></div>
    </div>
  </div>
  <div style="margin-top:32px;padding:24px;background:rgba(245,158,11,0.1);border-radius:12px;border:1px solid rgba(245,158,11,0.3);">
    <h4 style="color:var(--accent);margin-bottom:8px;">⚠️ Risks</h4>
    <p style="opacity:0.7;">Third-party API rate limits may require caching strategy. Team capacity reduced in Week 2 due to company offsite.</p>
  </div>
</div></body></html>"""},
        ],
    )


def _marketing_one_pager() -> Template:
    s = _base_style()
    return Template(
        id="marketing_one_pager",
        name="Marketing One-Pager",
        category="Marketing",
        description="Single-page product marketing sheet with benefits, social proof, and CTA.",
        aspect_ratio="A4",
        icon="📄",
        pages=[
            {"title": "One-Pager", "notes": "", "html": f"""<!DOCTYPE html><html><head>{s.replace('1920px', '794px').replace('1080px', '1123px')}</head><body>
<div style="display:flex;flex-direction:column;padding:60px 50px;height:100%;gap:32px;">
  <div style="text-align:center;">
    <div style="width:60px;height:60px;border-radius:12px;background:var(--primary);margin:0 auto 16px;display:flex;align-items:center;justify-content:center;"><span style="font-size:1.5rem;color:#fff;">✦</span></div>
    <h1 style="font-size:2.2rem;font-weight:800;margin-bottom:8px;">Product Name</h1>
    <p style="font-size:1.1rem;opacity:0.7;">The one-liner that explains your value proposition</p>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:20px;">
    <div style="padding:24px;background:rgba(255,255,255,0.05);border-radius:12px;text-align:center;">
      <div style="font-size:1.8rem;margin-bottom:8px;">🚀</div>
      <h3 style="font-size:1rem;margin-bottom:8px;">Fast</h3>
      <p style="font-size:0.85rem;opacity:0.6;line-height:1.5;">10x faster than alternatives.</p>
    </div>
    <div style="padding:24px;background:rgba(255,255,255,0.05);border-radius:12px;text-align:center;">
      <div style="font-size:1.8rem;margin-bottom:8px;">🔒</div>
      <h3 style="font-size:1rem;margin-bottom:8px;">Secure</h3>
      <p style="font-size:0.85rem;opacity:0.6;line-height:1.5;">Enterprise-grade security built in.</p>
    </div>
    <div style="padding:24px;background:rgba(255,255,255,0.05);border-radius:12px;text-align:center;">
      <div style="font-size:1.8rem;margin-bottom:8px;">💡</div>
      <h3 style="font-size:1rem;margin-bottom:8px;">Simple</h3>
      <p style="font-size:0.85rem;opacity:0.6;line-height:1.5;">Get started in under 5 minutes.</p>
    </div>
  </div>
  <div style="background:rgba(255,255,255,0.03);border-radius:12px;padding:24px;text-align:center;">
    <p style="font-size:1rem;font-style:italic;opacity:0.7;">"This product transformed how our team works. We saved 20 hours per week."</p>
    <p style="font-size:0.85rem;margin-top:8px;color:var(--accent);">— Jane Doe, VP Engineering at Acme Corp</p>
  </div>
  <div style="text-align:center;padding:24px;background:linear-gradient(135deg,var(--primary),var(--secondary));border-radius:12px;">
    <h3 style="font-size:1.3rem;margin-bottom:8px;">Ready to Get Started?</h3>
    <p style="opacity:0.8;">Visit www.product.com or email sales@product.com</p>
  </div>
</div></body></html>"""},
        ],
    )


def _product_launch() -> Template:
    s = _base_style()
    return Template(
        id="product_launch",
        name="Product Launch",
        category="Marketing",
        description="4-slide product launch announcement with hero, features, pricing, and availability.",
        aspect_ratio="16:9",
        icon="🚀",
        pages=[
            {"title": "Hero", "notes": "Main announcement slide.", "html": f"""<!DOCTYPE html><html><head>{s}</head><body>
<div style="display:flex;flex-direction:column;justify-content:center;align-items:center;height:100%;background:linear-gradient(135deg,var(--bg) 0%,rgba(37,99,235,0.2) 100%);">
  <div style="padding:8px 20px;border:1px solid var(--accent);border-radius:20px;font-size:0.9rem;color:var(--accent);margin-bottom:32px;">🎉 NOW AVAILABLE</div>
  <h1 style="font-size:5rem;font-weight:800;text-align:center;margin-bottom:16px;">Introducing<br><span style="color:var(--primary);">Product 2.0</span></h1>
  <p style="font-size:1.5rem;opacity:0.6;text-align:center;max-width:700px;">The next generation of your favourite tool — faster, smarter, and more powerful than ever.</p>
</div></body></html>"""},
            {"title": "Features", "notes": "", "html": f"""<!DOCTYPE html><html><head>{s}</head><body>
<div style="display:flex;flex-direction:column;padding:80px 100px;height:100%;">
  <h2 style="font-size:2.5rem;font-weight:700;margin-bottom:48px;">What's New</h2>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:32px;flex:1;">
    <div style="padding:36px;background:rgba(255,255,255,0.05);border-radius:16px;"><div style="font-size:2rem;margin-bottom:12px;">⚡</div><h3 style="font-size:1.4rem;margin-bottom:12px;">Lightning Fast</h3><p style="opacity:0.6;line-height:1.6;">3x performance improvement with our new engine.</p></div>
    <div style="padding:36px;background:rgba(255,255,255,0.05);border-radius:16px;"><div style="font-size:2rem;margin-bottom:12px;">🤖</div><h3 style="font-size:1.4rem;margin-bottom:12px;">AI-Powered</h3><p style="opacity:0.6;line-height:1.6;">Built-in AI assistant for smarter workflows.</p></div>
    <div style="padding:36px;background:rgba(255,255,255,0.05);border-radius:16px;"><div style="font-size:2rem;margin-bottom:12px;">🔗</div><h3 style="font-size:1.4rem;margin-bottom:12px;">Integrations</h3><p style="opacity:0.6;line-height:1.6;">Connect with 100+ tools out of the box.</p></div>
    <div style="padding:36px;background:rgba(255,255,255,0.05);border-radius:16px;"><div style="font-size:2rem;margin-bottom:12px;">🛡️</div><h3 style="font-size:1.4rem;margin-bottom:12px;">Security</h3><p style="opacity:0.6;line-height:1.6;">SOC 2 Type II certified with E2E encryption.</p></div>
  </div>
</div></body></html>"""},
            {"title": "Pricing", "notes": "", "html": f"""<!DOCTYPE html><html><head>{s}</head><body>
<div style="display:flex;flex-direction:column;align-items:center;padding:80px 100px;height:100%;">
  <h2 style="font-size:2.5rem;font-weight:700;margin-bottom:48px;">Simple Pricing</h2>
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:32px;width:100%;max-width:1200px;">
    <div style="padding:40px;background:rgba(255,255,255,0.05);border-radius:16px;text-align:center;">
      <h3 style="font-size:1.2rem;opacity:0.6;margin-bottom:16px;">STARTER</h3>
      <div style="font-size:3rem;font-weight:800;margin-bottom:8px;">$9<span style="font-size:1rem;opacity:0.5;">/mo</span></div>
      <div style="height:1px;background:rgba(255,255,255,0.1);margin:20px 0;"></div>
      <div style="text-align:left;font-size:0.95rem;line-height:2.2;opacity:0.7;">✓ 5 projects<br>✓ Basic analytics<br>✓ Email support</div>
    </div>
    <div style="padding:40px;background:linear-gradient(135deg,rgba(37,99,235,0.2),rgba(37,99,235,0.1));border-radius:16px;text-align:center;border:2px solid var(--primary);">
      <h3 style="font-size:1.2rem;color:var(--primary);margin-bottom:16px;">PRO ⭐</h3>
      <div style="font-size:3rem;font-weight:800;margin-bottom:8px;">$29<span style="font-size:1rem;opacity:0.5;">/mo</span></div>
      <div style="height:1px;background:rgba(255,255,255,0.1);margin:20px 0;"></div>
      <div style="text-align:left;font-size:0.95rem;line-height:2.2;opacity:0.7;">✓ Unlimited projects<br>✓ Advanced analytics<br>✓ Priority support<br>✓ AI features</div>
    </div>
    <div style="padding:40px;background:rgba(255,255,255,0.05);border-radius:16px;text-align:center;">
      <h3 style="font-size:1.2rem;opacity:0.6;margin-bottom:16px;">ENTERPRISE</h3>
      <div style="font-size:3rem;font-weight:800;margin-bottom:8px;">Custom</div>
      <div style="height:1px;background:rgba(255,255,255,0.1);margin:20px 0;"></div>
      <div style="text-align:left;font-size:0.95rem;line-height:2.2;opacity:0.7;">✓ Everything in Pro<br>✓ SSO & SAML<br>✓ Dedicated support<br>✓ Custom SLA</div>
    </div>
  </div>
</div></body></html>"""},
            {"title": "Get Started", "notes": "", "html": f"""<!DOCTYPE html><html><head>{s}</head><body>
<div style="display:flex;flex-direction:column;justify-content:center;align-items:center;height:100%;background:linear-gradient(135deg,var(--bg) 0%,rgba(37,99,235,0.15) 100%);">
  <h2 style="font-size:3.5rem;font-weight:800;text-align:center;margin-bottom:16px;">Start Building Today</h2>
  <p style="font-size:1.3rem;opacity:0.6;margin-bottom:48px;">Free 14-day trial • No credit card required</p>
  <div style="padding:16px 48px;background:var(--primary);border-radius:12px;font-size:1.4rem;font-weight:600;">Get Started Free →</div>
</div></body></html>"""},
        ],
    )


def _social_media() -> Template:
    s = _base_style(width=1080, height=1080, bg="#0F172A")
    return Template(
        id="social_media",
        name="Social Media Set",
        category="Marketing",
        description="3-post social media graphics set (1:1 square format).",
        aspect_ratio="1:1",
        icon="📱",
        pages=[
            {"title": "Quote Post", "notes": "", "html": f"""<!DOCTYPE html><html><head>{s}</head><body>
<div style="display:flex;flex-direction:column;justify-content:center;align-items:center;height:100%;padding:80px;background:linear-gradient(135deg,var(--bg),rgba(37,99,235,0.2));">
  <div style="font-size:4rem;margin-bottom:32px;opacity:0.3;">❝</div>
  <p style="font-size:2rem;font-weight:600;text-align:center;line-height:1.5;max-width:800px;">"The best way to predict the future is to create it."</p>
  <div style="margin-top:32px;opacity:0.5;">— Peter Drucker</div>
  <div style="margin-top:48px;padding:8px 24px;border:1px solid var(--primary);border-radius:20px;font-size:0.85rem;color:var(--primary);">@yourbrand</div>
</div></body></html>"""},
            {"title": "Stats Post", "notes": "", "html": f"""<!DOCTYPE html><html><head>{s}</head><body>
<div style="display:flex;flex-direction:column;justify-content:center;align-items:center;height:100%;padding:80px;">
  <h2 style="font-size:1.2rem;text-transform:uppercase;letter-spacing:3px;color:var(--accent);margin-bottom:32px;">Did You Know?</h2>
  <div style="font-size:6rem;font-weight:800;color:var(--primary);margin-bottom:16px;">73%</div>
  <p style="font-size:1.5rem;text-align:center;opacity:0.7;max-width:600px;">of teams report increased productivity after adopting AI tools</p>
  <div style="margin-top:48px;display:flex;gap:16px;">
    <div style="width:60px;height:4px;background:var(--primary);border-radius:2px;"></div>
    <div style="width:60px;height:4px;background:rgba(255,255,255,0.1);border-radius:2px;"></div>
    <div style="width:60px;height:4px;background:rgba(255,255,255,0.1);border-radius:2px;"></div>
  </div>
</div></body></html>"""},
            {"title": "CTA Post", "notes": "", "html": f"""<!DOCTYPE html><html><head>{s}</head><body>
<div style="display:flex;flex-direction:column;justify-content:center;align-items:center;height:100%;padding:80px;background:linear-gradient(180deg,var(--bg) 0%,rgba(37,99,235,0.3) 100%);">
  <div style="width:80px;height:80px;border-radius:20px;background:var(--primary);margin-bottom:32px;display:flex;align-items:center;justify-content:center;font-size:2rem;">✦</div>
  <h2 style="font-size:2.5rem;font-weight:800;text-align:center;margin-bottom:16px;">Join 10,000+<br>Happy Users</h2>
  <p style="font-size:1.2rem;opacity:0.6;margin-bottom:40px;">Start your free trial today</p>
  <div style="padding:14px 40px;background:var(--accent);border-radius:30px;font-weight:700;color:#000;font-size:1.1rem;">Try It Free</div>
</div></body></html>"""},
        ],
    )


def _wireframe_kit() -> Template:
    s = _base_style(primary="#6B7280", secondary="#4B5563", accent="#3B82F6",
                    bg="#FFFFFF", text="#1F2937")
    return Template(
        id="wireframe_kit",
        name="Wireframe Kit",
        category="UI",
        description="2-page lo-fi wireframe for a web app (dashboard + detail page).",
        aspect_ratio="16:9",
        icon="🔲",
        pages=[
            {"title": "Dashboard Wireframe", "notes": "Low-fidelity dashboard layout.", "html": f"""<!DOCTYPE html><html><head>{s}</head><body>
<div style="display:flex;height:100%;font-family:var(--body-font),sans-serif;">
  <div style="width:240px;background:#F3F4F6;border-right:2px solid #E5E7EB;padding:24px;display:flex;flex-direction:column;gap:12px;">
    <div style="height:40px;background:#D1D5DB;border-radius:8px;"></div>
    <div style="height:1px;background:#E5E7EB;margin:8px 0;"></div>
    <div style="height:32px;background:#DBEAFE;border-radius:6px;border:2px solid var(--accent);"></div>
    <div style="height:32px;background:#E5E7EB;border-radius:6px;"></div>
    <div style="height:32px;background:#E5E7EB;border-radius:6px;"></div>
    <div style="height:32px;background:#E5E7EB;border-radius:6px;"></div>
    <div style="flex:1;"></div>
    <div style="height:32px;background:#E5E7EB;border-radius:6px;"></div>
  </div>
  <div style="flex:1;padding:32px;display:flex;flex-direction:column;gap:24px;">
    <div style="display:flex;justify-content:space-between;align-items:center;">
      <div style="height:32px;width:200px;background:#E5E7EB;border-radius:6px;"></div>
      <div style="display:flex;gap:12px;">
        <div style="height:36px;width:100px;background:#DBEAFE;border-radius:8px;border:2px solid var(--accent);"></div>
        <div style="height:36px;width:36px;background:#E5E7EB;border-radius:50%;"></div>
      </div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:16px;">
      <div style="height:100px;background:#F3F4F6;border-radius:12px;border:2px dashed #D1D5DB;"></div>
      <div style="height:100px;background:#F3F4F6;border-radius:12px;border:2px dashed #D1D5DB;"></div>
      <div style="height:100px;background:#F3F4F6;border-radius:12px;border:2px dashed #D1D5DB;"></div>
      <div style="height:100px;background:#F3F4F6;border-radius:12px;border:2px dashed #D1D5DB;"></div>
    </div>
    <div style="flex:1;background:#F9FAFB;border-radius:12px;border:2px dashed #D1D5DB;display:flex;align-items:center;justify-content:center;">
      <span style="color:#9CA3AF;font-size:1.2rem;">📊 Main Content Area / Chart</span>
    </div>
    <div style="display:grid;grid-template-columns:2fr 1fr;gap:16px;height:200px;">
      <div style="background:#F9FAFB;border-radius:12px;border:2px dashed #D1D5DB;display:flex;align-items:center;justify-content:center;"><span style="color:#9CA3AF;">📋 Table</span></div>
      <div style="background:#F9FAFB;border-radius:12px;border:2px dashed #D1D5DB;display:flex;align-items:center;justify-content:center;"><span style="color:#9CA3AF;">📝 Activity Feed</span></div>
    </div>
  </div>
</div></body></html>"""},
            {"title": "Detail Page Wireframe", "notes": "Detail / form page layout.", "html": f"""<!DOCTYPE html><html><head>{s}</head><body>
<div style="display:flex;height:100%;">
  <div style="width:240px;background:#F3F4F6;border-right:2px solid #E5E7EB;padding:24px;display:flex;flex-direction:column;gap:12px;">
    <div style="height:40px;background:#D1D5DB;border-radius:8px;"></div>
    <div style="height:1px;background:#E5E7EB;margin:8px 0;"></div>
    <div style="height:32px;background:#E5E7EB;border-radius:6px;"></div>
    <div style="height:32px;background:#DBEAFE;border-radius:6px;border:2px solid var(--accent);"></div>
    <div style="height:32px;background:#E5E7EB;border-radius:6px;"></div>
    <div style="flex:1;"></div>
    <div style="height:32px;background:#E5E7EB;border-radius:6px;"></div>
  </div>
  <div style="flex:1;padding:32px;display:flex;flex-direction:column;gap:24px;">
    <div style="display:flex;align-items:center;gap:12px;">
      <div style="height:32px;width:32px;background:#E5E7EB;border-radius:6px;display:flex;align-items:center;justify-content:center;color:#9CA3AF;">←</div>
      <div style="height:28px;width:250px;background:#E5E7EB;border-radius:6px;"></div>
      <div style="flex:1;"></div>
      <div style="height:32px;width:80px;background:#E5E7EB;border-radius:6px;"></div>
      <div style="height:32px;width:80px;background:#DBEAFE;border-radius:6px;border:2px solid var(--accent);"></div>
    </div>
    <div style="display:grid;grid-template-columns:2fr 1fr;gap:24px;flex:1;">
      <div style="display:flex;flex-direction:column;gap:16px;">
        <div style="padding:24px;background:#F9FAFB;border-radius:12px;border:2px dashed #D1D5DB;">
          <div style="height:20px;width:100px;background:#D1D5DB;border-radius:4px;margin-bottom:12px;"></div>
          <div style="height:40px;background:#E5E7EB;border-radius:8px;margin-bottom:12px;"></div>
          <div style="height:40px;background:#E5E7EB;border-radius:8px;margin-bottom:12px;"></div>
          <div style="height:120px;background:#E5E7EB;border-radius:8px;"></div>
        </div>
        <div style="padding:24px;background:#F9FAFB;border-radius:12px;border:2px dashed #D1D5DB;flex:1;display:flex;align-items:center;justify-content:center;">
          <span style="color:#9CA3AF;">📎 Attachments Area</span>
        </div>
      </div>
      <div style="display:flex;flex-direction:column;gap:16px;">
        <div style="padding:24px;background:#F9FAFB;border-radius:12px;border:2px dashed #D1D5DB;">
          <div style="height:20px;width:80px;background:#D1D5DB;border-radius:4px;margin-bottom:16px;"></div>
          <div style="display:flex;flex-direction:column;gap:8px;">
            <div style="height:24px;background:#E5E7EB;border-radius:4px;"></div>
            <div style="height:24px;background:#E5E7EB;border-radius:4px;"></div>
            <div style="height:24px;background:#E5E7EB;border-radius:4px;"></div>
          </div>
        </div>
        <div style="padding:24px;background:#F9FAFB;border-radius:12px;border:2px dashed #D1D5DB;flex:1;">
          <div style="height:20px;width:80px;background:#D1D5DB;border-radius:4px;margin-bottom:16px;"></div>
          <div style="display:flex;flex-direction:column;gap:12px;">
            <div style="height:48px;background:#E5E7EB;border-radius:8px;"></div>
            <div style="height:48px;background:#E5E7EB;border-radius:8px;"></div>
          </div>
        </div>
      </div>
    </div>
  </div>
</div></body></html>"""},
        ],
    )


def _blank_canvas() -> Template:
    s = _base_style()
    return Template(
        id="blank_canvas",
        name="Blank Canvas",
        category="General",
        description="Start from scratch — a single blank page.",
        aspect_ratio="16:9",
        icon="🧊",
        pages=[
            {"title": "Page 1", "notes": "", "html": f"""<!DOCTYPE html><html><head>{s}</head><body>
<div style="display:flex;justify-content:center;align-items:center;height:100%;">
  <p style="font-size:1.5rem;opacity:0.3;">Start designing — tell the AI what to create</p>
</div></body></html>"""},
        ],
    )


# ═══════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════════

_TEMPLATES: list[Template] | None = None


def _init_templates() -> list[Template]:
    global _TEMPLATES
    if _TEMPLATES is None:
        _TEMPLATES = [
            _pitch_deck(),
            _status_report(),
            _marketing_one_pager(),
            _product_launch(),
            _social_media(),
            _wireframe_kit(),
            _blank_canvas(),
        ]
    return _TEMPLATES


def get_templates() -> list[Template]:
    """Return all available templates."""
    return list(_init_templates())


def get_template(template_id: str) -> Template | None:
    """Return a single template by ID, or None."""
    for t in _init_templates():
        if t.id == template_id:
            return t
    return None


def get_template_categories() -> list[str]:
    """Return distinct template categories in display order."""
    seen = []
    for t in _init_templates():
        if t.category not in seen:
            seen.append(t.category)
    return seen
