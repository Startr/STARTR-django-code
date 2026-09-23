"""The META layer: the environment that renders the stubs into real templates.

Two template languages meet in this package, and keeping them apart is the whole
design.

* The **meta** layer is a stub in ``templates/django_startr/``. It is rendered
  once, at generate time, by the environment below.
* The **emitted** layer is what a stub produces: an ordinary Jinja2 template
  that Django renders on every request.

Both are Jinja2. If they shared delimiters, every emitted ``{% %}`` would have
to be escaped, which is exactly what the DTL version of this package did with
``{% templatetag openblock %}`` and ``{% verbatim %}`` fences — and why one line
of the old ``list.html`` ran to 600 characters.

So the meta layer moves to its own delimiters:

===============  ==========  ==========
Layer            Statement   Expression
===============  ==========  ==========
meta (stubs)     ``[% %]``   ``[[ ]]``
emitted (output) ``{% %}``   ``{{ }}``
===============  ==========  ==========

A stub can now write ``{% for lead in leads %}`` as literal text and it passes
straight through, while ``[[ model_name ]]`` is substituted. No escaping, and a
stub reads like the file it produces.
"""

from jinja2 import Environment, PackageLoader, StrictUndefined

#: Meta-layer delimiters. Square brackets because they are rare in HTML and in
#: Python, so a stub almost never has to escape one.
BLOCK_START, BLOCK_END = "[%", "%]"
VARIABLE_START, VARIABLE_END = "[[", "]]"
COMMENT_START, COMMENT_END = "[#", "#]"


def meta_environment() -> Environment:
    """Build the environment that renders stubs into templates.

    ``autoescape`` is off, and deliberately. This layer emits template *source*,
    not a rendered page — HTML-escaping it would corrupt every quote and
    ampersand in the file being written. Escaping is the emitted layer's job,
    where Django's Jinja2 backend turns it on.

    ``undefined=StrictUndefined`` because the failure it prevents is the
    expensive one: a mistyped ``[[ model_nmae ]]`` would otherwise render as
    empty and ship a subtly broken template that nobody notices until a page
    404s.
    """
    return Environment(
        loader=PackageLoader("django_startr", "templates/django_startr"),
        block_start_string=BLOCK_START,
        block_end_string=BLOCK_END,
        variable_start_string=VARIABLE_START,
        variable_end_string=VARIABLE_END,
        comment_start_string=COMMENT_START,
        comment_end_string=COMMENT_END,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
        autoescape=False,
        undefined=StrictUndefined,
    )


_ENV = None


def render_stub(stub_name: str, context: dict) -> str:
    """Render one stub to the text of a generated file."""
    global _ENV
    if _ENV is None:
        _ENV = meta_environment()
    return _ENV.get_template(stub_name).render(context)
