# cloudless brand guidelines

> One agent. Any cloud. Zero rewrites.

This document is the source of truth for the `cloudless` visual and verbal
identity. If you're building something with the cloudless brand — a slide
deck, a landing page, a t-shirt — start here.

---

## The name

The brand is always lowercase: **`cloudless`**.

| Form          | Use                          |
|---------------|------------------------------|
| `cloudless`   | Headlines, body copy, code   |
| `cloudless.`  | Logo (with period as accent) |
| `Cloudless`   | Never                        |
| `CLOUDLESS`   | Never                        |
| `CloudLess`   | Never                        |

The period in the logo is intentional — it reads as a definitive statement
("you're done here") and visually echoes Python's dot notation. The CLI is
`cloudless` (no period); the brand mark is `cloudless.` (period included).

---

## Color

cloudless is intentionally distinct from AWS orange and GCP blue/red/yellow.
The palette reads as "infrastructure but lifted" — deep navy as the
foundation, a coral accent as the spark of life on top.

### Primary palette

| Token        | Hex       | Role                                            |
|--------------|-----------|-------------------------------------------------|
| `--ink`      | `#0F1B2D` | Headlines, branded dark surfaces                |
| `--mist`     | `#E8EEF5` | Page background on light themes                 |
| `--paper`    | `#FFFFFF` | Card / surface background                       |
| `--slate`    | `#475569` | Body text                                       |
| `--spark`    | `#FF5C39` | Primary accent — CTAs, hover, brand flourish    |
| `--sky`      | `#3B82F6` | Secondary accent — info, links                  |

### Supporting palette

| Token         | Hex       | Role                                          |
|---------------|-----------|-----------------------------------------------|
| `--moss`      | `#16A34A` | Success / pass states                         |
| `--ember`     | `#DC2626` | Error / blocked states                        |
| `--amber`     | `#F59E0B` | Warning                                       |
| `--graphite`  | `#1F2937` | Code block background on light                |
| `--fog`       | `#94A3B8` | Tertiary / muted text                         |

### Contrast rules

- `--ink` on `--mist` or `--paper`: ✅ AA Large + AAA Normal
- `--slate` on `--paper`: ✅ AAA
- `--spark` on `--ink`: ✅ AA Large (use for CTAs on dark surfaces)
- `--spark` on `--paper`: ⚠️ borderline for body text — only for buttons + flourishes, never paragraphs
- `--sky` on `--paper`: ✅ AA Normal

Never use spark on mist or sky on mist (both fail AA).

---

## Typography

| Role     | Family                 | Weights   | Notes                                            |
|----------|------------------------|-----------|--------------------------------------------------|
| Display  | Inter                  | 700, 800  | Tight tracking, used in hero + section heads     |
| Body     | Inter                  | 400, 500  | Comfortable line-height (1.6+)                   |
| Code     | JetBrains Mono         | 400, 600  | All code samples, terminal output                |
| Fallback | system-ui, sans-serif  | —         | If Inter doesn't load                            |

### Scale

| Level | Size   | Line | Weight | Tracking |
|-------|--------|------|--------|----------|
| h1    | 56px   | 1.05 | 800    | -0.03em  |
| h2    | 36px   | 1.15 | 700    | -0.02em  |
| h3    | 24px   | 1.25 | 700    | -0.01em  |
| body  | 16px   | 1.65 | 400    |  0       |
| small | 14px   | 1.5  | 400    |  0       |
| code  | 14px   | 1.5  | 400    |  0       |

---

## Voice & tone

cloudless is for developers shipping production systems. The voice is what
you'd say to a senior colleague over coffee: direct, technical, confident,
without selling.

### Do

- **State what's true.** "Deploys to AWS in 98 seconds." (We measured.)
- **Lead with code.** Then explain. Not the reverse.
- **Use active verbs.** "ships", "runs", "deploys", "fails" — not "enables", "leverages", "powers".
- **Lowercase the brand and the CLI.** Always.
- **Show specifics.** "391 passing tests, zero skipped." Numbers earn trust.
- **Name the tradeoff.** When something doesn't work, say so before the user finds out.

### Don't

- **No "AI agent" buzzword stacking.** We say "agent". Once. Then we describe what it does.
- **No "powered by", "leveraging", "harnessing".** Banned.
- **No emojis in docs body or code comments.** Permitted in social posts, README hero, and decorative landing-page elements only.
- **No marketing-speak superlatives.** "world-class", "industry-leading", "best-in-class" — all banned.
- **No future tense for unshipped features.** Don't say "cloudless will". Say "cloudless ships" or "in v1.2 cloudless ships". If it's not committed, it's not here.

### Tone calibration

| Context             | Example                                                                    |
|---------------------|----------------------------------------------------------------------------|
| Headline            | "Write your agent once. Ship it to any cloud."                             |
| Sub-tagline         | "AWS Bedrock AgentCore and GCP Vertex AI in one Python file."              |
| Body                | "cloudless deploys the same agent class to either cloud. You pick at `cloudless deploy` time." |
| Error message       | "Bedrock returned 429. Backing off 12s. Attempt 2 of 3."                   |
| README hero         | "**Write your agent once. Ship it to any cloud.** A Python framework for AWS Bedrock AgentCore and GCP Vertex AI." |
| Tweet               | "cloudless v0.1: write an agent once, deploy to AWS or GCP unchanged. 391 passing tests against real cloud."  |

---

## Logo usage

The mark always carries the period: `cloudless.`. The dot is brand.

### Clear space

Maintain at least the height of the `o` glyph as clear space on all sides.

### Color variations

| Variant     | Use                                                      |
|-------------|----------------------------------------------------------|
| `ink`       | Default — most surfaces                                  |
| `spark`     | Brand flourishes, hover states, never large body         |
| `paper`     | On dark surfaces only                                    |
| `mark only` | Favicons, social, small-context (the `.` becomes a sun)  |

### Don't

- Don't recolor the dot independently of the wordmark.
- Don't add gradients or shadows.
- Don't stretch or condense.
- Don't put on busy photographic backgrounds without a flat tint underneath.

---

## Voice samples

### Good

> cloudless deploys the same `@cloudless.agent` Python class to either AWS
> Bedrock AgentCore or GCP Vertex AI Agent Engine. The CLI handles container
> builds, IAM, Cognito, and the cross-cloud A2A wiring. You write the agent.

### Bad (don't do this)

> cloudless is a revolutionary AI agent platform that empowers developers
> to leverage cutting-edge cloud-native infrastructure across multiple
> hyperscalers, unlocking unprecedented agility for next-generation
> agentic applications.

---

## Asset checklist

When shipping a new brand surface (slide deck, conference booth, swag, etc.):

- [ ] Lowercase `cloudless` everywhere
- [ ] Logo uses approved SVG (no recolor outside the palette)
- [ ] Primary CTA is `--spark` on `--ink` background, or `--ink` on `--paper`
- [ ] Code samples use JetBrains Mono and respect the syntax theme
- [ ] No banned words ("leverage", "powered by", etc.)
- [ ] Numbers are real (link the source if asked)
- [ ] No emojis in docs body — social/landing only
