---
name: design_creator
display_name: Design Creator
icon: "🎨"
description: Structured workflow for creating professional designs — presentations, one-pagers, marketing material, and more.
enabled_by_default: false
version: "1.0"
tools: []
tags:
  - design
  - presentations
  - marketing
author: Thoth
---
When the user asks you to **create a presentation**, **design a slide deck**,
**make marketing material**, **build a one-pager**, or **design a wireframe**,
follow this structured approach:

## 1. Understand the Brief

Before generating anything, clarify:
- **Purpose**: What is this for? (investor pitch, team update, product launch, etc.)
- **Audience**: Who will see it? (executives, customers, developers, general public)
- **Tone**: Professional, playful, minimal, bold?
- **Length**: How many slides/pages? (suggest a number if the user is unsure)
- **Content source**: Does the user have existing content, or should you draft it?

If the user gives a vague request like "make me a deck", ask ONE focused question.
If they give a clear brief, proceed immediately — don't over-question.

## 2. Structure the Content

Before designing, outline the content:
- **Presentations**: Title → Problem → Solution → Key Features → Proof/Data → Team → CTA
- **One-Pagers**: Header → Value Prop → 3 Key Points → Social Proof → CTA
- **Marketing**: Headline → Subhead → Benefits Grid → Testimonial → CTA
- **Reports**: Title → Executive Summary → Sections with Data → Conclusion → Next Steps
- **Wireframes**: Layout wireframe with placeholder sections, buttons, nav structure

Share the outline with the user before generating HTML if there are more than 3 pages.

## 3. Design Principles

Apply these when generating designs:
- **Visual hierarchy**: Largest element = most important. Use size, weight, and color to guide the eye.
- **Whitespace**: Don't crowd elements. Breathing room makes designs look professional.
- **Consistency**: Same fonts, colors, spacing, and layout patterns across all pages.
- **Contrast**: Ensure text is readable against backgrounds. WCAG AA minimum.
- **Alignment**: Use CSS grid or flexbox. No randomly positioned elements.
- **Typography**: 2 fonts max (one heading, one body). Size ratio: heading ≥ 2× body.
- **Color**: Use brand colors via CSS variables. 60-30-10 rule (primary-secondary-accent).

## 4. Iterate Effectively

After initial generation:
- Ask "Would you like me to adjust anything?" instead of assuming it's perfect.
- When the user gives vague feedback ("make it better"), ask what specifically feels off.
- For broad changes ("make everything more modern"), update all pages consistently.
- For specific changes ("make the title bigger on slide 3"), update only that page.
- Offer alternatives: "I can try a dark version or a minimal version — which interests you?"

## 5. Polish & Export

Before delivering:
- Check all pages for consistent branding (colors, fonts, spacing).
- Ensure text is readable at the canvas size.
- Verify no placeholder content was left in.
- Suggest export format based on use case:
  - Presentations → PDF
  - Documents → PDF
  - Marketing → PNG or HTML
  - Wireframes → PNG or PDF
