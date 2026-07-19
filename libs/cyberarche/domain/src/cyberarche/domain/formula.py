"""Safe, bounded expression evaluator for formula properties (collections-formula).

A formula is a small expression over a row's other properties, e.g.
``prop("Price") * prop("Qty")`` or ``if(prop("Done"), "yes", "no")``. It is
parsed with :func:`ast.parse` and evaluated by walking a strict whitelist of AST
node types — there is no ``eval``/``exec`` and no attribute/subscript/lambda/name
access, so arbitrary code can never run.

Two entry points:

* :func:`validate_formula` — parse + shape-check; raises
  :class:`ValidationFailed` on a syntax error or any unsupported construct. Used
  when a formula property is created/edited.
* :func:`evaluate_formula` — evaluate against a ``resolver(name) -> value``
  callback (backing ``prop("Name")``) with an injected ``now`` datetime (backing
  ``now()``; ambient time is never read here). Any evaluation error degrades to
  ``None`` so a formula cell simply shows blank rather than raising.

``prop("Title")`` resolves to the row's document title; every other name is
looked up as another property's value via the resolver. Formulas reference only
non-formula properties and the title (formula-referencing-formula is not
supported — such a reference resolves to ``None``).
"""

from __future__ import annotations

import ast
import io
import operator
import tokenize
from collections.abc import Callable
from datetime import UTC, date, datetime

from cyberarche.domain.errors import ValidationFailed

Resolver = Callable[[str], object]

# Renamed target for a ``if(...)`` function call. ``if`` is a Python keyword and
# cannot be parsed as a call, so we rewrite the source token before parsing.
_IF_FUNC = "__formula_if__"

# Binary / unary / boolean / comparison operators, keyed by their AST node type.
_BINOPS: dict[type, Callable[[object, object], object]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARYOPS: dict[type, Callable[[object], object]] = {
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
    ast.Not: operator.not_,
}
_COMPARE: dict[type, Callable[[object, object], object]] = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}

# AST node types allowed anywhere in a formula (functions/names handled apart).
_ALLOWED_NODES: tuple[type, ...] = (
    ast.Expression,
    ast.Constant,
    ast.BinOp,
    ast.UnaryOp,
    ast.BoolOp,
    ast.Compare,
    ast.IfExp,
    ast.Load,
    ast.And,
    ast.Or,
    *_BINOPS,
    *_UNARYOPS,
    *_COMPARE,
)

_SIGNIFICANT = frozenset(
    {tokenize.NAME, tokenize.NUMBER, tokenize.STRING, tokenize.OP}
)
# Tokens that complete a value; a ternary ``if`` follows one, a call ``if`` never
# does. ``and/or/not/if/else`` are NAME tokens that do NOT complete a value.
_VALUE_CLOSERS = frozenset({")", "]", "}"})
_OPERATOR_KEYWORDS = frozenset({"and", "or", "not", "in", "is", "if", "else"})


# ---- source rewrite: if(...) -> __formula_if__(...) -------------------------


def _completes_value(tok: tokenize.TokenInfo | None) -> bool:
    """Whether the previous token completes a value (so a following ``if`` is the
    ternary keyword rather than a call)."""
    if tok is None:
        return False
    if tok.type in (tokenize.NUMBER, tokenize.STRING):
        return True
    if tok.type == tokenize.NAME:
        return tok.string not in _OPERATOR_KEYWORDS
    return tok.type == tokenize.OP and tok.string in _VALUE_CLOSERS


def _next_is_lparen(tokens: list[tokenize.TokenInfo], index: int) -> bool:
    for tok in tokens[index + 1 :]:
        if tok.type in _SIGNIFICANT:
            return tok.type == tokenize.OP and tok.string == "("
    return False


def _is_if_call(
    tok: tokenize.TokenInfo,
    prev: tokenize.TokenInfo | None,
    tokens: list[tokenize.TokenInfo],
    index: int,
) -> bool:
    return (
        tok.type == tokenize.NAME
        and tok.string == "if"
        and not _completes_value(prev)
        and _next_is_lparen(tokens, index)
    )


def _rewrite_if_calls(expr: str) -> str:
    """Rename the keyword ``if`` to a callable name when used as ``if(...)``,
    leaving the ternary ``a if b else c`` untouched. String-safe (token based)."""
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(expr).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return expr  # let ast.parse surface the real error
    out: list[tuple[int, str]] = []
    prev: tokenize.TokenInfo | None = None
    for index, tok in enumerate(tokens):
        string = _IF_FUNC if _is_if_call(tok, prev, tokens, index) else tok.string
        out.append((tok.type, string))
        if tok.type in _SIGNIFICANT:
            prev = tok
    return tokenize.untokenize(out)


def _parse(expr: str) -> ast.expr:
    try:
        return ast.parse(_rewrite_if_calls(expr), mode="eval").body
    except SyntaxError as exc:
        raise ValidationFailed(f"invalid formula: {exc.msg}") from exc


# ---- validation -------------------------------------------------------------


def validate_formula(expr: str) -> None:
    """Parse and shape-check a formula. Raises :class:`ValidationFailed` on a
    syntax error or any construct outside the whitelist."""
    _validate_node(_parse(expr))


def _validate_node(node: ast.AST) -> None:
    if isinstance(node, ast.Call):
        _validate_call(node)
        return
    if isinstance(node, ast.Name):
        raise ValidationFailed(f"unsupported name in formula: {node.id!r}")
    if not isinstance(node, _ALLOWED_NODES):
        raise ValidationFailed(
            f"unsupported expression in formula: {type(node).__name__}"
        )
    for child in ast.iter_child_nodes(node):
        _validate_node(child)


def _validate_call(node: ast.Call) -> None:
    if not isinstance(node.func, ast.Name) or node.func.id not in _FUNCTIONS:
        raise ValidationFailed("unsupported function call in formula")
    if node.keywords:
        raise ValidationFailed("keyword arguments are not supported in formulas")
    for arg in node.args:
        _validate_node(arg)


# ---- evaluation -------------------------------------------------------------


def evaluate_formula(expr: str, resolver: Resolver, *, now: datetime) -> object:
    """Evaluate a formula against ``resolver`` (for ``prop("Name")``) and the
    injected ``now``. Never raises: any error yields ``None``."""
    try:
        return _eval(_parse(expr), resolver, now)
    except ValidationFailed:
        raise
    except Exception:
        return None


def _eval(node: ast.AST, resolver: Resolver, now: datetime) -> object:
    handler = _EVAL_DISPATCH.get(type(node))
    if handler is None:
        raise ValidationFailed(
            f"unsupported expression in formula: {type(node).__name__}"
        )
    return handler(node, resolver, now)


def _eval_constant(node: ast.Constant, resolver: Resolver, now: datetime) -> object:
    return node.value


def _eval_binop(node: ast.BinOp, resolver: Resolver, now: datetime) -> object:
    left = _eval(node.left, resolver, now)
    right = _eval(node.right, resolver, now)
    op_type = type(node.op)
    if op_type in (ast.Div, ast.Mod) and right == 0:
        return None  # divide/modulo by zero degrades to blank
    return _BINOPS[op_type](left, right)


def _eval_unaryop(node: ast.UnaryOp, resolver: Resolver, now: datetime) -> object:
    return _UNARYOPS[type(node.op)](_eval(node.operand, resolver, now))


def _eval_boolop(node: ast.BoolOp, resolver: Resolver, now: datetime) -> object:
    result: object = isinstance(node.op, ast.And)
    for child in node.values:
        result = _eval(child, resolver, now)
        if isinstance(node.op, ast.And) and not result:
            return result
        if isinstance(node.op, ast.Or) and result:
            return result
    return result


def _eval_compare(node: ast.Compare, resolver: Resolver, now: datetime) -> object:
    left = _eval(node.left, resolver, now)
    for op, comparator in zip(node.ops, node.comparators):
        right = _eval(comparator, resolver, now)
        if not _COMPARE[type(op)](left, right):
            return False
        left = right
    return True


def _eval_ifexp(node: ast.IfExp, resolver: Resolver, now: datetime) -> object:
    branch = node.body if _eval(node.test, resolver, now) else node.orelse
    return _eval(branch, resolver, now)


def _eval_call(node: ast.Call, resolver: Resolver, now: datetime) -> object:
    func = _FUNCTIONS.get(node.func.id) if isinstance(node.func, ast.Name) else None
    if func is None:
        raise ValidationFailed("unsupported function call in formula")
    args = [_eval(arg, resolver, now) for arg in node.args]
    return func(args, resolver, now)


_EVAL_DISPATCH: dict[type, Callable[[ast.AST, Resolver, datetime], object]] = {
    ast.Constant: _eval_constant,
    ast.BinOp: _eval_binop,
    ast.UnaryOp: _eval_unaryop,
    ast.BoolOp: _eval_boolop,
    ast.Compare: _eval_compare,
    ast.IfExp: _eval_ifexp,
    ast.Call: _eval_call,
}


# ---- value coercion helpers -------------------------------------------------


def _to_number(value: object) -> float | int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        try:
            parsed = float(value)
        except ValueError:
            return None
        return int(parsed) if parsed.is_integer() else parsed
    return None


def _to_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=UTC)
    if isinstance(value, str):
        return _parse_iso(value)
    return None


def _parse_iso(text: str) -> datetime | None:
    text = text.strip()
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        pass
    try:
        parsed = date.fromisoformat(text)
    except ValueError:
        return None
    return datetime(parsed.year, parsed.month, parsed.day, tzinfo=UTC)


def _stringify(value: object) -> str:
    return "" if value is None else str(value)


# ---- whitelisted functions --------------------------------------------------
# Each takes (evaluated positional args, resolver, now) and returns a value.


def _fn_prop(args: list, resolver: Resolver, now: datetime) -> object:
    return resolver(_stringify(args[0]))


def _fn_now(args: list, resolver: Resolver, now: datetime) -> object:
    return now


def _fn_if(args: list, resolver: Resolver, now: datetime) -> object:
    cond, when_true, when_false = args
    return when_true if cond else when_false


def _fn_round(args: list, resolver: Resolver, now: datetime) -> object:
    number = _to_number(args[0])
    if number is None:
        return None
    ndigits = int(args[1]) if len(args) > 1 else 0
    return round(number, ndigits)


def _fn_abs(args: list, resolver: Resolver, now: datetime) -> object:
    number = _to_number(args[0])
    return None if number is None else abs(number)


def _fn_min(args: list, resolver: Resolver, now: datetime) -> object:
    numbers = [n for n in map(_to_number, args) if n is not None]
    return min(numbers) if numbers else None


def _fn_max(args: list, resolver: Resolver, now: datetime) -> object:
    numbers = [n for n in map(_to_number, args) if n is not None]
    return max(numbers) if numbers else None


def _fn_number(args: list, resolver: Resolver, now: datetime) -> object:
    return _to_number(args[0])


def _fn_date(args: list, resolver: Resolver, now: datetime) -> object:
    return _to_datetime(args[0])


def _fn_days_between(args: list, resolver: Resolver, now: datetime) -> object:
    start = _to_datetime(args[0])
    end = _to_datetime(args[1])
    if start is None or end is None:
        return None
    return (end.date() - start.date()).days


def _fn_concat(args: list, resolver: Resolver, now: datetime) -> object:
    return "".join(_stringify(arg) for arg in args)


def _fn_length(args: list, resolver: Resolver, now: datetime) -> object:
    value = args[0]
    if value is None:
        return 0
    if isinstance(value, (str, list, tuple)):
        return len(value)
    return len(str(value))


def _fn_contains(args: list, resolver: Resolver, now: datetime) -> object:
    return _stringify(args[1]) in _stringify(args[0])


def _fn_lower(args: list, resolver: Resolver, now: datetime) -> object:
    return _stringify(args[0]).lower()


def _fn_upper(args: list, resolver: Resolver, now: datetime) -> object:
    return _stringify(args[0]).upper()


_FUNCTIONS: dict[str, Callable[[list, Resolver, datetime], object]] = {
    "prop": _fn_prop,
    "now": _fn_now,
    "if": _fn_if,
    _IF_FUNC: _fn_if,
    "round": _fn_round,
    "abs": _fn_abs,
    "min": _fn_min,
    "max": _fn_max,
    "number": _fn_number,
    "date": _fn_date,
    "days_between": _fn_days_between,
    "concat": _fn_concat,
    "length": _fn_length,
    "contains": _fn_contains,
    "lower": _fn_lower,
    "upper": _fn_upper,
}
