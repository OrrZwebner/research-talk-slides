#!/usr/bin/env python3
r"""Pre-render TeX to self-contained static SVG with MathJax 3 (tex-svg) in headless Chromium.

Slides then carry the SVG inline: no runtime MathJax, works offline and on GitHub Pages, and the
formula inherits the text colour (MathJax draws with currentColor). Needs Playwright (+ network
once, to fetch MathJax from the CDN at build time).

Usage:
    tex2svg.py [--display] TEX [TEX ...]          # prints JSON [{"tex", "svg"}, ...]
    tex2svg.py [--display] --json IN.json OUT.json
        IN.json is a list of TeX strings or a {key: tex} object; OUT.json mirrors its shape
        with SVG strings.
Options:
    --display        display (block) style instead of inline style
    --mathjax URL    MathJax build (default: jsDelivr mathjax@3.2.2 es5/tex-svg-full.js, which
                     handles \class{...}{...} for colouring a symbol from a kit token via CSS)
Exit codes: 0 ok, 1 a formula failed to render (MathJax error node), 2 Playwright missing.
"""
import argparse
import json
import sys

# The -full build preloads every TeX extension; the plain build autoloads \class, \color etc.
# asynchronously, and the synchronous tex2svg() then throws "MathJax retry".
DEFAULT_MJ = 'https://cdn.jsdelivr.net/npm/mathjax@3.2.2/es5/tex-svg-full.js'

JS_RENDER = """async ([texs, display]) => {
  await MathJax.startup.promise;
  return texs.map(t => {
    const node = MathJax.tex2svg(t, {display});
    const svg = node.querySelector('svg');
    const err = node.querySelector('[data-mjx-error]');
    return {tex: t, svg: svg ? svg.outerHTML : '', error: err ? err.getAttribute('data-mjx-error') : null};
  });
}"""


def render(texs, display, mathjax_url):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print('Playwright missing: pip install playwright && python -m playwright install chromium',
              file=sys.stderr)
        sys.exit(2)
    with sync_playwright() as p:
        b = p.chromium.launch(args=['--no-sandbox', '--disable-gpu'])
        page = b.new_page()
        page.set_content('<!doctype html><html><head></head><body></body></html>')
        # fontCache 'none' puts every glyph path inside its own SVG, so each one stands alone
        page.add_script_tag(content="window.MathJax={svg:{fontCache:'none'},startup:{typeset:false}};")
        page.add_script_tag(url=mathjax_url)
        out = page.evaluate(JS_RENDER, [list(texs), display])
        b.close()
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('tex', nargs='*')
    ap.add_argument('--display', action='store_true')
    ap.add_argument('--json', nargs=2, metavar=('IN', 'OUT'))
    ap.add_argument('--mathjax', default=DEFAULT_MJ)
    a = ap.parse_args()
    if a.json:
        src = json.load(open(a.json[0], encoding='utf-8'))
        keys = list(src.keys()) if isinstance(src, dict) else None
        texs = [src[k] for k in keys] if keys else list(src)
    else:
        keys, texs = None, a.tex
    if not texs:
        ap.error('no TeX given')
    res = render(texs, a.display, a.mathjax)
    bad = [r for r in res if r['error'] or not r['svg']]
    if a.json:
        payload = {k: r['svg'] for k, r in zip(keys, res)} if keys else [r['svg'] for r in res]
        json.dump(payload, open(a.json[1], 'w', encoding='utf-8'), ensure_ascii=False)
        print(json.dumps({'out': a.json[1], 'n': len(res), 'errors': [(r['tex'], r['error']) for r in bad]}))
    else:
        print(json.dumps(res, ensure_ascii=False))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
